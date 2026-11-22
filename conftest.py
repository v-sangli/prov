import os
import subprocess
from pathlib import Path

import pytest

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch):
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with one commit (tracked a.txt, b.txt; .gitignore ignores *.log) and a bare origin."""
    r = tmp_path / "proj"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "a.txt").write_text("a\n")
    (r / "b.txt").write_text("b\n")
    (r / ".gitignore").write_text("*.log\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    remote = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(r, "remote", "add", "origin", str(remote))
    return r


@pytest.fixture
def registry(tmp_path: Path, monkeypatch) -> Path:
    reg = tmp_path / "registry"
    reg.mkdir()
    git(reg, "init", "-q", "-b", "main")
    (reg / ".git" / "info" / "exclude").write_text(".prov.lock\n")   # setup step, as in the README
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'registry = "{reg}"\nstore_root = "{tmp_path / "store"}"\n'
                   f'catalog = "{tmp_path / "catalog.duckdb"}"\n')
    monkeypatch.setenv("PROV_CONFIG", str(cfg))
    return reg


@pytest.fixture
def ctx(registry):
    """The Context for the test registry (built-in extensions)."""
    from prov.wiring import context
    return context()
