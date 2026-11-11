"""W&B: runs and curves online, artifacts by reference only.

`prov.wandb_init()` starts a W&B run carrying the prov run ID. After that, each `artifact.loaded`
event logs the input with `use_artifact` and each `artifact.published` logs the output with
`log_artifact`; `run.summary` values go to the W&B run summary. Each artifact holds one reference,
`file://<registry>/records/artifacts/<kind>/<id>.yaml` (the record, whose `uri` names the store
path), with `checksum=False`: W&B stats that one file, hashes its path string, reads no contents
and uploads nothing. Referencing the record rather than a store folder keeps it one entry however
many files the folder holds (W&B lists a referenced folder file by file). W&B draws the lineage
graph from these; the registry stays the source of truth.

The `wandb` package is imported only when an artifact is built or a run started; without an active
W&B run the subscribers do nothing (inputs are queued until wandb_init).
"""

import re
import sys

from prov.artifacts import aliases
from prov.artifacts.schema import ArtifactRecord
from prov.core import layout, log

_log = log.get("wandb")
_loaded: list[ArtifactRecord] = []  # inputs loaded before wandb_init, logged at init


def _active():
    wandb = sys.modules.get("wandb")
    return wandb.run if wandb is not None and wandb.run is not None else None


def reference_artifact(ctx, record: ArtifactRecord):
    """A W&B artifact holding only a file:// reference to this artifact's registry record."""
    import wandb

    target = ctx.registry / layout.artifact_record(record.kind, record.id)
    alias = record.meta.get("alias") or aliases.alias_of(ctx, record.id)
    name = aliases.parse(alias)[1] if alias else record.id
    art = wandb.Artifact(name=re.sub(r"[^A-Za-z0-9._-]", "-", name), type=record.kind,
                         metadata={"prov_id": record.id, "prov_alias": alias, "uri": record.uri})
    art.add_reference(f"file://{target}", checksum=False)
    return art


def on_load(ctx, record: ArtifactRecord) -> None:
    run = _active()
    if run is None:
        _loaded.append(record)
        return
    try:
        run.use_artifact(reference_artifact(ctx, record))
    except Exception as exc:                # W&B trouble must never break a run
        _log.warning("W&B use_artifact failed for %s: %s", record.id, exc)


def on_publish(ctx, record: ArtifactRecord) -> None:
    run = _active()
    if run is None:
        return
    try:
        run.log_artifact(reference_artifact(ctx, record))
    except Exception as exc:
        _log.warning("W&B log_artifact failed for %s: %s", record.id, exc)


def on_summary(ctx, values: dict) -> None:
    if (run := _active()) is not None:
        run.summary.update(values)


SUBSCRIBERS = {"artifact.loaded": [on_load], "artifact.published": [on_publish], "run.summary": [on_summary]}


def wandb_init(ctx, **kwargs):
    """`wandb.init` with the prov run ID in the config; earlier loaded inputs are logged."""
    import wandb

    run_env = ctx.run
    kwargs.setdefault("project", run_env.project if run_env else None)
    kwargs["config"] = {**(kwargs.get("config") or {}),
                        "prov": {"run_id": run_env.run_id if run_env else None, "inputs": [r.id for r in _loaded]}}
    run = wandb.init(**kwargs)
    if run_env:
        run_env.set_wandb(run.path if isinstance(run.path, str) else "/".join(run.path))
    pending, _loaded[:] = list(_loaded), []
    for record in pending:
        on_load(ctx, record)
    return run
