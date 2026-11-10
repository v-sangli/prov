"""Dataset versions: frozen lists of episode IDs. No bytes are copied.

A version is a `ds_` artifact record (no store path) plus `<registry>/datasets/<ds_id>.txt`, one
episode ID per line, sorted. Its alias is `ds:<name>/<n>`, numbered 1, 2, 3 ... per name. With a
split, `ds:<name>-train/<n>` and `ds:<name>-holdout/<n>` are written alongside, same number.
"""

import random
from datetime import datetime, timezone
from pathlib import Path

from prov import aliases, catalog, config, registry
from prov.ids import new_id
from prov.records import ArtifactRecord


class DatasetError(Exception):
    pass


def members_rel(ds_id: str) -> str:
    return f"datasets/{ds_id}.txt"


def members(ref: str, reg: Path | None = None) -> list[str]:
    reg = reg or config.load_machine().registry
    path = reg / members_rel(aliases.resolve(ref, reg))
    if not path.is_file():
        raise DatasetError(f"{ref} is not a dataset")
    return path.read_text().split()


def dataset_sessions(ref: str) -> dict[str, list[int]]:
    """{ses_id: [episode_index, ...]} for loading with LeRobot (repo_id = ses_id, root = store/sessions)."""
    ids = members(ref)
    with catalog.connect() as con:
        rows = con.execute("SELECT session, episode_index FROM episodes WHERE list_contains(?, id) "
                           "ORDER BY session, episode_index", [ids]).fetchall()
    out: dict[str, list[int]] = {}
    for ses, idx in rows:
        out.setdefault(ses, []).append(idx)
    return out


def _split(ids: list[str], sessions: dict[str, str], holdout: float, seed: int, by: str) -> tuple[list, list]:
    rng = random.Random(seed)
    if by == "episode":
        shuffled = sorted(ids)
        rng.shuffle(shuffled)
        k = max(1, round(holdout * len(ids)))
        return sorted(shuffled[k:]), sorted(shuffled[:k])
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(sessions[i], []).append(i)
    order = sorted(groups)
    rng.shuffle(order)
    held: list[str] = []
    for ses in order:
        if len(held) >= holdout * len(ids):
            break
        held += groups[ses]
    if len(held) == len(ids):
        raise DatasetError("session split would hold out every episode; use more sessions or a smaller fraction")
    return sorted(set(ids) - set(held)), sorted(held)


def freeze(name: str, episodes: list[str] | None = None, query: str | None = None,
           parent: str | None = None, notes: str | None = None,
           holdout: float | None = None, seed: int = 0, by: str = "episode") -> dict[str, ArtifactRecord]:
    """Freeze a dataset version from episode IDs or a catalog query returning episode IDs (first column).

    Returns {"all": record} plus {"train": ..., "holdout": ...} when `holdout` is given.
    """
    if (episodes is None) == (query is None):
        raise DatasetError("give either episodes or a query")
    if holdout is not None and not 0 < holdout < 1:
        raise DatasetError("holdout must be a fraction between 0 and 1")
    if by not in ("episode", "session"):
        raise DatasetError("split by 'episode' or 'session'")
    aliases.parse(f"ds:{name}/1")                           # validates the name
    machine = config.load_machine()
    reg = machine.registry

    with catalog.connect(machine) as con:
        if query is not None:
            episodes = [r[0] for r in con.execute(query).fetchall()]
        ids = sorted(set(episodes))
        known = dict(con.execute("SELECT id, session FROM episodes WHERE list_contains(?, id)", [ids]).fetchall())
    unknown = [i for i in ids if i not in known]
    if not ids:
        raise DatasetError("no episodes selected")
    if unknown:
        raise DatasetError(f"not registered episodes: {unknown[:5]}")
    parent_id = aliases.resolve(parent, reg) if parent else None

    existing = [int(v) for v in aliases.versions("ds", name, reg) if v.isdigit()]
    version = str(max(existing, default=0) + 1)
    parts = {"all": (name, ids)}
    if holdout is not None:
        train, held = _split(ids, known, holdout, seed, by)
        parts |= {"train": (f"{name}-train", train), "holdout": (f"{name}-holdout", held)}
        for _, (n, _) in list(parts.items())[1:]:
            if version in aliases.versions("ds", n, reg):
                raise DatasetError(f"ds:{n}/{version} already exists")

    ds_ids = {role: new_id("dataset") for role in parts}
    now = datetime.now(timezone.utc)
    out = {}
    for role, (n, eps) in parts.items():
        ref = f"ds:{n}/{version}"
        record = ArtifactRecord(
            id=ds_ids[role], kind="dataset", uri=None, created=now, meta={
                "alias": ref, "name": n, "version": version, "role": role, "parent": parent_id,
                "siblings": {r: i for r, i in ds_ids.items() if r != role},
                "episodes": len(eps), "sessions": len({known[e] for e in eps}),
                "selection": {"query": query} if query else {"episodes": "explicit list"},
                "split": {"holdout": holdout, "seed": seed, "by": by} if holdout is not None else None,
                "notes": notes,
            })
        mpath = registry.write(reg, members_rel(record.id), "".join(e + "\n" for e in eps))
        rpath = registry.write(reg, f"records/artifacts/dataset/{record.id}.yaml", record.to_yaml())
        registry.commit(reg, [mpath, rpath], f"dataset {ref}: {len(eps)} episodes")
        aliases.set_version(ref, record.id, reg)
        out[role] = record
    return out
