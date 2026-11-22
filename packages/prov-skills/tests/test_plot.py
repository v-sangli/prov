import sys
from pathlib import Path

import pytest

from conftest import git
from prov.artifacts import aliases
from prov.cli import main
from prov.artifacts.publish import load, publish
from prov.runs.schema import RunRecord
from prov.storage.store import resolve

pytest.importorskip("matplotlib")

SCRIPT = '''"""Plot success per episode from an eval result."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import prov
from prov_skills import plot

TITLE = "{title}"
rec = prov.load("res:evals/1")
rows = [json.loads(line) for line in open(prov.path(rec))]
with plot.style():
    fig, ax = plt.subplots()
    ax.plot([r["ep"] for r in rows], [r["err"] for r in rows], marker="o", label="policy A")
    ax.plot([r["ep"] for r in rows], [r["err"] * 0.8 for r in rows], marker="o", label="policy B")
    ax.set_title(TITLE)
    ax.set_xlabel("episode")
    ax.set_ylabel("error (mm)")
    ax.legend()
    plot.save_figure(fig, "errors", caption="Error per episode")
'''


@pytest.fixture
def analysis_repo(repo, registry, monkeypatch, tmp_path, ctx):
    (repo / "prov.toml").write_text('project = "demo"\n')
    (repo / "analysis").mkdir()
    (repo / "analysis" / "plot.py").write_text(SCRIPT.format(title="errors v1"))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "analysis")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("MPLBACKEND", "Agg")
    res = tmp_path / "evals.jsonl"
    res.write_text("".join(f'{{"ep": {i}, "err": {e}}}\n' for i, e in enumerate([12.0, 9.5, 11.2, 8.1])))
    publish(ctx, res, "result", alias="res:evals/1")
    return repo


def _runs(registry: Path) -> list[RunRecord]:
    return sorted((RunRecord.from_yaml(p) for p in (registry / "records" / "runs").glob("*.yaml")),
                  key=lambda r: r.started)


def _figure_bytes(ctx, fig_id: str) -> dict[str, bytes]:
    rec = load(ctx, fig_id)
    folder = resolve(ctx, rec.uri)
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def test_style_applies_palette_and_restores():
    import matplotlib as mpl
    from prov_skills import plot
    before = mpl.rcParams["axes.prop_cycle"]
    with plot.style():
        assert mpl.rcParams["axes.prop_cycle"].by_key()["color"] == plot.CATEGORICAL
        assert mpl.rcParams["axes.facecolor"] == plot.SURFACE
    assert mpl.rcParams["axes.prop_cycle"] == before


def test_save_figure_and_journal_copy(analysis_repo, registry, tmp_path, ctx):
    assert main(["run", "--kind", "analysis", "--", sys.executable, str(analysis_repo / "analysis" / "plot.py")]) == 0
    [run] = _runs(registry)
    [fig_id] = run.outputs
    assert run.inputs == [aliases.resolve(ctx, "res:evals/1")]
    rec = load(ctx, fig_id)
    assert rec.kind == "figure" and rec.meta["caption"] == "Error per episode"
    assert set(_figure_bytes(ctx, fig_id)) == {"errors.png", "errors.pdf"}

    from prov_skills import plot
    doc = tmp_path / "journal" / "2026-11-10-errors"
    doc.mkdir(parents=True)
    copy = plot.to_journal(rec, doc)
    assert copy.name == f"{fig_id}.png" and copy.read_bytes() == _figure_bytes(ctx, fig_id)["errors.png"]
