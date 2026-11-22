"""prov dataset freeze.

    prov dataset freeze <name> (--query SQL | --episodes FILE) [--parent REF] [--notes T]
                               [--holdout F [--seed N] [--by episode|session]]
        Freeze ds:<name>/<next> from episode IDs; with --holdout also <name>-train and <name>-holdout.
"""

from pathlib import Path

from prov.datasets.freeze import freeze
from prov.datasets.split import BY


def cmd_dataset(args, get_ctx) -> int:
    eps = Path(args.episodes).read_text().split() if args.episodes else None
    out = freeze(get_ctx(), args.name, episodes=eps, query=args.query, parent=args.parent, notes=args.notes,
                 holdout=args.holdout, seed=args.seed, by=args.by)
    for rec in out.values():
        print(f"{rec.meta['alias']}\t{rec.id}\t{rec.meta['episodes']} episodes\t{rec.meta['sessions']} sessions")
    return 0


def register(sub, ext) -> None:
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
    ds.add_argument("--by", choices=list(BY), default="episode")
    ds.set_defaults(func=cmd_dataset)
