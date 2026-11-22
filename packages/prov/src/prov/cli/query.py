"""prov catalog rebuild, q, trace, uses.

    prov catalog rebuild           rebuild the DuckDB catalog from the registry
    prov q "<sql>"                 query the catalog (rebuilt first if the registry changed);
                                   tab-separated, with a header
    prov trace <ID or alias>       upstream lineage: what it was made from, down to sessions and commits
    prov uses <ID or alias>        downstream: every run, artifact and dataset built on it
"""

from prov.lineage import graph
from prov.storage import catalog


def cmd_catalog(args, get_ctx) -> int:
    print(catalog.rebuild(get_ctx()))
    return 0


def cmd_q(args, get_ctx) -> int:
    with catalog.connect(get_ctx()) as con:
        cur = con.execute(args.sql)
        print("\t".join(d[0] for d in cur.description))
        for row in cur.fetchall():
            print("\t".join("" if v is None else str(v) for v in row))
    return 0


def cmd_lineage(args, get_ctx) -> int:
    walk = graph.trace if args.cmd == "trace" else graph.uses
    arrow = "<- " if args.cmd == "trace" else "-> "
    for depth, _, text in walk(get_ctx(), args.ref):
        print(("  " * (depth - 1) + arrow if depth else "") + text)
    return 0


def register(sub, ext) -> None:
    cat = sub.add_parser("catalog", help="catalog maintenance")
    cat.add_argument("action", choices=["rebuild"])
    cat.set_defaults(func=cmd_catalog)
    q = sub.add_parser("q", help="query the catalog with SQL")
    q.add_argument("sql")
    q.set_defaults(func=cmd_q)
    for name, help_ in (("trace", "upstream lineage"), ("uses", "downstream lineage")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("ref")
        p.set_defaults(func=cmd_lineage)
