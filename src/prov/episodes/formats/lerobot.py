"""LeRobot v2.x and v3.0 folders."""

import json
from pathlib import Path
from typing import Any

import duckdb

from prov.core.errors import StoreError
from prov.core.extensions import IngestFormat


def read(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(session meta, [{episode_index, length, tasks}]) from a LeRobot v2.x or v3.0 folder."""
    info_path = root / "meta" / "info.json"
    if not info_path.is_file():
        raise StoreError(f"{root} is not a LeRobot dataset (no meta/info.json)")
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
        raise StoreError(f"{root}: no meta/episodes/ (v3) or meta/episodes.jsonl (v2)")
    return meta, eps


FORMAT = IngestFormat("lerobot", read)
