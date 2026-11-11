import sys
from pathlib import Path

import pytest
import wandb

from conftest import git
from prov.artifacts import aliases
from prov.lineage import graph as lineage
from prov.storage import catalog
from prov.cli import main
from prov.wiring import context
from prov.artifacts.publish import load, publish
from prov.datasets.freeze import freeze
from prov.runs.schema import RunRecord
from test_episodes import make_lerobot


def _project(repo: Path, monkeypatch) -> None:
    (repo / "prov.toml").write_text('project = "demo"\n')
    git(repo, "add", "prov.toml")
    git(repo, "commit", "-q", "-m", "prov.toml")
    monkeypatch.chdir(repo)


def _run(kind: str, code: str) -> RunRecord:
    assert main(["run", "--kind", kind, "--", sys.executable, "-c", code]) == 0
    cfg_reg = context().registry
    runs = sorted((cfg_reg / "records" / "runs").glob("*.yaml"))
    return RunRecord.from_yaml(runs[-1])


@pytest.fixture
def chain(repo, registry, monkeypatch, tmp_path, ctx):
    """collect -> dataset -> train -> eval -> analysis, each a prov run."""
    _project(repo, monkeypatch)
    src = make_lerobot(tmp_path / "teleop", [5, 6, 7, 8])
    collect = _run("collect", f"import prov; from prov.episodes.ingest import ingest; ingest(prov.context(), {str(src)!r})")
    freeze(ctx, "cube", query="SELECT id FROM episodes", holdout=0.25)

    spec = tmp_path / "bench.yaml"
    spec.write_text("tasks: [cube]\nepisodes: holdout\nmetrics: [success_rate]\n")
    publish(ctx, spec, "benchmark", alias="bench:cube-holdout/1")

    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "model.safetensors").write_bytes(b"w")
    train = _run("train", "import prov; prov.load('ds:cube-train/1'); "
                          f"prov.publish({str(ckpt)!r}, 'checkpoint', alias='model:cube/0.1')")
    res = tmp_path / "eval.jsonl"
    res.write_text('{"ep": 0, "success": true}\n')
    evaluate = _run("eval", "import prov; prov.load('model:cube/0.1'); prov.load('bench:cube-holdout/1'); "
                            f"prov.publish({str(res)!r}, 'result'); prov.summary(success_rate=0.5, n=2); "
                            "prov.summary(success_rate=0.75)")
    fig = tmp_path / "fig.png"
    fig.write_bytes(b"png")
    analysis = _run("analysis", f"import prov; prov.load({evaluate.outputs[0]!r}); "
                                f"prov.publish({str(fig)!r}, 'figure')")
    return {"collect": collect, "train": train, "eval": evaluate, "analysis": analysis}


def test_summary_recorded_later_values_win(chain, ctx):
    assert chain["eval"].summary == {"success_rate": 0.75, "n": 2}
    with catalog.connect(ctx) as con:
        rows = con.execute("""
            SELECT r.id, s.value FROM runs r
            JOIN run_inputs b ON b.run = r.id
            JOIN aliases al ON al.id = b.artifact AND al.ref = 'bench:cube-holdout/1'
            JOIN run_summary s ON s.run = r.id AND s.key = 'success_rate'
            WHERE r.kind = 'eval'""").fetchall()
    assert rows == [(chain["eval"].id, 0.75)]


def test_trace_figure_reaches_episodes_and_commits(chain, repo, ctx):
    fig = chain["analysis"].outputs[0]
    nodes = lineage.trace(ctx, fig)
    ids = [n for _, n, _ in nodes]
    session = load(ctx, chain["collect"].outputs[0]).id
    for expected in (fig, chain["analysis"].id, chain["eval"].id, chain["train"].id,
                     aliases.resolve(ctx, "model:cube/0.1"), aliases.resolve(ctx, "ds:cube-train/1"),
                     aliases.resolve(ctx, "bench:cube-holdout/1"), session, chain["collect"].id):
        assert expected in ids
    depth = {n: d for d, n, _ in nodes}
    assert depth[fig] == 0 and depth[chain["collect"].id] > depth[session] > depth[chain["train"].id]
    text = "\n".join(t for _, _, t in nodes)
    assert f"proj@{git(repo, 'rev-parse', 'HEAD')[:10]}" in text
    assert "ds:cube-train/1  dataset, 3 episodes in 1 sessions" in text


