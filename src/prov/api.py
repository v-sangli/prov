"""The public Python API used inside wrapped runs: `import prov`.

Each function builds the Context (machine config + the current `prov run`, if any) and calls the
library layer. Scripts that want the library directly can take `prov.context()` and call it.
"""

from pathlib import Path
from typing import Any

from prov.artifacts import aliases
from prov.artifacts import publish as _artifacts
from prov.artifacts.schema import ArtifactRecord
from prov.core import events, log
from prov.datasets import members as _members
from prov.integrations import wandb as _wandb
from prov.wiring import context

_log = log.get("api")


def load(ref: str) -> ArtifactRecord:
    """Resolve an ID or alias to its artifact record; inside `prov run`, record it as an input."""
    ctx = context()
    record = _artifacts.load(ctx, aliases.resolve(ctx, ref))
    if ctx.run:
        ctx.run.record_input(record.id)
    events.emit(ctx, "artifact.loaded", record)
    return record


def publish(path: Path, kind: str, meta: dict[str, Any] | None = None, copy: bool = False,
            alias: str | None = None) -> ArtifactRecord:
    """Move (or copy) `path` into the store under a new ID, make it read-only, record it.
    Inside `prov run` it becomes the run's output. `alias` (`kind:name/version`) is set too."""
    return _artifacts.publish(context(), path, kind, meta=meta, copy=copy, alias=alias)


def path(record: ArtifactRecord) -> Path:
    """Where an artifact's bytes are in the store."""
    return _artifacts.path(context(), record)


def summary(**values: float | int | str) -> None:
    """Final numbers for the current run (success_rate=0.62, n_episodes=50); later values win.
    Also sent to the W&B run summary when one is active."""
    ctx = context()
    if not (ctx.run and ctx.run.add_summary(values)):
        _log.warning("summary outside `prov run`; not recorded")
    events.emit(ctx, "run.summary", values)


def members(ref: str) -> list[str]:
    """Episode IDs of a dataset version."""
    return _members.members(context(), ref)


def dataset_sessions(ref: str) -> dict[str, list[int]]:
    """{ses_id: [episode_index, ...]} for loading with LeRobot (repo_id = ses_id, root = store/sessions)."""
    return _members.dataset_sessions(context(), ref)


def wandb_init(**kwargs):
    """`wandb.init` with the prov run ID in the config; earlier `prov.load` inputs are logged."""
    return _wandb.wandb_init(context(), **kwargs)


__all__ = ["context", "load", "publish", "path", "summary", "members", "dataset_sessions",
           "wandb_init"]
