"""prov doc register.

    prov doc register <path> [<path> ...]
        Register Markdown docs inside a git repo: give each a doc_ ID (written as `id:` in its
        frontmatter) and record what it cites; prints each ID. Every cited ID or alias must be in
        the registry. A file in no git repo is refused: fold it into a journal first.
"""

from pathlib import Path

from prov.docs import register as docs


def cmd_doc(args, get_ctx) -> int:
    for record in docs.register(get_ctx(), [Path(p) for p in args.paths]):
        print(record.id)
    return 0


def register(sub, ext) -> None:
    doc = sub.add_parser("doc", help="docs that cite prov IDs")
    doc.add_argument("action", choices=["register"])
    doc.add_argument("paths", nargs="+")
    doc.set_defaults(func=cmd_doc)
