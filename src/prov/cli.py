"""`prov` command line.

    prov run [--kind K] [--tag key=value ...] [--notes TEXT] -- <command> [args...]
        Snapshot every repo in prov.toml, run the command with PROV_RUN_ID set, write
        <registry>/records/runs/<run_id>.yaml (status `running` at start, final at exit), commit it,
        and exit with the command's exit code. Artifacts published by the command become its outputs.

    prov publish <path> --kind K [--meta key=value ...] [--copy]
        Move (or copy) a file or folder into the store under a new ID, make it read-only, record it.

    prov show <id>
        Print a run or artifact record (and an artifact's store path).

    prov ingest lerobot <path> [--source-map F.jsonl] [--calib calib_ID ...] [--meta k=v] [--copy]
        Publish a LeRobot folder as a session and register one ep_ ID per episode.

    prov annotate <ep_id> key=value [key=value ...]
        Label an episode (outcome, failure_type, tags, note, ...); the latest value wins.

    prov catalog rebuild
        Rebuild the DuckDB catalog from the registry.

    prov q "<sql>"
        Query the catalog (rebuilt first if the registry changed). Tab-separated, with a header.

    prov dataset freeze <name> (--query SQL | --episodes FILE) [--parent REF] [--notes T]
                               [--holdout F [--seed N] [--by episode|session]]
        Freeze ds:<name>/<next> from episode IDs; with --holdout also <name>-train and <name>-holdout.

    prov alias set <kind:name/version> <ID>        a version: set once, never changes
    prov alias label <kind:name@label> <kind:name/version>   move a label
    prov alias show <ID or alias>                   print what it resolves to

    prov init <project>
        Make the current repo a prov project: prov.toml, journal/ skeleton, journal/media link into
        the store, agent skills linked into .claude/skills/. Never overwrites.

    prov journal new <topic> [--continues <doc>]   start today's doc from the template
    prov journal lint                              check frontmatter, IDs, images, links, NOW.md
    prov journal index                             rebuild journal/INDEX.md (docs by date and status)

    prov rerun <run_id>
        Run the same command again on the recorded code snapshot (git worktrees), as a new run
        tagged rerun_of=<run_id>.

    prov trace <ID or alias>    upstream lineage: what it was made from, down to sessions and commits
    prov uses <ID or alias>     downstream: every run, artifact and dataset built on it
"""

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from prov import aliases, api, catalog, config, datasets, episodes, gitsnap, journal, lineage, registry, rerun, store, wb
from prov.ids import kind_of, new_id
from prov.records import Env, RunRecord

KINDS = ["collect", "export", "train", "eval", "analysis", "other"]


def _env() -> Env:
    gpus = []
    if shutil.which("nvidia-smi"):
        p = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True)
        gpus = [g.strip() for g in p.stdout.splitlines() if g.strip()] if p.returncode == 0 else []
    return Env(python=platform.python_version(), platform=platform.platform(), gpu=gpus)


def _pairs(items: list[str]) -> dict[str, str]:
    for item in items:
        if "=" not in item:
            raise config.ConfigError(f"expected key=value, got {item!r}")
    return dict(item.split("=", 1) for item in items)


