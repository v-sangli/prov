import json
import sys
from pathlib import Path

import duckdb
import pytest

from conftest import git
from prov.storage import catalog
from prov.cli import main
from prov.artifacts.publish import publish
from prov.core.errors import StoreError
from prov.episodes.annotate import annotate
from prov.episodes.ingest import ingest, read_episodes
from prov.storage.store import resolve


def make_lerobot(root: Path, lengths: list[int], fps: int = 30, version: str = "v3.0",
                 task: str = "pick_cube") -> Path:
    (root / "meta").mkdir(parents=True)
    features = {"observation.images.wrist": {"dtype": "video"}, "observation.images.top": {"dtype": "video"},
                "action": {"dtype": "float32"}}
    (root / "meta" / "info.json").write_text(json.dumps({
        "codebase_version": version, "robot_type": "so101", "fps": fps, "features": features,
        "total_episodes": len(lengths), "total_frames": sum(lengths)}))
    rows = [{"episode_index": i, "length": n, "tasks": [task]} for i, n in enumerate(lengths)]
    if version.startswith("v3"):
        d = root / "meta" / "episodes" / "chunk-000"
        d.mkdir(parents=True)
        jl = root / "eps.jsonl"
        jl.write_text("".join(json.dumps(r) + "\n" for r in rows))
        duckdb.sql(f"COPY (SELECT * FROM read_json('{jl}')) TO '{d / 'file-000.parquet'}' (FORMAT parquet)")
        jl.unlink()
    else:
        (root / "meta" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return root


def test_ingest_v3_session(registry, tmp_path, ctx):
    src = make_lerobot(tmp_path / "in" / "teleop_a", [60, 90, 45])
    session, eps = ingest(ctx, src)

    assert session.id.startswith("ses_") and not src.exists()
    assert session.meta["fps"] == 30 and session.meta["robot_type"] == "so101"
    assert session.meta["cameras"] == ["observation.images.top", "observation.images.wrist"]
    assert [e.episode_index for e in eps] == [0, 1, 2]
    assert len({e.id for e in eps}) == 3 and all(e.id.startswith("ep_") for e in eps)
    assert [e.duration_s for e in eps] == [2.0, 3.0, 1.5]
    assert all(e.source.kind == "teleop" and e.tasks == ["pick_cube"] for e in eps)
    assert read_episodes(ctx, session.id) == eps
    assert git(registry, "log", "-1", "--format=%s") == f"ingest {session.id}: 3 episodes"
    assert git(registry, "status", "--porcelain") == ""


def test_ingest_v2_session(registry, tmp_path, ctx):
    _, eps = ingest(ctx, make_lerobot(tmp_path / "old", [10, 20], fps=10, version="v2.1"))
    assert [(e.episode_index, e.length, e.duration_s) for e in eps] == [(0, 10, 1.0), (1, 20, 2.0)]


def test_source_map_references_mcap(registry, tmp_path, ctx):
    src = make_lerobot(tmp_path / "export_1", [30, 30])
    smap = tmp_path / "sources.jsonl"
    smap.write_text("".join(json.dumps({"episode_index": i, "path": "/raw/take_07.mcap",
                                        "start_s": 10.0 * i, "end_s": 10.0 * i + 1}) + "\n" for i in range(2)))
    _, eps = ingest(ctx, src, source_map=smap)
    assert [(e.source.kind, e.source.path, e.source.start_s) for e in eps] == [
        ("mcap", "/raw/take_07.mcap", 0.0), ("mcap", "/raw/take_07.mcap", 10.0)]


def test_incomplete_source_map_moves_nothing(registry, tmp_path, ctx):
    src = make_lerobot(tmp_path / "export_2", [30, 30])
    smap = tmp_path / "sources.jsonl"
    smap.write_text(json.dumps({"episode_index": 0, "path": "/raw/a.mcap"}) + "\n")
    with pytest.raises(StoreError, match=r"no entry for episodes \[1\]"):
        ingest(ctx, src, source_map=smap)
    assert src.exists() and not (registry / "records" / "artifacts").exists()


def test_not_lerobot_moves_nothing(registry, tmp_path, ctx):
    d = tmp_path / "junk"
    d.mkdir()
    with pytest.raises(StoreError, match="not a LeRobot dataset"):
        ingest(ctx, d)
    assert d.exists()


def test_reingest_is_a_noop(registry, tmp_path, ctx):
    src = make_lerobot(tmp_path / "teleop_b", [5, 5])
    s1, e1 = ingest(ctx, src, copy=True)
    s2, e2 = ingest(ctx, src, copy=True)                                   # same source again
    s3, e3 = ingest(ctx, resolve(ctx, s1.uri))              # the store folder itself
    assert s1 == s2 == s3 and e1 == e2 == e3
    assert len(list((registry / "records" / "artifacts" / "session").glob("*.yaml"))) == 1
    assert len(list((registry / "records" / "episodes").glob("*.jsonl"))) == 1


def test_calibrations(registry, tmp_path, ctx):
    cal = tmp_path / "wrist_intrinsics.yaml"
    cal.write_text("fx: 600\n")
    calib = publish(ctx, cal, "calibration").id
    _, eps = ingest(ctx, make_lerobot(tmp_path / "c", [5]), calibrations=[calib])
    assert eps[0].calibrations == [calib]

    src = make_lerobot(tmp_path / "d", [5])
    with pytest.raises(StoreError):
        ingest(ctx, src, calibrations=["calib_00000000000000000000000000"])
    with pytest.raises(StoreError, match="not a calibration"):
        ingest(ctx, src, calibrations=[eps[0].id])
    assert src.exists()


def test_annotations_latest_wins(registry, tmp_path, ctx):
    _, eps = ingest(ctx, make_lerobot(tmp_path / "e", [5, 5]))
    ep = eps[0].id
    annotate(ctx, ep, {"outcome": "failure", "failure_type": "grasp_slip"})
    annotate(ctx, ep, {"outcome": "success"})
    with catalog.connect(ctx) as con:
        latest = dict(con.execute("SELECT key, value FROM annotations WHERE episode = ?", [ep]).fetchall())
        n_log = con.execute("SELECT count(*) FROM annotation_log").fetchone()[0]
    assert latest == {"outcome": "success", "failure_type": "grasp_slip"} and n_log == 3
    with pytest.raises(StoreError):
        annotate(ctx, "ep_00000000000000000000000000", {"outcome": "x"})
    with pytest.raises(StoreError, match="not an episode"):
        annotate(ctx, eps[0].session, {"outcome": "x"})


def _dump(db: Path) -> dict:
    with duckdb.connect(str(db), read_only=True) as con:
        tables = [t for (t,) in con.execute(
            "SELECT table_name FROM information_schema.tables ORDER BY table_name").fetchall()]
        return {t: sorted(map(str, con.execute(f"SELECT * FROM {t}").fetchall())) for t in tables}


def test_rebuild_from_scratch_is_identical(repo, registry, monkeypatch, tmp_path, ctx):
    (repo / "prov.toml").write_text('project = "demo"\n')
    git(repo, "add", "prov.toml")
    git(repo, "commit", "-q", "-m", "prov.toml")
    monkeypatch.chdir(repo)
    src = make_lerobot(tmp_path / "f", [5, 7])
    code = f"import prov; from prov.episodes.ingest import ingest; ingest(prov.context(), {str(src)!r})"
    assert main(["run", "--kind", "collect", "--tag", "robot=so101", "--", sys.executable, "-c", code]) == 0
    with catalog.connect(ctx) as con:
        ep = con.execute("SELECT id FROM episodes ORDER BY episode_index LIMIT 1").fetchone()[0]
    annotate(ctx, ep, {"outcome": "failure"})

    db = ctx.catalog
    catalog.rebuild(ctx)
    first = _dump(db)
    db.unlink()
    catalog.rebuild(ctx)
    assert _dump(db) == first
    assert len(first["episodes"]) == 2 and len(first["runs"]) == 1 and len(first["annotations"]) == 1


def test_connect_rebuilds_after_registry_changes(registry, tmp_path, ctx):
    ingest(ctx, make_lerobot(tmp_path / "g", [5]))
    with catalog.connect(ctx) as con:
        assert con.execute("SELECT count(*) FROM episodes").fetchone()[0] == 1
    ingest(ctx, make_lerobot(tmp_path / "h", [5, 5]))
    with catalog.connect(ctx) as con:
        assert con.execute("SELECT count(*) FROM episodes").fetchone()[0] == 3


def test_lineage_run_to_episodes(repo, registry, monkeypatch, tmp_path, ctx):
    (repo / "prov.toml").write_text('project = "demo"\n')
    git(repo, "add", "prov.toml")
    git(repo, "commit", "-q", "-m", "prov.toml")
    monkeypatch.chdir(repo)
    src = make_lerobot(tmp_path / "i", [5, 6, 7])
    code = f"import prov; from prov.episodes.ingest import ingest; ingest(prov.context(), {str(src)!r})"
    main(["run", "--kind", "collect", "--", sys.executable, "-c", code])
    with catalog.connect(ctx) as con:
        rows = con.execute("""
            SELECT r.kind, e.episode_index, rc.base
            FROM runs r JOIN run_outputs o ON o.run = r.id
            JOIN episodes e ON e.session = o.artifact
            JOIN run_code rc ON rc.run = r.id
            ORDER BY e.episode_index""").fetchall()
    head = git(repo, "rev-parse", "HEAD")
    assert rows == [("collect", 0, head), ("collect", 1, head), ("collect", 2, head)]


def test_cli_ingest_annotate_q(registry, tmp_path, capsys):
    src = make_lerobot(tmp_path / "j", [5, 5])
    assert main(["ingest", "lerobot", str(src), "--meta", "operator=me"]) == 0
    ses = capsys.readouterr().out.split("\t")[0]
    assert main(["q", f"SELECT id FROM episodes WHERE session = '{ses}' ORDER BY episode_index"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "id" and len(lines) == 3
    assert main(["annotate", lines[1], "outcome=success"]) == 0
    assert main(["q", "SELECT value FROM annotations"]) == 0
    assert capsys.readouterr().out.splitlines() == ["value", "success"]
    assert main(["q", "SELECT * FROM nope"]) == 2
