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