def cmd_run(args: argparse.Namespace) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("prov run: no command given (prov run -- <command>)", file=sys.stderr)
        return 2
    machine = config.load_machine()
    project = config.load_project(Path.cwd())
    tags = _pairs(args.tag)
    store.warn_if_low_space(machine.store_root)

    run_id = new_id("run")
    rel = f"records/runs/{run_id}.yaml"
    code = [gitsnap.snapshot(repo, run_id) for repo in project.repos]
    record = RunRecord(
        id=run_id, kind=args.kind, project=project.project,
        started=datetime.now(timezone.utc), status="running", host=socket.gethostname(),
        cwd=str(Path.cwd()), command=command, code=code, env=_env(), tags=tags, notes=args.notes,
    )
    registry.write(machine.registry, rel, record.to_yaml())
    for c in code:
        if c.dirty:
            print(f"prov: {c.repo} is dirty; snapshot {c.snapshot[:10]} at {c.ref}", file=sys.stderr)
        if not c.pushed:
            print(f"prov: {c.repo}: {c.ref} not pushed (no origin or push failed)", file=sys.stderr)
    print(f"prov: {run_id}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        files = {k: Path(tmp) / k for k in ("inputs", "outputs", "summary", "wandb")}
        for f in files.values():
            f.touch()
        env = {**os.environ, "PROV_RUN_ID": run_id, "PROV_PROJECT": project.project,
               store.INPUTS_ENV: str(files["inputs"]), store.OUTPUTS_ENV: str(files["outputs"]),
               api.SUMMARY_ENV: str(files["summary"]), wb.WANDB_ENV: str(files["wandb"])}
        try:
            rc = subprocess.run(command, env=env).returncode
        except FileNotFoundError:
            rc = 127
        except KeyboardInterrupt:
            rc = -2
        record.inputs = list(dict.fromkeys(l for l in files["inputs"].read_text().splitlines() if l))
        record.outputs = [line for line in files["outputs"].read_text().splitlines() if line]
        for line in files["summary"].read_text().splitlines():
            record.summary.update(json.loads(line))
        record.wandb = files["wandb"].read_text().strip() or None

    record.finished = datetime.now(timezone.utc)
    record.exit_code = rc
    record.status = "ok" if rc == 0 else ("killed" if rc < 0 else "failed")
    path = registry.write(machine.registry, rel, record.to_yaml())
    registry.commit(machine.registry, path, f"run {run_id} {record.status}")
    return rc if rc >= 0 else 128 - rc


def cmd_publish(args: argparse.Namespace) -> int:
    record = store.publish(Path(args.path), args.kind, meta=_pairs(args.meta), copy=args.copy,
                           alias=args.alias)
    print(record.id)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    machine = config.load_machine()
    args.id = aliases.resolve(args.id, machine.registry)
    if kind_of(args.id) == "run":
        path = machine.registry / "records" / "runs" / f"{args.id}.yaml"
        if not path.is_file():
            raise store.StoreError(f"no record for {args.id}")
        print(path.read_text(), end="")
        return 0
    record = store.load(args.id, machine.registry)
    print(record.to_yaml(), end="")
    if record.uri:
        print(f"# path: {store.resolve(record.uri, machine.store_root)}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    session, eps = episodes.ingest_lerobot(
        Path(args.path), source_map=Path(args.source_map) if args.source_map else None,
        calibrations=args.calib, meta=_pairs(args.meta), copy=args.copy)
    print(f"{session.id}\t{len(eps)} episodes")
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    if not args.labels:
        raise config.ConfigError("give at least one key=value")
    episodes.annotate(args.episode, _pairs(args.labels))
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    print(catalog.rebuild())
    return 0


def cmd_q(args: argparse.Namespace) -> int:
    with catalog.connect() as con:
        cur = con.execute(args.sql)
        print("\t".join(d[0] for d in cur.description))
        for row in cur.fetchall():
            print("\t".join("" if v is None else str(v) for v in row))
    return 0


def cmd_dataset(args: argparse.Namespace) -> int:
    eps = Path(args.episodes).read_text().split() if args.episodes else None
    out = datasets.freeze(args.name, episodes=eps, query=args.query, parent=args.parent, notes=args.notes,
                          holdout=args.holdout, seed=args.seed, by=args.by)
    for role, rec in out.items():
        print(f"{rec.meta['alias']}\t{rec.id}\t{rec.meta['episodes']} episodes\t{rec.meta['sessions']} sessions")
    return 0


def cmd_alias(args: argparse.Namespace) -> int:
    if args.action == "set":
        aliases.set_version(args.ref, args.target)
    elif args.action == "label":
        aliases.set_label(args.ref, args.target)
    else:
        print(aliases.resolve(args.ref))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    made = journal.init_project(Path.cwd(), args.project)
    print("\n".join(made) if made else "nothing to do: already set up")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    if args.action == "new":
        if not args.topic:
            raise journal.JournalError("journal new needs a topic")
        print(journal.new_doc(args.topic, continues=args.continues))
        return 0
    root = journal.journal_root()
    if args.action == "index":
        print(journal.index(root))
        return 0
    problems = journal.lint(root)
    print("\n".join(problems) if problems else "journal OK")
    return 1 if problems else 0


def cmd_rerun(args: argparse.Namespace) -> int:
    return rerun.rerun(args.run_id)


def cmd_lineage(args: argparse.Namespace) -> int:
    walk = lineage.trace if args.cmd == "trace" else lineage.uses
    arrow = "<- " if args.cmd == "trace" else "-> "
    for depth, _, text in walk(args.ref):
        print(("  " * (depth - 1) + arrow if depth else "") + text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prov")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run a command and record it")
    run.add_argument("--kind", choices=KINDS, default="other")
    run.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    run.add_argument("--notes")
    run.add_argument("command", nargs=argparse.REMAINDER)
    pub = sub.add_parser("publish", help="move a file or folder into the store and record it")
    pub.add_argument("path")
    pub.add_argument("--kind", required=True, choices=sorted(store.KIND_DIRS))
    pub.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE")
    pub.add_argument("--copy", action="store_true", help="copy instead of move")
    pub.add_argument("--alias", help="also name it kind:name/version")
    show = sub.add_parser("show", help="print a run or artifact record")
    show.add_argument("id")
    ing = sub.add_parser("ingest", help="register a recording session and its episodes")
    ing.add_argument("format", choices=["lerobot"])
    ing.add_argument("path")
    ing.add_argument("--source-map", help="JSONL: episode_index -> MCAP path/raw ID/time range")
    ing.add_argument("--calib", action="append", default=[], metavar="CALIB_ID")
    ing.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE")
    ing.add_argument("--copy", action="store_true", help="copy instead of move")
    ann = sub.add_parser("annotate", help="label an episode")
    ann.add_argument("episode")
    ann.add_argument("labels", nargs="*", metavar="KEY=VALUE")
    cat = sub.add_parser("catalog", help="catalog maintenance")
    cat.add_argument("action", choices=["rebuild"])
    q = sub.add_parser("q", help="query the catalog with SQL")
    q.add_argument("sql")
    ds = sub.add_parser("dataset", help="dataset versions")
    ds.add_argument("action", choices=["freeze"])
    ds.add_argument("name")
    sel = ds.add_mutually_exclusive_group(required=True)
    sel.add_argument("--query", help="SQL on the catalog returning episode IDs (first column)")
    sel.add_argument("--episodes", help="file with one episode ID per line")
    ds.add_argument("--parent", help="dataset this one derives from (ID or alias)")
    ds.add_argument("--notes")
    ds.add_argument("--holdout", type=float, help="fraction to hold out, e.g. 0.1")
    ds.add_argument("--seed", type=int, default=0)
    ds.add_argument("--by", choices=["episode", "session"], default="episode")
    al = sub.add_parser("alias", help="readable names for IDs")
    al.add_argument("action", choices=["set", "label", "show"])
    al.add_argument("ref")
    al.add_argument("target", nargs="?")
    sub.add_parser("init", help="make this repo a prov project").add_argument("project")
    jr = sub.add_parser("journal", help="project journal")
    jr.add_argument("action", choices=["new", "lint", "index"])
    jr.add_argument("topic", nargs="?")
    jr.add_argument("--continues", help="doc folder this one continues (relative to journal/)")
    sub.add_parser("rerun", help="re-run a recorded run on its code snapshot").add_argument("run_id")
    for name, help_ in (("trace", "upstream lineage"), ("uses", "downstream lineage")):
        sub.add_parser(name, help=help_).add_argument("ref")
    args = parser.parse_args(argv)
    if args.cmd == "alias" and args.action != "show" and not args.target:
        parser.error(f"alias {args.action} needs a target")
    handlers = {"init": cmd_init, "journal": cmd_journal, "rerun": cmd_rerun, "trace": cmd_lineage, "uses": cmd_lineage, "dataset": cmd_dataset, "alias": cmd_alias, "run": cmd_run, "publish": cmd_publish, "show": cmd_show, "ingest": cmd_ingest,
                "annotate": cmd_annotate, "catalog": cmd_catalog, "q": cmd_q}
    try:
        return handlers[args.cmd](args)
    except (config.ConfigError, gitsnap.SnapshotError, store.StoreError, aliases.AliasError,
            datasets.DatasetError, rerun.RerunError, journal.JournalError, ValueError, catalog.duckdb.Error) as exc:
        print(f"prov: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
