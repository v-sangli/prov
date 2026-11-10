"""`prov` command line.

    prov run [--kind K] [--tag key=value ...] [--notes TEXT] -- <command> [args...]

Snapshots every repo in prov.toml, runs the command with PROV_RUN_ID set, writes
<registry>/records/runs/<run_id>.yaml (status `running` at start, final at exit), commits it in the
registry repo, and exits with the command's exit code.
"""

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from prov import config, gitsnap
from prov.ids import new_id
from prov.records import Env, RunRecord

KINDS = ["collect", "export", "train", "eval", "analysis", "other"]


def _env() -> Env:
    gpus = []
    if shutil.which("nvidia-smi"):
        p = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True)
        gpus = [g.strip() for g in p.stdout.splitlines() if g.strip()] if p.returncode == 0 else []
    return Env(python=platform.python_version(), platform=platform.platform(), gpu=gpus)


def _write(record: RunRecord, registry: Path) -> Path:
    path = registry / "records" / "runs" / f"{record.id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(record.to_yaml())
    tmp.replace(path)
    return path


def _commit_registry(registry: Path, path: Path, message: str) -> None:
    if not (registry / ".git").exists():
        return
    env = {**os.environ, **gitsnap._IDENTITY}
    rel = str(path.relative_to(registry))
    subprocess.run(["git", "-C", str(registry), "add", "--", rel], check=True, env=env)
    subprocess.run(["git", "-C", str(registry), "commit", "-q", "-m", message, "--", rel],
                   check=True, env=env, capture_output=True)


def cmd_run(args: argparse.Namespace) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("prov run: no command given (prov run -- <command>)", file=sys.stderr)
        return 2
    machine = config.load_machine()
    project = config.load_project(Path.cwd())
    tags = dict(t.split("=", 1) for t in args.tag)

    run_id = new_id("run")
    code = [gitsnap.snapshot(repo, run_id) for repo in project.repos]
    record = RunRecord(
        id=run_id, kind=args.kind, project=project.project,
        started=datetime.now(timezone.utc), status="running", host=socket.gethostname(),
        cwd=str(Path.cwd()), command=command, code=code, env=_env(), tags=tags, notes=args.notes,
    )
    path = _write(record, machine.registry)
    for c in code:
        if c.dirty:
            print(f"prov: {c.repo} is dirty; snapshot {c.snapshot[:10]} at {c.ref}", file=sys.stderr)
        if not c.pushed:
            print(f"prov: {c.repo}: {c.ref} not pushed (no origin or push failed)", file=sys.stderr)
    print(f"prov: {run_id}", file=sys.stderr)

    try:
        rc = subprocess.run(command, env={**os.environ, "PROV_RUN_ID": run_id}).returncode
    except FileNotFoundError:
        rc = 127
    except KeyboardInterrupt:
        rc = -2

    record.finished = datetime.now(timezone.utc)
    record.exit_code = rc
    record.status = "ok" if rc == 0 else ("killed" if rc < 0 else "failed")
    path = _write(record, machine.registry)
    _commit_registry(machine.registry, path, f"run {run_id} {record.status}")
    return rc if rc >= 0 else 128 - rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prov")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run a command and record it")
    run.add_argument("--kind", choices=KINDS, default="other")
    run.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    run.add_argument("--notes")
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "run":
            return cmd_run(args)
    except (config.ConfigError, gitsnap.SnapshotError) as exc:
        print(f"prov: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
