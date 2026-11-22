"""The store: artifact bytes under `<store_root>/<kind dir>/<id>/`, read-only once placed.

Bytes only; the records describing them are written by `artifacts.publish`.
"""

import shutil
import stat
from pathlib import Path

from prov.core import layout, log
from prov.core.errors import StoreError

MIN_FREE_BYTES = 50 * 1024**3
URI_PREFIX = "store://"

_log = log.get("store")


def uri(ctx, path: Path) -> str:
    return URI_PREFIX + str(path.relative_to(ctx.store_root))


def resolve(ctx, uri_: str) -> Path:
    if not uri_.startswith(URI_PREFIX):
        raise StoreError(f"not a store URI: {uri_!r}")
    return ctx.store_root / uri_.removeprefix(URI_PREFIX)


def kind_dir(ctx, kind: str) -> Path:
    return ctx.store_root / layout.KIND_DIRS[kind]


def is_inside(ctx, path: Path) -> bool:
    root = ctx.store_root.resolve() if ctx.store_root.exists() else ctx.store_root
    return path == root or root in path.parents


def warn_if_low_space(ctx) -> None:
    probe = ctx.store_root if ctx.store_root.exists() else ctx.store_root.parent
    free = shutil.disk_usage(probe).free
    if free < MIN_FREE_BYTES:
        _log.warning("warning: only %.0f GB free on the store disk", free / 1024**3)


def place(ctx, src: Path, kind: str, id_: str, copy: bool = False) -> Path:
    """Move (or copy) `src` to `<store>/<kind dir>/<id>/`; a file keeps its name inside that folder.
    Returns the placed file or folder. Call `make_read_only` once anything extra is written."""
    dest_dir = ctx.store_root / layout.store_dir(kind, id_)
    dest = dest_dir if src.is_dir() else dest_dir / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not copy:
        shutil.move(src, dest)
    elif src.is_dir():
        shutil.copytree(src, dest, symlinks=True)
    else:
        shutil.copy2(src, dest)
    return dest


def make_read_only(ctx, kind: str, id_: str) -> None:
    path = ctx.store_root / layout.store_dir(kind, id_)
    targets = [path] if path.is_file() else [*path.rglob("*"), path]   # children before parents
    for p in targets:
        if p.is_symlink():
            continue
        mode = p.stat().st_mode
        p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
