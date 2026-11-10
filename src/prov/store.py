"""The store: artifact bytes under `<store_root>/<kind dir>/<id>/`, read-only once published."""

import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prov import aliases, config, registry
from prov.ids import kind_of, new_id
from prov.records import ArtifactRecord

KIND_DIRS = {
    "raw": "raw",
    "session": "sessions",
    "dataset": "datasets",
    "checkpoint": "checkpoints",
    "benchmark": "benchmarks",
    "calibration": "calibrations",
    "result": "results",
    "figure": "figures",
    "video": "media",
}
MIN_FREE_BYTES = 50 * 1024**3
OUTPUTS_ENV = "PROV_RUN_OUTPUTS"   # set by `prov run`: file the child appends published IDs to
INPUTS_ENV = "PROV_RUN_INPUTS"     # set by `prov run`: file the child appends loaded IDs to


class StoreError(Exception):
    pass


def record_rel(kind: str, id_: str) -> str:
    return f"records/artifacts/{kind}/{id_}.yaml"


def resolve(uri: str, store_root: Path | None = None) -> Path:
    if not uri.startswith("store://"):
        raise StoreError(f"not a store URI: {uri!r}")
    root = store_root or config.load_machine().store_root
    return root / uri.removeprefix("store://")


def load(id_: str, registry_root: Path | None = None) -> ArtifactRecord:
    reg = registry_root or config.load_machine().registry
    path = reg / record_rel(kind_of(id_), id_)
    if not path.is_file():
        raise StoreError(f"no record for {id_}")
    return ArtifactRecord.from_yaml(path)


def _make_read_only(path: Path) -> None:
    targets = [path] if path.is_file() else [*path.rglob("*"), path]   # children before parents
    for p in targets:
        if p.is_symlink():
            continue
        mode = p.stat().st_mode
        p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def warn_if_low_space(store_root: Path) -> None:
    probe = store_root if store_root.exists() else store_root.parent
    free = shutil.disk_usage(probe).free
    if free < MIN_FREE_BYTES:
        print(f"prov: warning: only {free / 1024**3:.0f} GB free on the store disk", file=sys.stderr)


def publish(path: Path, kind: str, meta: dict[str, Any] | None = None, copy: bool = False,
            alias: str | None = None) -> ArtifactRecord:
    """Move (or copy) `path` into the store under a new ID, make it read-only, record it.

    `alias` (`kind:name/version`) is checked before anything moves and set after."""
    if alias:
        akind, aname, aversion, _ = aliases.parse(alias)
        if aversion is None or aliases.KINDS[akind] != kind:
            raise StoreError(f"--alias {alias!r} must be a numbered version naming a {kind}")
        if aversion in aliases.versions(akind, aname):
            raise StoreError(f"{alias} already exists; versions never change")
    if kind not in KIND_DIRS:
        raise StoreError(f"kind {kind!r} can't be published; one of {sorted(KIND_DIRS)}")
    machine = config.load_machine()
    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise StoreError(f"{src} does not exist")
    root = machine.store_root.resolve() if machine.store_root.exists() else machine.store_root
    if src == root or root in src.parents:
        raise StoreError(f"{src} is already inside the store")
    warn_if_low_space(machine.store_root)

    id_ = new_id(kind)
    dest_dir = machine.store_root / KIND_DIRS[kind] / id_
    dest = dest_dir if src.is_dir() else dest_dir / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not copy:
        shutil.move(src, dest)
    elif src.is_dir():
        shutil.copytree(src, dest, symlinks=True)
    else:
        shutil.copy2(src, dest)

    run_id = os.environ.get("PROV_RUN_ID")
    record = ArtifactRecord(
        id=id_, kind=kind, uri=f"store://{dest.relative_to(machine.store_root)}",
        created=datetime.now(timezone.utc), source=str(src), produced_by=run_id, meta=meta or {},
    )
    if kind == "checkpoint" and dest.is_dir():
        (dest / "manifest.yaml").write_text(record.to_yaml())
    _make_read_only(dest_dir)

    rec_path = registry.write(machine.registry, record_rel(kind, id_), record.to_yaml())
    registry.commit(machine.registry, rec_path, f"publish {id_} ({kind})")
    if alias:
        aliases.set_version(alias, id_, machine.registry)
    if run_id and os.environ.get(OUTPUTS_ENV):
        with open(os.environ[OUTPUTS_ENV], "a") as f:
            f.write(id_ + "\n")
    return record
