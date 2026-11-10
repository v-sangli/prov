"""Python API used inside wrapped runs."""

import json
import os
import sys
from pathlib import Path

from prov import aliases, config, store, wb
from prov.records import ArtifactRecord

SUMMARY_ENV = "PROV_RUN_SUMMARY"   # set by `prov run`: file the child appends summary entries to


def load(ref: str) -> ArtifactRecord:
    """Resolve an ID or alias to its artifact record; inside `prov run`, record it as an input."""
    machine = config.load_machine()
    record = store.load(aliases.resolve(ref, machine.registry), machine.registry)
    if os.environ.get("PROV_RUN_ID") and os.environ.get(store.INPUTS_ENV):
        with open(os.environ[store.INPUTS_ENV], "a") as f:
            f.write(record.id + "\n")
    wb.on_load(record)
    return record


def summary(**values: float | int | str) -> None:
    """Final numbers for the current run (success_rate=0.62, n_episodes=50); later values win.
    Also sent to the W&B run summary when one is active."""
    if os.environ.get("PROV_RUN_ID") and os.environ.get(SUMMARY_ENV):
        with open(os.environ[SUMMARY_ENV], "a") as f:
            f.write(json.dumps(values) + "\n")
    else:
        print("prov: summary outside `prov run`; not recorded", file=sys.stderr)
    if (run := wb._active()) is not None:
        run.summary.update(values)


def path(record: ArtifactRecord) -> Path:
    """Where an artifact's bytes are in the store."""
    if record.uri is None:
        raise store.StoreError(f"{record.id} has no bytes in the store")
    return store.resolve(record.uri)
