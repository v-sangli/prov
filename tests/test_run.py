import sys
from pathlib import Path

from conftest import git
from prov.cli import main
from prov.runs.schema import RunRecord


def _records(registry: Path) -> list[RunRecord]:
    return [RunRecord.from_yaml(p) for p in sorted((registry / "records" / "runs").glob("*.yaml"))]


def _project(repo: Path, monkeypatch, repos='["."]'):
    (repo / "prov.toml").write_text(f'project = "demo"\nrepos = {repos}\n')
    git(repo, "add", "prov.toml")
    git(repo, "commit", "-q", "-m", "prov.toml")
    monkeypatch.chdir(repo)


def test_run_writes_record_and_commits_it(repo, registry, monkeypatch, tmp_path):
    _project(repo, monkeypatch)
    out = tmp_path / "seen_id"
    code = f"import os; open({str(out)!r}, 'w').write(os.environ['PROV_RUN_ID'])"
    rc = main(["run", "--kind", "analysis", "--tag", "task=cube", "--", sys.executable, "-c", code])

    assert rc == 0
    [rec] = _records(registry)
    assert rec.id == out.read_text()
    assert rec.status == "ok" and rec.exit_code == 0 and rec.finished >= rec.started
    assert rec.kind == "analysis" and rec.project == "demo" and rec.tags == {"task": "cube"}
    assert rec.command[0] == sys.executable
    [c] = rec.code
    assert c.base == git(repo, "rev-parse", "HEAD") and not c.dirty and c.pushed
    assert git(registry, "log", "--format=%s") == f"run {rec.id} ok"
    assert git(registry, "status", "--porcelain") == ""


def test_failed_command_status_and_exit_code(repo, registry, monkeypatch):
    _project(repo, monkeypatch)
    rc = main(["run", "--", sys.executable, "-c", "raise SystemExit(3)"])
    [rec] = _records(registry)
    assert rc == 3 and rec.status == "failed" and rec.exit_code == 3


def test_missing_command_binary(repo, registry, monkeypatch):
    _project(repo, monkeypatch)
    rc = main(["run", "--", "definitely-not-a-command-xyz"])
    [rec] = _records(registry)
    assert rc == 127 and rec.status == "failed"


def test_dirty_run_records_snapshot(repo, registry, monkeypatch):
    _project(repo, monkeypatch)
    (repo / "a.txt").write_text("edited\n")
    main(["run", "--", sys.executable, "-c", "pass"])
    [rec] = _records(registry)
    [c] = rec.code
    assert c.dirty and c.ref == f"refs/prov/{rec.id}"
    assert git(repo, "diff", "--name-only", c.base, c.snapshot) == "a.txt"


def test_multiple_repos(repo, registry, monkeypatch, tmp_path):
    other = tmp_path / "upstream"
    other.mkdir()
    git(other, "init", "-q", "-b", "main")
    (other / "u.py").write_text("u\n")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "u")
    (other / "u.py").write_text("patched\n")
    _project(repo, monkeypatch, repos='[".", "../upstream"]')

    main(["run", "--", sys.executable, "-c", "pass"])
    [rec] = _records(registry)
    assert [(c.repo, c.dirty, c.pushed) for c in rec.code] == [("proj", False, True), ("upstream", True, False)]


def test_no_prov_toml(registry, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--", "true"]) == 2
    assert "no prov.toml" in capsys.readouterr().err
