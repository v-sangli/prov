"""prov init, journal.

    prov init <project>
        Make the current repo a prov project: prov.toml, journal/ skeleton, journal/media link into
        the store, agent skills linked into .claude/skills/. Never overwrites.

    prov journal new <topic> [--continues <doc>]   start today's doc from the template
    prov journal lint                              check frontmatter, IDs, images, links, NOW.md
    prov journal index                             rebuild journal/INDEX.md (docs by date and status)
"""

from pathlib import Path

from prov.core.errors import JournalError
from prov.journal import docs
from prov.journal.lint import lint
from prov.journal.project import init_project


def cmd_init(args, get_ctx) -> int:
    made = init_project(get_ctx(), Path.cwd(), args.project)
    print("\n".join(made) if made else "nothing to do: already set up")
    return 0


def cmd_journal(args, get_ctx) -> int:
    if args.action == "new":
        if not args.topic:
            raise JournalError("journal new needs a topic")
        print(docs.new_doc(args.topic, continues=args.continues))
        return 0
    root = docs.journal_root()
    if args.action == "index":
        print(docs.index(root))
        return 0
    problems = lint(get_ctx(), root)
    print("\n".join(problems) if problems else "journal OK")
    return 1 if problems else 0


def register(sub, ext) -> None:
    init = sub.add_parser("init", help="make this repo a prov project")
    init.add_argument("project")
    init.set_defaults(func=cmd_init)
    jr = sub.add_parser("journal", help="project journal")
    jr.add_argument("action", choices=["new", "lint", "index"])
    jr.add_argument("topic", nargs="?")
    jr.add_argument("--continues", help="doc folder this one continues (relative to journal/)")
    jr.set_defaults(func=cmd_journal)
