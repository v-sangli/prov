"""Writing records into the registry repo."""

import os
import subprocess
from pathlib import Path

# Commits made by prov (registry records, code snapshots) use this identity, so no personal
# name or email is pushed with them.
IDENTITY = {
    "GIT_AUTHOR_NAME": "prov", "GIT_AUTHOR_EMAIL": "prov@localhost",
    "GIT_COMMITTER_NAME": "prov", "GIT_COMMITTER_EMAIL": "prov@localhost",
}


def write(registry: Path, rel: str, text: str) -> Path:
    """Atomically write `text` to `registry/rel`."""
    path = registry / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)
    return path


def append(registry: Path, rel: str, text: str) -> Path:
    """Append `text` to `registry/rel` (append-only logs)."""
    path = registry / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(text)
    return path


def commit(registry: Path, paths: Path | list[Path], message: str) -> None:
    """Commit these files in the registry repo; no-op if the registry is not a git repo."""
    if not (registry / ".git").exists():
        return
    env = {**os.environ, **IDENTITY}
    rels = [str(p.relative_to(registry)) for p in ([paths] if isinstance(paths, Path) else paths)]
    subprocess.run(["git", "-C", str(registry), "add", "--", *rels], check=True, env=env)
    subprocess.run(["git", "-C", str(registry), "commit", "-q", "-m", message, "--", *rels],
                   check=True, env=env, capture_output=True)


def head(registry: Path) -> str | None:
    """The registry's HEAD commit, or None when it is not a git repo or has no commits."""
    if not (registry / ".git").exists():
        return None
    p = subprocess.run(["git", "-C", str(registry), "rev-parse", "-q", "--verify", "HEAD"],
                       capture_output=True, text=True)
    return p.stdout.strip() or None
