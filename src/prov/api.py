"""Python API used inside wrapped runs."""

import os
from pathlib import Path

from prov import aliases, config, store
from prov.records import ArtifactRecord


def load(ref: str) -> ArtifactRecord:
    """Resolve an ID or alias to its artifact record; inside `prov run`, record it as an input."""
    machine = config.load_machine()
    record = store.load(aliases.resolve(ref, machine.registry), machine.registry)
    if os.environ.get("PROV_RUN_ID") and os.environ.get(store.INPUTS_ENV):
        with open(os.environ[store.INPUTS_ENV], "a") as f:
            f.write(record.id + "\n")
    return record


def path(record: ArtifactRecord) -> Path:
    """Where an artifact's bytes are in the store."""
    if record.uri is None:
        raise store.StoreError(f"{record.id} has no bytes in the store")
    return store.resolve(record.uri)
