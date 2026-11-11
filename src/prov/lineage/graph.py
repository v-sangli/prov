"""Lineage over the catalog.

Edges: artifact <- the run that produced it; run <- its inputs; dataset <- its parent dataset and
the sessions of its episodes; session <- its producing run. `trace` walks upstream, `uses`
downstream. Each node appears once; repeats are shown as `(see above)`.
"""

from prov.artifacts import aliases
from prov.storage import catalog


def _describe(con, id_: str) -> str:
    if id_.startswith("run_"):
        row = con.execute("SELECT kind, project, status FROM runs WHERE id = ?", [id_]).fetchone()
        code = con.execute("SELECT repo, left(base, 10), dirty FROM run_code WHERE run = ? ORDER BY repo",
                           [id_]).fetchall()
        commits = ", ".join(f"{r}@{b}{' dirty' if d else ''}" for r, b, d in code)
        return f"{id_}  {row[0]} run, {row[1]}, {row[2]} [{commits}]" if row else f"{id_}  (missing)"
    row = con.execute("SELECT kind, meta->>'alias' FROM artifacts WHERE id = ?", [id_]).fetchone()
    if not row:
        return f"{id_}  (missing)"
    names = [r for (r,) in con.execute("SELECT ref FROM aliases WHERE id = ? ORDER BY ref", [id_]).fetchall()]
    label = f"  {' '.join(names)}" if names else ""
    extra = ""
    if row[0] == "dataset":
        n, s = con.execute("SELECT count(*), count(DISTINCT e.session) FROM dataset_members m "
                           "JOIN episodes e ON e.id = m.episode WHERE m.dataset = ?", [id_]).fetchone()
        extra = f", {n} episodes in {s} sessions"
    elif row[0] == "session":
        extra = f", {con.execute('SELECT count(*) FROM episodes WHERE session = ?', [id_]).fetchone()[0]} episodes"
    return f"{id_}{label}  {row[0]}{extra}"


def _upstream(con, id_: str) -> list[str]:
    if id_.startswith("run_"):
        return [a for (a,) in con.execute("SELECT artifact FROM run_inputs WHERE run = ? ORDER BY artifact", [id_]).fetchall()]
    out = [r for (r,) in con.execute("SELECT produced_by FROM artifacts WHERE id = ? AND produced_by IS NOT NULL", [id_]).fetchall()]
    out += [p for (p,) in con.execute("SELECT meta->>'parent' FROM artifacts WHERE id = ? AND kind = 'dataset' "
                                      "AND meta->>'parent' IS NOT NULL", [id_]).fetchall()]
    out += [s for (s,) in con.execute("SELECT DISTINCT e.session FROM dataset_members m JOIN episodes e ON e.id = m.episode "
                                      "WHERE m.dataset = ? ORDER BY 1", [id_]).fetchall()]
    return out


def _downstream(con, id_: str) -> list[str]:
    if id_.startswith("run_"):
        return [a for (a,) in con.execute("SELECT artifact FROM run_outputs WHERE run = ? ORDER BY artifact", [id_]).fetchall()]
    out = [r for (r,) in con.execute("SELECT DISTINCT run FROM run_inputs WHERE artifact = ? ORDER BY run", [id_]).fetchall()]
    out += [d for (d,) in con.execute("SELECT id FROM artifacts WHERE kind = 'dataset' AND meta->>'parent' = ? ORDER BY id", [id_]).fetchall()]
    out += [d for (d,) in con.execute("SELECT DISTINCT m.dataset FROM dataset_members m JOIN episodes e ON e.id = m.episode "
                                      "WHERE e.session = ? ORDER BY 1", [id_]).fetchall()]
    return out


def _walk(ctx, ref: str, step) -> list[tuple[int, str, str]]:
    id_ = aliases.resolve(ctx, ref)
    out, seen = [], set()
    with catalog.connect(ctx) as con:
        def visit(node: str, depth: int) -> None:
            if node in seen:
                out.append((depth, node, f"{node}  (see above)"))
                return
            seen.add(node)
            out.append((depth, node, _describe(con, node)))
            for nxt in step(con, node):
                visit(nxt, depth + 1)
        visit(id_, 0)
    return out


def trace(ctx, ref: str) -> list[tuple[int, str, str]]:
    """Upstream: [(depth, id, description)]."""
    return _walk(ctx, ref, _upstream)


def uses(ctx, ref: str) -> list[tuple[int, str, str]]:
    """Downstream: [(depth, id, description)]."""
    return _walk(ctx, ref, _downstream)
