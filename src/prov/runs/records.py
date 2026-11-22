"""Run records in the registry."""

from pathlib import Path

from prov.core import layout
from prov.core.errors import StoreError
from prov.runs.schema import RunRecord
from prov.storage import registry
from prov.storage.lock import RegistryLock


def path(ctx, run_id: str) -> Path:
    return ctx.registry / layout.run_record(run_id)


def load(ctx, run_id: str) -> RunRecord:
    p = path(ctx, run_id)
    if not p.is_file():
        raise StoreError(f"no record for {run_id}")
    return RunRecord.from_yaml(p)


def write(ctx, record: RunRecord, message: str | None = None) -> Path:
    """Write the record; commit it when `message` is given."""
    with RegistryLock(ctx.registry):
        p = registry.write(ctx.registry, layout.run_record(record.id), record.to_yaml())
        if message:
            registry.commit(ctx.registry, p, message)
    return p


def all_runs(ctx) -> list[RunRecord]:
    return [RunRecord.from_yaml(p) for p in sorted((ctx.registry / layout.RUNS_DIR).glob("*.yaml"))]
