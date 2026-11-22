"""Each extension point takes a new entry without touching the code that uses it."""

import dataclasses
import json
from pathlib import Path

from prov.core.extensions import CatalogTables, IngestFormat, LintCheck
from prov.episodes.ingest import ingest
from prov.journal.docs import new_doc
from prov.journal.lint import lint
from prov.journal.project import init_project
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


def test_new_lint_check(ctx, tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    monkeypatch.chdir(root)
    init_project(ctx, root, "p")
    new_doc("first")
    no_todo = LintCheck("no_todo", lambda view: [f"{d.rel}:1: TODO left" for d in view.docs if "TODO" in d.text])
    ctx = _with(ctx, lint_checks=[*ctx.ext.lint_checks, no_todo])
    assert lint(ctx, root / "journal") == []
    doc = [d for d in (root / "journal").rglob("README.md") if "first" in str(d)][0]
    doc.write_text(doc.read_text() + "\nTODO\n")
    assert [p.split(": ", 1)[1] for p in lint(ctx, root / "journal")] == ["TODO left"]


def test_new_catalog_table(ctx):
    extra = CatalogTables("notes", "CREATE TABLE notes (k VARCHAR);", lambda c: {"notes": [("a",), ("b",)]})
    ctx = _with(ctx, tables=[*ctx.ext.tables, extra])
    catalog.rebuild(ctx)
    with catalog.connect(ctx) as con:
        assert con.execute("SELECT k FROM notes ORDER BY k").fetchall() == [("a",), ("b",)]
        assert con.execute("SELECT count(*) FROM runs").fetchone() == (0,)
