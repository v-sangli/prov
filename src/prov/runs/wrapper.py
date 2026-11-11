"""The `prov run` lifecycle.

1. Snapshot every repo in prov.toml (refs/prov/<run_id>, pushed when there is an origin).
2. Write the run record with status `running`.
3. Run the command with the RunEnv variables set (core.runenv), so prov calls inside it record
   inputs, outputs, summary values and the W&B run path into temporary files.
4. Fold those files into the record, set status / exit code / finish time, write and commit it.
"""

import json
import os
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from prov.core import log
from prov.core.context import ProjectConfig
from prov.core.ids import new_id
from prov.core.runenv import RunEnv
from prov.runs import machine, records, snapshot
from prov.runs.schema import RunRecord
from prov.storage import store

_log = log.get("run")


def _lines(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if line]


def run(ctx, project: ProjectConfig, command: list[str], kind: str = "other",
        tags: dict[str, str] | None = None, notes: str | None = None) -> int:
    """Run `command` as a recorded run; returns the exit code to exit with (128+N on signal N)."""
    store.warn_if_low_space(ctx)
    run_id = new_id("run")
    code = [snapshot.snapshot(repo, run_id) for repo in project.repos]
    record = RunRecord(
        id=run_id, kind=kind, project=project.project,
        started=datetime.now(timezone.utc), status="running", host=socket.gethostname(),
        cwd=str(Path.cwd()), command=command, code=code, env=machine.env(), tags=tags or {}, notes=notes,
    )
    records.write(ctx, record)
    for c in code:
        if c.dirty:
            _log.info("%s is dirty; snapshot %s at %s", c.repo, c.snapshot[:10], c.ref)
        if not c.pushed:
            _log.info("%s: %s not pushed (no origin or push failed)", c.repo, c.ref)
    _log.info("%s", run_id)

    with tempfile.TemporaryDirectory() as tmp:
        files = {k: Path(tmp) / k for k in ("inputs", "outputs", "summary", "wandb")}
        for f in files.values():
            f.touch()
        run_env = RunEnv(run_id=run_id, project=project.project, **files)
        try:
            rc = subprocess.run(command, env={**os.environ, **run_env.to_env()}).returncode
        except FileNotFoundError:
            rc = 127
        except KeyboardInterrupt:
            rc = -2
        record.inputs = list(dict.fromkeys(_lines(files["inputs"])))
        record.outputs = _lines(files["outputs"])
        for line in _lines(files["summary"]):
            record.summary.update(json.loads(line))
        record.wandb = files["wandb"].read_text().strip() or None

    record.finished = datetime.now(timezone.utc)
    record.exit_code = rc
    record.status = "ok" if rc == 0 else ("killed" if rc < 0 else "failed")
    records.write(ctx, record, f"run {run_id} {record.status}")
    return rc if rc >= 0 else 128 - rc
