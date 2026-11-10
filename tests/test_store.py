import sys
from pathlib import Path

import pytest
import yaml

from conftest import git
from prov.cli import main
from prov.records import ArtifactRecord, RunRecord
from prov.store import StoreError, load, publish, resolve


def _store(tmp_path: Path) -> Path:
    return tmp_path / "store"


def _session_dir(tmp_path: Path) -> Path:
    d = tmp_path / "incoming" / "teleop_0001"
    (d / "data").mkdir(parents=True)
    (d / "data" / "file-000.parquet").write_bytes(b"rows")
    (d / "meta.json").write_text("{}")
    return d


def test_publish_moves_folder_under_its_id(registry, tmp_path):
    src = _session_dir(tmp_path)
    rec = publish(src, "session", meta={"robot": "so101"})

    dest = resolve(rec.uri, _store(tmp_path))
    assert rec.id.startswith("ses_") and rec.uri == f"store://sessions/{rec.id}"
    assert not src.exists()
    assert (dest / "data" / "file-000.parquet").read_bytes() == b"rows"
    assert rec.source == str(src) and rec.meta == {"robot": "so101"} and rec.produced_by is None
    assert load(rec.id, registry) == rec
    assert git(registry, "log", "-1", "--format=%s") == f"publish {rec.id} (session)"
    assert git(registry, "status", "--porcelain") == ""


def test_published_folder_is_read_only(registry, tmp_path):
    dest = resolve(publish(_session_dir(tmp_path), "session").uri, _store(tmp_path))
    with pytest.raises(PermissionError):
        (dest / "meta.json").write_text("changed")
    with pytest.raises(PermissionError):
        (dest / "new.txt").write_text("x")
    with pytest.raises(PermissionError):
        (dest / "data" / "file-000.parquet").unlink()
    assert (dest / "meta.json").read_text() == "{}"


def test_publish_single_file(registry, tmp_path):
    fig = tmp_path / "closure.png"
    fig.write_bytes(b"png")
    rec = publish(fig, "figure")
    assert rec.uri == f"store://figures/{rec.id}/closure.png"
    assert resolve(rec.uri, _store(tmp_path)).read_bytes() == b"png" and not fig.exists()


def test_copy_keeps_source(registry, tmp_path):
    src = _session_dir(tmp_path)
    rec = publish(src, "session", copy=True)
    assert src.exists() and (resolve(rec.uri, _store(tmp_path)) / "meta.json").exists()


def test_checkpoint_gets_manifest(registry, tmp_path):
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "model.safetensors").write_bytes(b"w")
    rec = publish(ckpt, "checkpoint", meta={"step": "30000"})
    manifest = resolve(rec.uri, _store(tmp_path)) / "manifest.yaml"
    assert ArtifactRecord.model_validate(yaml.safe_load(manifest.read_text())) == rec


@pytest.mark.parametrize("kind", ["episode", "run", "nonsense"])
def test_unpublishable_kinds(registry, tmp_path, kind):
    with pytest.raises(StoreError):
        publish(_session_dir(tmp_path), kind)


def test_missing_path(registry, tmp_path):
    with pytest.raises(StoreError, match="does not exist"):
        publish(tmp_path / "nope", "session")


def test_path_already_in_store(registry, tmp_path):
    rec = publish(_session_dir(tmp_path), "session")
    with pytest.raises(StoreError, match="already inside the store"):
        publish(resolve(rec.uri, _store(tmp_path)), "session")


def test_publish_inside_run_links_both_ways(repo, registry, monkeypatch, tmp_path):
    (repo / "prov.toml").write_text('project = "demo"\n')
    git(repo, "add", "prov.toml")
    git(repo, "commit", "-q", "-m", "prov.toml")
    monkeypatch.chdir(repo)
    src = _session_dir(tmp_path)
    code = f"from prov.store import publish; publish({str(src)!r}, 'session')"

    assert main(["run", "--kind", "collect", "--", sys.executable, "-c", code]) == 0

    [run] = [RunRecord.from_yaml(p) for p in (registry / "records" / "runs").glob("*.yaml")]
    [art_path] = (registry / "records" / "artifacts" / "session").glob("*.yaml")
    art = ArtifactRecord.from_yaml(art_path)
    assert run.outputs == [art.id] and art.produced_by == run.id


def test_cli_publish_and_show(registry, tmp_path, capsys):
    src = _session_dir(tmp_path)
    assert main(["publish", str(src), "--kind", "session", "--meta", "task=cube"]) == 0
    id_ = capsys.readouterr().out.strip()
    assert main(["show", id_]) == 0
    out = capsys.readouterr().out
    assert f"id: {id_}" in out and "task: cube" in out
    assert f"# path: {_store(tmp_path)}/sessions/{id_}" in out
    assert main(["show", "ses_00000000000000000000000000"]) == 2
