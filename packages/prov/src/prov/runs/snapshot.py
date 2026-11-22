"""Code snapshots: the whole working tree as a commit under refs/prov/<run_id>.

Built with a temporary index, so the branch, the real index and the working tree are untouched.
Includes modified, staged and new untracked files; gitignored files are not included. Untracked
files over `max_untracked_bytes` are left out and listed.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from prov.core.errors import SnapshotError
from prov.runs.schema import CodeState, ExcludedFile
from prov.storage.registry import IDENTITY as _IDENTITY

MAX_UNTRACKED_BYTES = 5 * 1024 * 1024


def _git(repo: Path, *args: str, env: dict | None = None, check: bool = True) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    if check and p.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")
    return p.stdout.strip()


def snapshot(repo: Path, run_id: str, max_untracked_bytes: int = MAX_UNTRACKED_BYTES,
             push: bool = True) -> CodeState:
    repo = Path(_git(repo, "rev-parse", "--show-toplevel"))
    base = _git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False)
    if not base:
        raise SnapshotError(f"{repo} has no commits; commit once before running")

    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    excluded = []
    for rel in filter(None, untracked):
        size = (repo / rel).stat().st_size
        if size > max_untracked_bytes:
            excluded.append(ExcludedFile(path=rel, bytes=size))

    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), **_IDENTITY}
        _git(repo, "read-tree", "HEAD", env=env)
        _git(repo, "add", "-A", "--", ".", env=env)
        for f in excluded:
            _git(repo, "rm", "--cached", "-q", "--", f.path, env=env)
        tree = _git(repo, "write-tree", env=env)

    dirty = tree != _git(repo, "rev-parse", "HEAD^{tree}")
    commit = (_git(repo, "commit-tree", tree, "-p", base, "-m", f"prov snapshot {run_id}", env=_IDENTITY)
              if dirty else base)
    ref = f"refs/prov/{run_id}"
    _git(repo, "update-ref", ref, commit)

    pushed = False
    if push and "origin" in _git(repo, "remote").split():
        p = subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", f"{ref}:{ref}"],
                           capture_output=True, text=True)
        pushed = p.returncode == 0

    return CodeState(repo=repo.name, path=str(repo), base=base, snapshot=commit, ref=ref,
                     dirty=dirty, pushed=pushed, excluded=excluded)
