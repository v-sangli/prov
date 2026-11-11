"""Publishing and loading artifacts.

publish: move (or copy) a file or folder into the store under a new ID, make it read-only, write
and commit its record, set its alias, record it as an output of the current run, and emit
`artifact.published`. load: an artifact record by ID.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prov.artifacts import aliases
from prov.artifacts.schema import ArtifactRecord
from prov.core import events, layout
from prov.core.errors import StoreError
from prov.core.ids import kind_of, new_id
from prov.storage import registry, store


def _check_alias(ctx, alias: str, kind: str) -> None:
    akind, aname, aversion, _ = aliases.parse(alias)
    if aversion is None or aliases.KINDS[akind] != kind:
        raise StoreError(f"--alias {alias!r} must be a numbered version naming a {kind}")
    if aversion in aliases.versions(ctx, akind, aname):
        raise StoreError(f"{alias} already exists; versions never change")


def publish(ctx, path: Path, kind: str, meta: dict[str, Any] | None = None, copy: bool = False,
            alias: str | None = None) -> ArtifactRecord:
    """`alias` (`kind:name/version`) is checked before anything moves and set after."""
    if alias:
        _check_alias(ctx, alias, kind)
    if kind not in layout.KIND_DIRS:
        raise StoreError(f"kind {kind!r} can't be published; one of {sorted(layout.KIND_DIRS)}")
    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise StoreError(f"{src} does not exist")
    if store.is_inside(ctx, src):
        raise StoreError(f"{src} is already inside the store")
    store.warn_if_low_space(ctx)

    id_ = new_id(kind)
    dest = store.place(ctx, src, kind, id_, copy=copy)
    record = ArtifactRecord(
        id=id_, kind=kind, uri=store.uri(ctx, dest), created=datetime.now(timezone.utc),
        source=str(src), produced_by=ctx.run.run_id if ctx.run else None, meta=meta or {},
    )
    if kind == "checkpoint" and dest.is_dir():
        (dest / "manifest.yaml").write_text(record.to_yaml())
    store.make_read_only(ctx, kind, id_)

    rec_path = registry.write(ctx.registry, layout.artifact_record(kind, id_), record.to_yaml())
    registry.commit(ctx.registry, rec_path, f"publish {id_} ({kind})")
    if alias:
        aliases.set_version(ctx, alias, id_)
    if ctx.run:
        ctx.run.record_output(id_)
    events.emit(ctx, "artifact.published", record)
    return record


def write_record(ctx, record: ArtifactRecord) -> Path:
    """Write (not commit) a record that has no bytes in the store, e.g. a dataset version."""
    return registry.write(ctx.registry, layout.artifact_record(record.kind, record.id), record.to_yaml())


def load(ctx, id_: str) -> ArtifactRecord:
    path = ctx.registry / layout.artifact_record(kind_of(id_), id_)
    if not path.is_file():
        raise StoreError(f"no record for {id_}")
    return ArtifactRecord.from_yaml(path)


def all_artifacts(ctx, kind: str = "*") -> list[ArtifactRecord]:
    return [ArtifactRecord.from_yaml(p)
            for p in sorted((ctx.registry / layout.ARTIFACTS_DIR).glob(f"{kind}/*.yaml"))]


def path(ctx, record: ArtifactRecord) -> Path:
    """Where an artifact's bytes are in the store."""
    if record.uri is None:
        raise StoreError(f"{record.id} has no bytes in the store")
    return store.resolve(ctx, record.uri)
