"""Each extension point takes a new entry without touching the code that uses it."""

import dataclasses
import json
from pathlib import Path

from prov.core.extensions import CatalogTables, IngestFormat
from prov.episodes.ingest import ingest
from prov.storage import catalog


def _with(ctx, **changes):
    return dataclasses.replace(ctx, ext=dataclasses.replace(ctx.ext, **changes))


def test_new_ingest_format(ctx, tmp_path):
    def read(root: Path):
        rows = json.loads((root / "takes.json").read_text())
        return {"format": "takes", "fps": 10}, [{"episode_index": i, "length": n} for i, n in enumerate(rows)]

    src = tmp_path / "rec"
    src.mkdir()
    (src / "takes.json").write_text("[30, 40]")
    ctx = _with(ctx, formats={**ctx.ext.formats, "takes": IngestFormat("takes", read)})
    session, eps = ingest(ctx, src, format="takes")
    assert session.meta["format"] == "takes"
    assert [(e.episode_index, e.length, e.duration_s) for e in eps] == [(0, 30, 3.0), (1, 40, 4.0)]


def test_new_catalog_table(ctx):
    extra = CatalogTables("notes", "CREATE TABLE notes (k VARCHAR);", lambda c: {"notes": [("a",), ("b",)]})
    ctx = _with(ctx, tables=[*ctx.ext.tables, extra])
    catalog.rebuild(ctx)
    with catalog.connect(ctx) as con:
        assert con.execute("SELECT k FROM notes ORDER BY k").fetchall() == [("a",), ("b",)]
        assert con.execute("SELECT count(*) FROM runs").fetchone() == (0,)


def test_new_catalog_edges_join_lineage(ctx):
    from prov.lineage import graph
    a, b = "fig_" + "0" * 26, "fig_" + "1" * 26
    extra = CatalogTables("links", "CREATE TABLE links (src VARCHAR, dst VARCHAR);",
                          lambda c: {"links": [(a, b)]},
                          nodes=f"SELECT '{a}' AS id, 'A' AS label UNION ALL SELECT '{b}', 'B'",
                          edges="SELECT src, 'link' AS rel, dst FROM links")
    ctx = _with(ctx, tables=[*ctx.ext.tables, extra])
    catalog.rebuild(ctx)
    assert graph.trace(ctx, b) == [(0, b, "B"), (1, a, "A")]
    assert graph.uses(ctx, a) == [(0, a, "A"), (1, b, "B")]
    with catalog.connect(ctx) as con:
        assert con.execute("SELECT src, rel, dst FROM edges WHERE rel = 'link'").fetchall() == [(a, "link", b)]


def test_catalog_rebuilds_when_its_tables_change(ctx, registry):
    from conftest import git
    (registry / "x").write_text("x")
    git(registry, "add", "x")
    git(registry, "commit", "-q", "-m", "x")
    catalog.rebuild(ctx)                                   # built from the built-in tables
    extra = CatalogTables("notes", "CREATE TABLE notes (k VARCHAR);", lambda c: {"notes": [("a",)]})
    ctx = _with(ctx, tables=[*ctx.ext.tables, extra])      # same registry HEAD, new tables
    with catalog.connect(ctx) as con:
        assert con.execute("SELECT k FROM notes").fetchall() == [("a",)]
