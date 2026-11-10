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
"""

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from prov import aliases, catalog, config, datasets, episodes, gitsnap, registry, store
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
        inputs_file, outputs_file = Path(tmp) / "inputs", Path(tmp) / "outputs"
        inputs_file.touch()
        outputs_file.touch()
        env = {**os.environ, "PROV_RUN_ID": run_id, store.INPUTS_ENV: str(inputs_file),
               store.OUTPUTS_ENV: str(outputs_file)}
        try:
            rc = subprocess.run(command, env=env).returncode
        except FileNotFoundError:
            rc = 127
        except KeyboardInterrupt:
            rc = -2
        record.inputs = list(dict.fromkeys(l for l in inputs_file.read_text().splitlines() if l))
        record.outputs = [line for line in outputs_file.read_text().splitlines() if line]

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
    args = parser.parse_args(argv)
    if args.cmd == "alias" and args.action != "show" and not args.target:
        parser.error(f"alias {args.action} needs a target")
    handlers = {"dataset": cmd_dataset, "alias": cmd_alias, "run": cmd_run, "publish": cmd_publish, "show": cmd_show, "ingest": cmd_ingest,
                "annotate": cmd_annotate, "catalog": cmd_catalog, "q": cmd_q}
    try:
        return handlers[args.cmd](args)
    except (config.ConfigError, gitsnap.SnapshotError, store.StoreError, aliases.AliasError,
            datasets.DatasetError, ValueError, catalog.duckdb.Error) as exc:
        print(f"prov: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