def test_uses_session_reaches_figure(chain, ctx):
    session = chain["collect"].outputs[0]
    ids = [n for _, n, _ in lineage.uses(ctx, session)]
    assert chain["analysis"].outputs[0] in ids and aliases.resolve(ctx, "ds:cube/1") in ids


def test_cli_trace(chain, capsys, ctx):
    assert main(["trace", "model:cube/0.1"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(aliases.resolve(ctx, "model:cube/0.1")) and out[1].startswith("<- run_")


def test_summary_outside_run_warns(registry, capsys):
    from prov import summary
    summary(x=1)
    assert "not recorded" in capsys.readouterr().err


class _FakeRun:
    def __init__(self):
        self.used, self.logged, self.summary = [], [], {}

    def use_artifact(self, art):
        self.used.append(art)

    def log_artifact(self, art):
        self.logged.append(art)


def test_wandb_reference_artifacts_hold_paths_only(registry, tmp_path, monkeypatch, ctx):
    src = make_lerobot(tmp_path / "s", [5, 5])
    from prov.episodes.ingest import ingest
    ingest(ctx, src)
    ds = freeze(ctx, "cube", query="SELECT id FROM episodes")["all"]
    fake = _FakeRun()
    monkeypatch.setattr(wandb, "run", fake)

    import prov
    prov.load("ds:cube/1")
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "w.bin").write_bytes(b"0" * 1000)
    rec = prov.publish(ckpt, "checkpoint", alias="model:cube/0.1")

    from wandb.sdk.lib.hashutil import md5_string
    [used], [logged] = fake.used, fake.logged
    assert (used.type, used.name, used.metadata["prov_id"]) == ("dataset", "cube", ds.id)
    assert logged.type == "checkpoint" and logged.metadata["prov_alias"] == "model:cube/0.1"
    assert logged.metadata["uri"] == rec.uri
    for art, rec_id, kind in ((used, ds.id, "dataset"), (logged, rec.id, "checkpoint")):
        target = registry / "records" / "artifacts" / kind / f"{rec_id}.yaml"
        [entry] = art.manifest.entries.values()          # one entry, however big the folder
        assert entry.ref == f"file://{target}"
        assert entry.digest == md5_string(target.resolve().as_uri())   # path hashed, contents not read


def test_wandb_failures_never_break_a_run(registry, tmp_path, monkeypatch, capsys, ctx):
    class Broken(_FakeRun):
        def log_artifact(self, art):
            raise RuntimeError("offline")
    monkeypatch.setattr(wandb, "run", Broken())
    f = tmp_path / "r.json"
    f.write_text("{}")
    publish(ctx, f, "result")
    assert "W&B log_artifact failed" in capsys.readouterr().err


def test_wandb_init_offline_records_run_path(repo, registry, monkeypatch, tmp_path, ctx):
    _project(repo, monkeypatch)
    monkeypatch.setenv("WANDB_MODE", "offline")
    monkeypatch.setenv("WANDB_DIR", str(tmp_path))
    monkeypatch.setenv("WANDB_SILENT", "true")
    f = tmp_path / "r.json"
    f.write_text("{}")
    rec = _run("eval", "import prov; run = prov.wandb_init(); "
                       f"prov.publish({str(f)!r}, 'result'); prov.summary(score=1.0); run.finish()")
    assert rec.wandb and rec.wandb.split("/")[-2] == "demo"
    assert rec.summary == {"score": 1.0} and len(rec.outputs) == 1
