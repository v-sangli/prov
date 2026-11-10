import sys
from pathlib import Path

import pytest

from conftest import git
from prov import aliases, catalog
from prov.aliases import AliasError
from prov.cli import main
from prov.datasets import DatasetError, dataset_sessions, freeze, members
from prov.episodes import annotate, ingest_lerobot
from prov.records import RunRecord
from prov.store import StoreError, publish
from test_episodes import make_lerobot


def _sessions(tmp_path: Path, lengths: list[list[int]]) -> list[list[str]]:
    """Ingest one session per entry; return episode IDs per session."""
    out = []
    for i, ls in enumerate(lengths):
        _, eps = ingest_lerobot(make_lerobot(tmp_path / f"s{i}", ls))
        out.append([e.id for e in eps])
    return out


ALL = "SELECT id FROM episodes"


# aliases

@pytest.mark.parametrize("ref,parts", [
    ("ds:cube-pick/3", ("ds", "cube-pick", "3", None)),
    ("model:gr00t-cube/0.4", ("model", "gr00t-cube", "0.4", None)),
    ("model:gr00t-cube@best", ("model", "gr00t-cube", None, "best")),
])
def test_parse(ref, parts):
    assert aliases.parse(ref) == parts


@pytest.mark.parametrize("bad", ["ds:x@2", "ds:x", "nope:x/1", "ds:/1", "ds:x/1@best", "ds_01ABC"])
def test_parse_rejects(bad):
    with pytest.raises(AliasError):
        aliases.parse(bad)


def test_versions_never_change(registry, tmp_path):
    [[a, b]] = _sessions(tmp_path, [[5, 5]])
    ds1 = freeze("x", query=ALL)["all"].id
    aliases.set_version("ds:y/1", ds1)
    aliases.set_version("ds:y/1", ds1)                      # same target: no-op
    with pytest.raises(AliasError, match="never change"):
        aliases.set_version("ds:y/1", freeze("z", episodes=[a])["all"].id)
    with pytest.raises(AliasError, match="is not a dataset"):
        aliases.set_version("ds:y/2", a)


def test_labels_move_and_history_is_git_log(registry, tmp_path):
    [[a, b]] = _sessions(tmp_path, [[5, 5]])
    v1 = freeze("x", episodes=[a])["all"].id
    v2 = freeze("x", episodes=[a, b])["all"].id
    aliases.set_label("ds:x@best", "ds:x/1")
    aliases.set_label("ds:x@best", "ds:x/2")
    assert aliases.resolve("ds:x@best") == v2 and aliases.resolve("ds:x/1") == v1
    log = git(registry, "log", "--format=%s", "--", "aliases/ds/x.yaml").splitlines()
    assert log[:2] == ["label ds:x@best -> 2 (was 1)", "label ds:x@best -> 1"]
    with pytest.raises(AliasError, match="does not exist"):
        aliases.set_label("ds:x@best", "ds:x/9")
    with pytest.raises(AliasError):
        aliases.set_label("ds:x@best", "ds:other/1")


def test_resolve(registry, tmp_path):
    [[a, _]] = _sessions(tmp_path, [[5, 5]])
    assert aliases.resolve(a) == a
    with pytest.raises(AliasError, match="no version"):
        aliases.resolve("ds:missing/1")
    with pytest.raises(AliasError, match="no label"):
        aliases.resolve("ds:missing@best")


# datasets

def test_freeze_numbers_versions_and_old_versions_stay(registry, tmp_path):
    [s0, s1] = _sessions(tmp_path, [[5, 5], [5, 5, 5]])
    v1 = freeze("cube", episodes=s0, notes="first two")["all"]
    v2 = freeze("cube", query=ALL, parent="ds:cube/1")["all"]

    assert v1.meta["alias"] == "ds:cube/1" and v2.meta["alias"] == "ds:cube/2"
    assert v1.uri is None and v1.meta["episodes"] == 2 and v1.meta["sessions"] == 1
    assert v2.meta["parent"] == v1.id and v2.meta["selection"] == {"query": ALL}
    assert members("ds:cube/1") == sorted(s0) and members("ds:cube/2") == sorted(s0 + s1)
    assert aliases.resolve("ds:cube/1") == v1.id
    assert git(registry, "status", "--porcelain") == ""


def test_freeze_rejects_bad_selection(registry, tmp_path):
    _sessions(tmp_path, [[5]])
    with pytest.raises(DatasetError, match="not registered"):
        freeze("x", episodes=["ep_00000000000000000000000000"])
    with pytest.raises(DatasetError, match="no episodes"):
        freeze("x", query="SELECT id FROM episodes WHERE false")
    with pytest.raises(DatasetError):
        freeze("x")
    assert aliases.versions("ds", "x") == {}


def test_split_by_episode(registry, tmp_path):
    [ids] = _sessions(tmp_path, [[5] * 20])
    parts = freeze("cube", query=ALL, holdout=0.2, seed=7)
    train, held = members("ds:cube-train/1"), members("ds:cube-holdout/1")
    assert len(held) == 4 and len(train) == 16
    assert set(train) | set(held) == set(ids) and not set(train) & set(held)
    assert parts["train"].meta["siblings"] == {"all": parts["all"].id, "holdout": parts["holdout"].id}
    freeze("cube", query=ALL, holdout=0.2, seed=7)
    assert members("ds:cube-holdout/2") == held                 # same seed, same split


