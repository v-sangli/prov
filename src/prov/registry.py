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


def commit(registry: Path, path: Path, message: str) -> None:
    """Commit one file in the registry repo; no-op if the registry is not a git repo."""
    if not (registry / ".git").exists():
        return
    env = {**os.environ, **IDENTITY}
    rel = str(path.relative_to(registry))
    subprocess.run(["git", "-C", str(registry), "add", "--", rel], check=True, env=env)
    subprocess.run(["git", "-C", str(registry), "commit", "-q", "-m", message, "--", rel],
                   check=True, env=env, capture_output=True)
