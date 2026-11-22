"""`prov` command line: the parser root, verbosity, error handling and the list of command groups.

Run `prov --help` or `prov <command> --help`; each group's module docstring documents its commands.
"""

import argparse
import sys

import duckdb

from prov.cli import artifacts, datasets, episodes, init, query, run
from prov.core import log
from prov.core.context import Context
from prov.core.errors import ProvError
from prov.wiring import extensions

GROUPS = [run, artifacts, episodes, query, datasets, init]


def main(argv: list[str] | None = None) -> int:
    ext = extensions()
    parser = argparse.ArgumentParser(prog="prov")
    noise = parser.add_mutually_exclusive_group()
    noise.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    noise.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for group in GROUPS:
        group.register(sub, ext)
    args = parser.parse_args(argv)
    log.set_verbosity(1 if args.verbose else -1 if args.quiet else 0)
    try:
        return args.func(args, lambda: Context.load(ext))
    except (ProvError, ValueError, duckdb.Error) as exc:   # ValueError: pydantic validation
        print(f"prov: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
