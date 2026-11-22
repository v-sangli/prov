"""Lineage over the catalog's `nodes` and `edges` views.

An edge `src -> dst` means dst was made from (or rests on) src; the catalog bundles say which
edges exist and how each node is labelled. `trace` walks upstream, `uses` downstream; a node's
neighbours come in `ord`, then ID order. Each node appears once; repeats are shown as `(see above)`.
"""

from prov.artifacts import aliases
from prov.storage import catalog


def _walk(ctx, ref: str, sql: str) -> list[tuple[int, str, str]]:
    id_ = aliases.resolve(ctx, ref)
    with catalog.connect(ctx) as con:
        labels = dict(con.execute("SELECT id, label FROM nodes").fetchall())
        step: dict[str, list[str]] = {}
        for node, nxt in con.execute(sql).fetchall():
            step.setdefault(node, []).append(nxt)
    out, seen = [], set()

    def visit(node: str, depth: int) -> None:
        if node in seen:
            out.append((depth, node, f"{node}  (see above)"))
            return
        seen.add(node)
        out.append((depth, node, labels.get(node, f"{node}  (missing)")))
        for nxt in step.get(node, []):
            visit(nxt, depth + 1)
    visit(id_, 0)
    return out


def trace(ctx, ref: str) -> list[tuple[int, str, str]]:
    """Upstream: [(depth, id, description)]."""
    return _walk(ctx, ref, "SELECT dst, src FROM edges ORDER BY ord, src")


def uses(ctx, ref: str) -> list[tuple[int, str, str]]:
    """Downstream: [(depth, id, description)]."""
    return _walk(ctx, ref, "SELECT src, dst FROM edges ORDER BY ord, dst")
