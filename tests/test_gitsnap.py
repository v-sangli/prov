from pathlib import Path

import pytest

from conftest import git
from prov.gitsnap import SnapshotError, snapshot


def _state(repo: Path) -> dict:
    """Everything a snapshot must leave untouched."""
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "branch": git(repo, "symbolic-ref", "HEAD"),
        "status": git(repo, "status", "--porcelain", "--untracked-files=all"),
        "index_tree": git(repo, "write-tree"),
        "files": {p.name: p.read_bytes() for p in repo.iterdir() if p.is_file()},
    }


def test_clean_repo(repo):
    s = snapshot(repo, "run_X")
    assert not s.dirty
    assert s.snapshot == s.base == git(repo, "rev-parse", "HEAD")
    assert git(repo, "rev-parse", "refs/prov/run_X") == s.base
    assert s.pushed


def test_dirty_repo_diff_is_exactly_the_changes(repo):
    (repo / "a.txt").write_text("a changed\n")          # modified, unstaged
    (repo / "b.txt").write_text("b staged\n")
    git(repo, "add", "b.txt")                           # staged
    (repo / "new.py").write_text("print(1)\n")          # untracked
    (repo / "debug.log").write_text("ignored\n")        # gitignored
    before = _state(repo)

    s = snapshot(repo, "run_Y")

    assert s.dirty and s.snapshot != s.base
    assert _state(repo) == before
    changed = set(git(repo, "diff", "--name-only", s.base, s.snapshot).split())
    assert changed == {"a.txt", "b.txt", "new.py"}
    assert git(repo, "show", f"{s.snapshot}:a.txt") == "a changed"
    assert git(repo, "show", f"{s.snapshot}:b.txt") == "b staged"
    assert git(repo, "rev-parse", f"{s.snapshot}^") == s.base


def test_ref_reaches_remote(repo, tmp_path):
    (repo / "a.txt").write_text("x\n")
    s = snapshot(repo, "run_Z")
    remote = git(tmp_path / "origin.git", "rev-parse", "refs/prov/run_Z")
    assert s.pushed and remote == s.snapshot


def test_no_remote_still_snapshots(repo):
    git(repo, "remote", "remove", "origin")
    (repo / "a.txt").write_text("x\n")
    s = snapshot(repo, "run_N")
    assert s.dirty and not s.pushed
    assert git(repo, "rev-parse", "refs/prov/run_N") == s.snapshot


def test_big_untracked_file_is_listed_not_stored(repo):
    (repo / "weights.bin").write_bytes(b"0" * 2000)
    (repo / "small.py").write_text("x = 1\n")
    s = snapshot(repo, "run_B", max_untracked_bytes=1000)
    assert [(f.path, f.bytes) for f in s.excluded] == [("weights.bin", 2000)]
    files = set(git(repo, "ls-tree", "-r", "--name-only", s.snapshot).split())
    assert "small.py" in files and "weights.bin" not in files


def test_snapshot_from_subdirectory(repo):
    (repo / "sub").mkdir()
    (repo / "sub" / "c.txt").write_text("c\n")
    s = snapshot(repo / "sub", "run_S")
    assert s.path == str(repo)
    assert "sub/c.txt" in git(repo, "ls-tree", "-r", "--name-only", s.snapshot).split()


def test_repo_without_commits(tmp_path):
    r = tmp_path / "empty"
    r.mkdir()
    git(r, "init", "-q")
    with pytest.raises(SnapshotError, match="no commits"):
        snapshot(r, "run_E")
