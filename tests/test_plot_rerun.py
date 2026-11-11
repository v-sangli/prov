import sys
from pathlib import Path

import pytest

from conftest import git
from prov import aliases
from prov.cli import main
from prov.records import RunRecord
from prov.store import load, publish, resolve

pytest.importorskip("matplotlib")

SCRIPT = '''"""Plot success per episode from an eval result."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import prov
from prov import plot

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
def analysis_repo(repo, registry, monkeypatch, tmp_path):
    (repo / "prov.toml").write_text('project = "demo"\n')
    (repo / "analysis").mkdir()
    (repo / "analysis" / "plot.py").write_text(SCRIPT.format(title="errors v1"))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "analysis")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("MPLBACKEND", "Agg")
    res = tmp_path / "evals.jsonl"
    res.write_text("".join(f'{{"ep": {i}, "err": {e}}}\n' for i, e in enumerate([12.0, 9.5, 11.2, 8.1])))
    publish(res, "result", alias="res:evals/1")
    return repo


def _runs(registry: Path) -> list[RunRecord]:
    return sorted((RunRecord.from_yaml(p) for p in (registry / "records" / "runs").glob("*.yaml")),
                  key=lambda r: r.started)


def _figure_bytes(fig_id: str, store_root: Path) -> dict[str, bytes]:
    rec = load(fig_id)
    folder = resolve(rec.uri, store_root)
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def test_style_applies_palette_and_restores():
    import matplotlib as mpl
    from prov import plot
    before = mpl.rcParams["axes.prop_cycle"]
    with plot.style():
        assert mpl.rcParams["axes.prop_cycle"].by_key()["color"] == plot.CATEGORICAL
        assert mpl.rcParams["axes.facecolor"] == plot.SURFACE
    assert mpl.rcParams["axes.prop_cycle"] == before


def test_save_figure_and_journal_copy(analysis_repo, registry, tmp_path):
    assert main(["run", "--kind", "analysis", "--", sys.executable, str(analysis_repo / "analysis" / "plot.py")]) == 0
    [run] = _runs(registry)
    [fig_id] = run.outputs
    assert run.inputs == [aliases.resolve("res:evals/1")]
    rec = load(fig_id)
    assert rec.kind == "figure" and rec.meta["caption"] == "Error per episode"
    assert set(_figure_bytes(fig_id, tmp_path / "store")) == {"errors.png", "errors.pdf"}

    from prov import plot
    doc = tmp_path / "journal" / "2026-11-10-errors"
    doc.mkdir(parents=True)
    copy = plot.to_journal(rec, doc)
    assert copy.name == f"{fig_id}.png" and copy.read_bytes() == _figure_bytes(fig_id, tmp_path / "store")["errors.png"]


def test_rerun_reproduces_figure_byte_for_byte(analysis_repo, registry, tmp_path):
    main(["run", "--kind", "analysis", "--tag", "topic=errors", "--",
          sys.executable, str(analysis_repo / "analysis" / "plot.py")])
    [first] = _runs(registry)

    assert main(["rerun", first.id]) == 0
    second = _runs(registry)[-1]
    assert second.id != first.id and second.tags == {"rerun_of": first.id, "topic": "errors"}
    assert second.code[0].base == first.code[0].snapshot and not second.code[0].dirty
    assert _figure_bytes(second.outputs[0], tmp_path / "store") == _figure_bytes(first.outputs[0], tmp_path / "store")
    assert git(analysis_repo, "worktree", "list").count("\n") == 0          # worktree cleaned up


def test_rerun_uses_snapshot_not_current_code(analysis_repo, registry, tmp_path):
    script = analysis_repo / "analysis" / "plot.py"
    script.write_text(SCRIPT.format(title="uncommitted edit"))           # dirty run
    main(["run", "--kind", "analysis", "--", sys.executable, str(script)])
    [first] = _runs(registry)
    assert first.code[0].dirty

    script.write_text(SCRIPT.format(title="later edit"))                 # code moves on
    assert main(["rerun", first.id]) == 0
    second = _runs(registry)[-1]
    assert _figure_bytes(second.outputs[0], tmp_path / "store") == _figure_bytes(first.outputs[0], tmp_path / "store")
    assert "later edit" in script.read_text()                            # working tree untouched


def test_rerun_unknown(registry, capsys):
    assert main(["rerun", "run_00000000000000000000000000"]) == 2
    assert "no record" in capsys.readouterr().err
