"""Ingest: a recording folder becomes a `ses_` artifact plus one `ep_` ID per episode.

The folder's format (`ctx.ext.formats`, e.g. lerobot) reads its session meta and episode rows.
Each episode records where it came from: `teleop`, or an MCAP file and time range from a source map
(JSONL, one line per episode, written by the MCAP export):
    {"episode_index": 0, "path": "/data/raw/2026-11-09/take_01.mcap", "raw": "raw_...", "start_s": 0.0, "end_s": 18.4}
"""

import json
from pathlib import Path
from typing import Any

from prov.artifacts import publish as artifacts
from prov.artifacts.schema import ArtifactRecord
from prov.core import layout
from prov.core.errors import StoreError
from prov.core.ids import kind_of, new_id
from prov.episodes.schema import EpisodeRecord, EpisodeSource
from prov.storage import registry, store
from prov.storage.lock import RegistryLock


def _format(ctx, name: str):
    if name not in ctx.ext.formats:
        raise StoreError(f"unknown format {name!r}; one of {sorted(ctx.ext.formats)}")
    return ctx.ext.formats[name]


def read_source_map(path: Path) -> dict[int, EpisodeSource]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            idx = row.pop("episode_index")
            out[idx] = EpisodeSource(kind="mcap", **row)
    return out


def _check_sources(rows: list[dict[str, Any]], sources: dict[int, EpisodeSource]) -> None:
    missing = [r["episode_index"] for r in rows if sources and r["episode_index"] not in sources]
    if missing:
        raise StoreError(f"source map has no entry for episodes {missing[:10]}")


def _existing_session_for(ctx, source: Path) -> ArtifactRecord | None:
    return next((a for a in artifacts.all_artifacts(ctx, "session") if a.source == str(source)), None)


def read_episodes(ctx, session_id: str) -> list[EpisodeRecord]:
    path = ctx.registry / layout.episodes_file(session_id)
    if not path.is_file():
        return []
    return [EpisodeRecord.model_validate_json(line) for line in path.read_text().splitlines() if line]


def ingest(ctx, path: Path, format: str = "lerobot", source_map: Path | None = None,
           calibrations: list[str] = (), meta: dict[str, Any] | None = None,
           copy: bool = False) -> tuple[ArtifactRecord, list[EpisodeRecord]]:
    """Publish a folder as a session (unless it is one already) and register its episodes.

    Re-ingesting is a no-op: a folder already in the store, or a source already ingested, returns
    the existing session and episodes. Holds the registry lock for the whole ingest.
    """
    with RegistryLock(ctx.registry):
        return _ingest(ctx, path, format, source_map, calibrations, meta, copy)


def _ingest(ctx, path: Path, format: str, source_map: Path | None, calibrations: list[str],
            meta: dict[str, Any] | None, copy: bool) -> tuple[ArtifactRecord, list[EpisodeRecord]]:
    """ingest, without the lock."""
    fmt = _format(ctx, format)
    for c in calibrations:
        if kind_of(c) != "calibration":
            raise StoreError(f"{c} is not a calibration ID")
        artifacts.load(ctx, c)

    sources = read_source_map(source_map) if source_map else {}
    src = Path(path).expanduser().resolve()
    if src.parent == store.kind_dir(ctx, "session").resolve():
        session = artifacts.load(ctx, src.name)
    elif existing := _existing_session_for(ctx, src):
        session = existing
    else:
        session_meta, rows = fmt.read(src)     # validate before moving anything
        _check_sources(rows, sources)
        session = artifacts._publish(ctx, src, "session", meta={**session_meta, **(meta or {})}, copy=copy)

    if eps := read_episodes(ctx, session.id):
        return session, eps

    session_meta, rows = fmt.read(store.resolve(ctx, session.uri))
    _check_sources(rows, sources)
    fps = float(session_meta["fps"])
    eps = [
        EpisodeRecord(
            id=new_id("episode"), session=session.id, episode_index=r["episode_index"],
            length=r["length"], fps=fps, duration_s=round(r["length"] / fps, 6),
            tasks=r.get("tasks", []), source=sources.get(r["episode_index"], EpisodeSource(kind="teleop")),
            calibrations=list(calibrations),
        )
        for r in rows
    ]
    text = "".join(e.model_dump_json() + "\n" for e in eps)
    ep_path = registry.write(ctx.registry, layout.episodes_file(session.id), text)
    registry.commit(ctx.registry, ep_path, f"ingest {session.id}: {len(eps)} episodes")
    return session, eps
