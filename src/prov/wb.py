"""W&B: runs and curves online, artifacts by reference only.

`prov.wandb_init()` starts a W&B run carrying the prov run ID. After that, `prov.load` logs each
input with `use_artifact` and `prov.publish` logs each output with `log_artifact`. Each artifact
holds one reference, `file://<registry>/records/artifacts/<kind>/<id>.yaml` (the record, whose
`uri` names the store path), with `checksum=False`: W&B stats that one file, hashes its path
string, reads no contents and uploads nothing. Referencing the record rather than a store folder
keeps it one entry however many files the folder holds (W&B lists a referenced folder file by file).
W&B draws the lineage graph from these; the registry stays the source of truth.
"""

import os
import re
import sys
from pathlib import Path

from prov import aliases, config, store
from prov.records import ArtifactRecord

WANDB_ENV = "PROV_RUN_WANDB"       # set by `prov run`: file the child writes its W&B run path to
_loaded: list[ArtifactRecord] = []  # inputs loaded before wandb_init, logged at init


def _active():
    wandb = sys.modules.get("wandb")
    return wandb.run if wandb is not None and wandb.run is not None else None


def _alias_of(record: ArtifactRecord, reg: Path) -> str | None:
    if record.meta.get("alias"):
        return record.meta["alias"]
    vrows, _ = aliases.all_aliases(reg)
    return next((ref for ref, _, _, _, id_ in vrows if id_ == record.id), None)


def reference_artifact(record: ArtifactRecord):
    """A W&B artifact holding only a file:// reference to this artifact's registry record."""
    import wandb

    machine = config.load_machine()
    target = machine.registry / store.record_rel(record.kind, record.id)
    alias = _alias_of(record, machine.registry)
    name = aliases.parse(alias)[1] if alias else record.id
    art = wandb.Artifact(name=re.sub(r"[^A-Za-z0-9._-]", "-", name), type=record.kind,
                         metadata={"prov_id": record.id, "prov_alias": alias, "uri": record.uri})
    art.add_reference(f"file://{target}", checksum=False)
    return art


def on_load(record: ArtifactRecord) -> None:
    run = _active()
    if run is None:
        _loaded.append(record)
        return
    try:
        run.use_artifact(reference_artifact(record))
    except Exception as exc:                # W&B trouble must never break a run
        print(f"prov: W&B use_artifact failed for {record.id}: {exc}", file=sys.stderr)


def on_publish(record: ArtifactRecord) -> None:
    run = _active()
    if run is None:
        return
    try:
        run.log_artifact(reference_artifact(record))
    except Exception as exc:
        print(f"prov: W&B log_artifact failed for {record.id}: {exc}", file=sys.stderr)


def wandb_init(**kwargs):
    """`wandb.init` with the prov run ID in the config; earlier `prov.load` inputs are logged."""
    import wandb

    run_id = os.environ.get("PROV_RUN_ID")
    kwargs.setdefault("project", os.environ.get("PROV_PROJECT"))
    kwargs["config"] = {**(kwargs.get("config") or {}),
                        "prov": {"run_id": run_id, "inputs": [r.id for r in _loaded]}}
    run = wandb.init(**kwargs)
    if run_id and os.environ.get(WANDB_ENV):
        Path(os.environ[WANDB_ENV]).write_text(run.path if isinstance(run.path, str) else "/".join(run.path))
    pending, _loaded[:] = list(_loaded), []
    for record in pending:
        on_load(record)
    return run
