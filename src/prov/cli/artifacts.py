"""prov publish, show, alias.

    prov publish <path> --kind K [--meta key=value ...] [--copy] [--alias kind:name/version]
        Move (or copy) a file or folder into the store under a new ID, make it read-only, record it.

    prov show <id or alias>
        Print a run or artifact record (and an artifact's store path).

    prov alias set <kind:name/version> <ID>        a version: set once, never changes
    prov alias label <kind:name@label> <kind:name/version>   move a label
    prov alias show <ID or alias>                   print what it resolves to
"""

from pathlib import Path

from prov.artifacts import aliases, publish
from prov.cli.common import pairs
from prov.core import layout
from prov.core.errors import ConfigError
from prov.core.ids import kind_of
from prov.runs import records


def cmd_publish(args, get_ctx) -> int:
    record = publish.publish(get_ctx(), Path(args.path), args.kind, meta=pairs(args.meta), copy=args.copy,
                             alias=args.alias)
    print(record.id)
    return 0


def cmd_show(args, get_ctx) -> int:
    ctx = get_ctx()
    id_ = aliases.resolve(ctx, args.id)
    if kind_of(id_) == "run":
        records.load(ctx, id_)                          # raises when there is no record
        print(records.path(ctx, id_).read_text(), end="")
        return 0
    record = publish.load(ctx, id_)
    print(record.to_yaml(), end="")
    if record.uri:
        print(f"# path: {publish.path(ctx, record)}")
    return 0


def cmd_alias(args, get_ctx) -> int:
    if args.action != "show" and not args.target:
        raise ConfigError(f"alias {args.action} needs a target")
    ctx = get_ctx()
    if args.action == "set":
        aliases.set_version(ctx, args.ref, args.target)
    elif args.action == "label":
        aliases.set_label(ctx, args.ref, args.target)
    else:
        print(aliases.resolve(ctx, args.ref))
    return 0


def register(sub, ext) -> None:
    pub = sub.add_parser("publish", help="move a file or folder into the store and record it")
    pub.add_argument("path")
    pub.add_argument("--kind", required=True, choices=sorted(layout.KIND_DIRS))
    pub.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE")
    pub.add_argument("--copy", action="store_true", help="copy instead of move")
    pub.add_argument("--alias", help="also name it kind:name/version")
    pub.set_defaults(func=cmd_publish)
    show = sub.add_parser("show", help="print a run or artifact record")
    show.add_argument("id")
    show.set_defaults(func=cmd_show)
    al = sub.add_parser("alias", help="readable names for IDs")
    al.add_argument("action", choices=["set", "label", "show"])
    al.add_argument("ref")
    al.add_argument("target", nargs="?")
    al.set_defaults(func=cmd_alias)