def test_split_by_session(registry, tmp_path):
    sessions = _sessions(tmp_path, [[5] * 3, [5] * 3, [5] * 3, [5] * 3])
    freeze("cube", query=ALL, holdout=0.25, by="session")
    held = set(members("ds:cube-holdout/1"))
    assert any(held == set(s) for s in sessions)                # exactly one whole session
    with pytest.raises(DatasetError, match="every episode"):
        freeze("one", episodes=sessions[0], holdout=0.5, by="session")


def test_dataset_sessions_for_lerobot(registry, tmp_path):
    [s0, s1] = _sessions(tmp_path, [[5, 5, 5], [5, 5]])
    freeze("pick", episodes=[s0[0], s0[2], s1[1]])
    got = dataset_sessions("ds:pick/1")
    with catalog.connect() as con:
        ses = dict(con.execute("SELECT id, session FROM episodes").fetchall())
    assert got == {ses[s0[0]]: [0, 2], ses[s1[1]]: [1]}


def test_catalog_tables_and_failure_query(registry, tmp_path):
    [ids] = _sessions(tmp_path, [[5, 5, 5]])
    annotate(ids[1], {"outcome": "failure", "failure_type": "grasp_slip"})
    freeze("cube", query=ALL)
    aliases.set_label("ds:cube@latest", "ds:cube/1")
    with catalog.connect() as con:
        rows = con.execute("""
            SELECT e.id, ft.value
            FROM dataset_members m JOIN episodes e ON e.id = m.episode
            JOIN annotations o ON o.episode = e.id AND o.key = 'outcome' AND o.value = 'failure'
            LEFT JOIN annotations ft ON ft.episode = e.id AND ft.key = 'failure_type'
            WHERE m.alias = 'ds:cube/1'""").fetchall()
        label = con.execute("SELECT version FROM alias_labels WHERE ref = 'ds:cube@latest'").fetchone()
        n_alias = con.execute("SELECT count(*) FROM aliases WHERE kind = 'ds'").fetchone()[0]
    assert rows == [(ids[1], "grasp_slip")] and label == ("1",) and n_alias == 1


# load / publish --alias / CLI

def test_load_inside_run_records_inputs(repo, registry, monkeypatch, tmp_path):
    _sessions(tmp_path, [[5, 5]])
    freeze("cube", query=ALL)
    (repo / "prov.toml").write_text('project = "demo"\n')
    git(repo, "add", "prov.toml")
    git(repo, "commit", "-q", "-m", "prov.toml")
    monkeypatch.chdir(repo)
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "w.bin").write_bytes(b"w")
    code = ("import prov; ds = prov.load('ds:cube/1'); prov.load('ds:cube/1'); "
            f"prov.publish({str(ckpt)!r}, 'checkpoint', alias='model:cube-policy/0.1')")
    assert main(["run", "--kind", "train", "--", sys.executable, "-c", code]) == 0

    [run] = [RunRecord.from_yaml(p) for p in (registry / "records" / "runs").glob("*.yaml")]
    model = aliases.resolve("model:cube-policy/0.1")
    assert run.inputs == [aliases.resolve("ds:cube/1")] and run.outputs == [model]
    with catalog.connect() as con:
        chain = con.execute("""
            SELECT al.ref FROM run_outputs o JOIN run_inputs i ON i.run = o.run
            JOIN aliases al ON al.id = i.artifact WHERE o.artifact = ?""", [model]).fetchall()
    assert chain == [("ds:cube/1",)]


def test_publish_alias_checked_before_moving(registry, tmp_path):
    f = tmp_path / "cal.yaml"
    f.write_text("fx: 1\n")
    rec = publish(f, "calibration", alias="calib:wrist/1")
    assert aliases.resolve("calib:wrist/1") == rec.id
    g = tmp_path / "cal2.yaml"
    g.write_text("fx: 2\n")
    with pytest.raises(StoreError, match="already exists"):
        publish(g, "calibration", alias="calib:wrist/1")
    with pytest.raises(StoreError, match="numbered version naming a calibration"):
        publish(g, "calibration", alias="model:wrist/1")
    assert g.exists()


def test_cli_dataset_and_alias(registry, tmp_path, capsys):
    [ids] = _sessions(tmp_path, [[5, 5, 5, 5]])
    eps = tmp_path / "eps.txt"
    eps.write_text("\n".join(ids[:3]))
    assert main(["dataset", "freeze", "cube", "--episodes", str(eps), "--holdout", "0.34"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [l.split("\t")[0] for l in out] == ["ds:cube/1", "ds:cube-train/1", "ds:cube-holdout/1"]
    assert main(["alias", "label", "ds:cube@best", "ds:cube/1"]) == 0
    assert main(["alias", "show", "ds:cube@best"]) == 0
    assert capsys.readouterr().out.strip() == out[0].split("\t")[1]
    assert main(["show", "ds:cube/1"]) == 0
    shown = capsys.readouterr().out
    assert "role: all" in shown and "# path" not in shown
    assert main(["alias", "set", "ds:cube/1", ids[0]]) == 2
