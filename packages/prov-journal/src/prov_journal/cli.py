"""`prov-journal` command line.

    prov-journal init
        Add the journal to the current prov project: journal/ skeleton, journal/media link into
        the store, the .gitignore lines. Never overwrites.

    prov-journal new <topic> [--continues <doc>]   start today's doc from the template
    prov-journal lint                              check frontmatter, IDs, images, links, NOW.md
    prov-journal index                             rebuild journal/INDEX.md (docs by date and status)
    prov-journal register                          register every dated doc as a prov doc; prints each ID

    prov-journal site build [<vault dir>] [--name N]
        Build a Markdown vault (default: this project's journal) into a static site with Quartz.
    prov-journal site serve [--host 127.0.0.1|<addr>|tailscale] [--port 8090] [--rebuild-every 300]
        Serve every built site, with /<site>/media/ answered read-only from the store.
"""

import argparse
import sys
from pathlib import Path

import duckdb

from prov.core import log
from prov.core.context import Context, load_project
from prov.core.errors import ProvError
from prov.docs import register
from prov.wiring import extensions
from prov_journal import docs
from prov_journal.lint import lint
from prov_journal.project import init_journal
from prov_journal.site import build, server


def cmd_init(args, get_ctx) -> int:
    made = init_journal(get_ctx(), Path.cwd())
    print("\n".join(made) if made else "nothing to do: already set up")
    return 0


def cmd_new(args, get_ctx) -> int:
    print(docs.new_doc(args.topic, continues=args.continues))
    return 0


def cmd_index(args, get_ctx) -> int:
    print(docs.index(docs.journal_root()))
    return 0


def cmd_register(args, get_ctx) -> int:
    for record in register.register(get_ctx(), [d.path for d in docs.docs(docs.journal_root())]):
        print(record.id)
    return 0


def cmd_lint(args, get_ctx) -> int:
    problems = lint(get_ctx(), docs.journal_root())
    print("\n".join(problems) if problems else "journal OK")
    return 1 if problems else 0


def cmd_site(args, get_ctx) -> int:
    ctx = get_ctx()
    if args.action == "serve":
        server.serve(ctx, args.host, args.port, args.rebuild_every)
        return 0
    if args.source:
        source, name = Path(args.source), args.name or Path(args.source).resolve().name
    else:
        project = load_project(Path.cwd())
        source, name = project.root / "journal", args.name or project.project
    print(build.build(ctx, source, name))
    return 0


def main(argv: list[str] | None = None) -> int:
    ext = extensions()
    parser = argparse.ArgumentParser(prog="prov-journal")
    noise = parser.add_mutually_exclusive_group()
    noise.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    noise.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="add the journal to this prov project").set_defaults(func=cmd_init)
    new = sub.add_parser("new", help="start today's doc from the template")
    new.add_argument("topic")
    new.add_argument("--continues", help="doc folder this one continues (relative to journal/)")
    new.set_defaults(func=cmd_new)
    sub.add_parser("lint", help="check the journal").set_defaults(func=cmd_lint)
    sub.add_parser("index", help="rebuild journal/INDEX.md").set_defaults(func=cmd_index)
    sub.add_parser("register", help="register every dated doc as a prov doc").set_defaults(func=cmd_register)
    st = sub.add_parser("site", help="build and serve journal / handbook sites")
    st.add_argument("action", choices=["build", "serve"])
    st.add_argument("source", nargs="?", help="vault folder to build (default: this project's journal)")
    st.add_argument("--name", help="site name (default: project name or folder name)")
    st.add_argument("--host", default="127.0.0.1", help="address to bind, or `tailscale`")
    st.add_argument("--port", type=int, default=8090)
    st.add_argument("--rebuild-every", type=int, default=300, help="seconds; 0 disables")
    st.set_defaults(func=cmd_site)
    args = parser.parse_args(argv)
    log.set_verbosity(1 if args.verbose else -1 if args.quiet else 0)
    try:
        return args.func(args, lambda: Context.load(ext))
    except (ProvError, ValueError, duckdb.Error) as exc:   # ValueError: pydantic validation
        print(f"prov-journal: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
