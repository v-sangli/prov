"""Episodes: ingesting LeRobot sessions and annotating episodes.

A session is one LeRobot folder (as recorded by teleop, or exported from MCAP). Ingest publishes
it as a `ses_` artifact and writes one line per episode to
`<registry>/records/episodes/<ses_id>.jsonl`, each with its own `ep_` ID and a reference to where
it came from: `teleop`, or an MCAP file and time range given in a source map.

Source map (JSONL, one line per episode, written by the MCAP export):
    {"episode_index": 0, "path": "/data/raw/2026-11-09/take_01.mcap", "raw": "raw_...", "start_s": 0.0, "end_s": 18.4}
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from prov import config, registry, store
from prov.ids import kind_of, new_id
from prov.records import Annotation, ArtifactRecord, EpisodeRecord, EpisodeSource


def episodes_rel(session_id: str) -> str:
    return f"records/episodes/{session_id}.jsonl"


def annotations_rel(session_id: str) -> str:
    return f"records/annotations/{session_id}.jsonl"


def read_lerobot(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(session meta, [{episode_index, length, tasks}]) from a LeRobot v2.x or v3.0 folder."""
    info_path = root / "meta" / "info.json"
    if not info_path.is_file():
        raise store.StoreError(f"{root} is not a LeRobot dataset (no meta/info.json)")
    info = json.loads(info_path.read_text())
    meta = {
        "format": "lerobot",
        "codebase_version": info.get("codebase_version"),
        "robot_type": info.get("robot_type"),
        "fps": info["fps"],
        "cameras": sorted(k for k, f in info.get("features", {}).items() if f.get("dtype") == "video"),
        "total_episodes": info.get("total_episodes"),
        "total_frames": info.get("total_frames"),
    }
    v3 = root / "meta" / "episodes"
    v2 = root / "meta" / "episodes.jsonl"
    if v3.is_dir():
        rows = duckdb.sql(
            f"SELECT episode_index, length, tasks FROM read_parquet('{v3}/**/*.parquet') ORDER BY episode_index"
        ).fetchall()
        eps = [{"episode_index": i, "length": n, "tasks": list(t or [])} for i, n, t in rows]
    elif v2.is_file():
        eps = sorted((json.loads(line) for line in v2.read_text().splitlines() if line.strip()),
                     key=lambda e: e["episode_index"])
    else:
        raise store.StoreError(f"{root}: no meta/episodes/ (v3) or meta/episodes.jsonl (v2)")
    return meta, eps


def _read_source_map(path: Path) -> dict[int, EpisodeSource]:
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
        raise store.StoreError(f"source map has no entry for episodes {missing[:10]}")


def _existing_session_for(source: Path, reg: Path) -> str | None:
    for p in (reg / "records" / "artifacts" / "session").glob("*.yaml"):
        if ArtifactRecord.from_yaml(p).source == str(source):
            return p.stem
    return None


def read_episodes(session_id: str, reg: Path) -> list[EpisodeRecord]:
    path = reg / episodes_rel(session_id)
    if not path.is_file():
        return []
    return [EpisodeRecord.model_validate_json(line) for line in path.read_text().splitlines() if line]


def ingest_lerobot(path: Path, source_map: Path | None = None, calibrations: list[str] = (),
                   meta: dict[str, Any] | None = None, copy: bool = False) -> tuple[ArtifactRecord, list[EpisodeRecord]]:
    """Publish a LeRobot folder as a session (unless it is one already) and register its episodes.

    Re-ingesting is a no-op: a folder already in the store, or a source already ingested, returns
    the existing session and episodes.
    """
    machine = config.load_machine()
    for c in calibrations:
        if kind_of(c) != "calibration":
            raise store.StoreError(f"{c} is not a calibration ID")
        store.load(c, machine.registry)

    sources = _read_source_map(source_map) if source_map else {}
    src = Path(path).expanduser().resolve()
    sessions_dir = (machine.store_root / store.KIND_DIRS["session"]).resolve()
    if src.parent == sessions_dir:
        session = store.load(src.name, machine.registry)
    elif existing := _existing_session_for(src, machine.registry):
        session = store.load(existing, machine.registry)
    else:
        lerobot_meta, rows = read_lerobot(src)     # validate before moving anything
        _check_sources(rows, sources)
        session = store.publish(src, "session", meta={**lerobot_meta, **(meta or {})}, copy=copy)

    if eps := read_episodes(session.id, machine.registry):
        return session, eps

    root = store.resolve(session.uri, machine.store_root)
    lerobot_meta, rows = read_lerobot(root)
    _check_sources(rows, sources)
    fps = float(lerobot_meta["fps"])
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
    ep_path = registry.write(machine.registry, episodes_rel(session.id), text)
    registry.commit(machine.registry, ep_path, f"ingest {session.id}: {len(eps)} episodes")
    return session, eps


def _session_of(episode_id: str, reg: Path) -> str:
    needle = f'"id":"{episode_id}"'
    for p in (reg / "records" / "episodes").glob("*.jsonl"):
        if needle in p.read_text():
            return p.stem
    raise store.StoreError(f"no episode {episode_id}")


def annotate(episode_id: str, labels: dict[str, str]) -> list[Annotation]:
    """Append labels (outcome, failure_type, tags, note, ...) to an episode; the latest value wins."""
    if kind_of(episode_id) != "episode":
        raise store.StoreError(f"{episode_id} is not an episode ID")
    machine = config.load_machine()
    session_id = _session_of(episode_id, machine.registry)
    now = datetime.now(timezone.utc)
    notes = [Annotation(episode=episode_id, key=k, value=v, time=now) for k, v in labels.items()]
    path = machine.registry / annotations_rel(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.writelines(a.model_dump_json() + "\n" for a in notes)
    registry.commit(machine.registry, path, f"annotate {episode_id}: {', '.join(labels)}")
    return notes
