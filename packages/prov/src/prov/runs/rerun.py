"""Re-run a recorded run on its exact code.

Each repo in the run's record is checked out at its snapshot commit as a detached git worktree,
laid out under a temporary root the way the repos sit relative to each other (so prov.toml's
relative `repos` still resolve). The command runs from the matching working directory as a new
`prov run`, tagged `rerun_of=<run_id>`; command arguments that point inside a recorded repo are
pointed at its worktree. The worktrees are removed afterwards.

Not restored: gitignored files (e.g. a .venv inside the repo), untracked files over the size cap
(listed in the record), and the Python environment. Use an interpreter outside the repos.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from prov.core.errors import RerunError, StoreError
from prov.runs import records


def _git(repo: str, *args: str) -> None:
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RerunError(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")


def _remap(value: str, mapping: dict[str, Path]) -> str:
    for old, new in mapping.items():
        if value == old or value.startswith(old + os.sep):
            return str(new) + value[len(old):]
    return value


def rerun(ctx, run_id: str) -> int:
    try:
        record = records.load(ctx, run_id)
    except StoreError as exc:
        raise RerunError(str(exc)) from None
    if not record.code:
        raise RerunError(f"{run_id} recorded no code")

    base = Path(os.path.commonpath([c.path for c in record.code]))
    if len(record.code) == 1:
        base = base.parent
    with tempfile.TemporaryDirectory(prefix=f"prov-rerun-{run_id}-") as tmp:
        mapping: dict[str, Path] = {}
        try:
            for c in sorted(record.code, key=lambda c: c.path):
                dest = Path(tmp) / Path(c.path).relative_to(base)
                dest.parent.mkdir(parents=True, exist_ok=True)
                _git(c.path, "worktree", "add", "--detach", "-q", str(dest), c.snapshot)
                mapping[c.path] = dest
            mapping = dict(sorted(mapping.items(), key=lambda kv: -len(kv[0])))   # longest prefix first
            cwd = _remap(record.cwd, mapping)
            if not Path(cwd).is_dir():
                raise RerunError(f"working directory {record.cwd} is not inside a recorded repo")
            command = [_remap(a, mapping) for a in record.command]
            argv = [sys.executable, "-m", "prov.cli", "run", "--kind", record.kind,
                    "--tag", f"rerun_of={run_id}",
                    *[f"--tag={k}={v}" for k, v in record.tags.items() if k != "rerun_of"],
                    "--", *command]
            return subprocess.run(argv, cwd=cwd).returncode
        finally:
            for c in record.code:
                if c.path in mapping:
                    subprocess.run(["git", "-C", c.path, "worktree", "remove", "--force", str(mapping[c.path])],
                                   capture_output=True)
