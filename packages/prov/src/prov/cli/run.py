"""prov run, prov rerun.

    prov run [--kind K] [--tag key=value ...] [--notes TEXT] -- <command> [args...]
        Snapshot every repo in prov.toml, run the command with PROV_RUN_ID set, write
        <registry>/records/runs/<run_id>.yaml (status `running` at start, final at exit), commit it,
        and exit with the command's exit code. Artifacts published by the command become its outputs.

    prov rerun <run_id>
        Run the same command again on the recorded code snapshot (git worktrees), as a new run
        tagged rerun_of=<run_id>.
"""

import argparse
import sys
from pathlib import Path

from prov.cli.common import pairs
from prov.core.context import load_project
from prov.runs import rerun, wrapper
from prov.runs.schema import KINDS


def cmd_run(args, get_ctx) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("prov run: no command given (prov run -- <command>)", file=sys.stderr)
        return 2
    ctx = get_ctx()
    project = load_project(Path.cwd())
    return wrapper.run(ctx, project, command, kind=args.kind, tags=pairs(args.tag), notes=args.notes)


def cmd_rerun(args, get_ctx) -> int:
    return rerun.rerun(get_ctx(), args.run_id)


def register(sub, ext) -> None:
    run = sub.add_parser("run", help="run a command and record it")
    run.add_argument("--kind", choices=KINDS, default="other")
    run.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    run.add_argument("--notes")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)
    rr = sub.add_parser("rerun", help="re-run a recorded run on its code snapshot")
    rr.add_argument("run_id")
    rr.set_defaults(func=cmd_rerun)
