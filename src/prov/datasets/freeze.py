"""Freezing dataset versions.

A version is a `ds_` artifact record (no store path) plus its members file. Its alias is
`ds:<name>/<n>`, numbered 1, 2, 3 ... per name. With a split, `ds:<name>-train/<n>` and
`ds:<name>-holdout/<n>` are written alongside, same number.
"""

from datetime import datetime, timezone

from prov.artifacts import aliases
from prov.artifacts.publish import write_record
from prov.artifacts.schema import ArtifactRecord
from prov.core import layout
from prov.core.errors import DatasetError
from prov.core.ids import new_id
from prov.datasets.split import BY, split
from prov.storage import catalog, registry
from prov.storage.lock import RegistryLock


def _select(ctx, episodes: list[str] | None, query: str | None) -> tuple[list[str], dict[str, str]]:
    """(sorted unique episode IDs, {episode: session}); every ID must be registered."""
    with catalog.connect(ctx) as con:
        if query is not None:
            episodes = [r[0] for r in con.execute(query).fetchall()]
        ids = sorted(set(episodes))
        known = dict(con.execute("SELECT id, session FROM episodes WHERE list_contains(?, id)", [ids]).fetchall())
    unknown = [i for i in ids if i not in known]
    if not ids:
        raise DatasetError("no episodes selected")
    if unknown:
        raise DatasetError(f"not registered episodes: {unknown[:5]}")
    return ids, known


def freeze(ctx, name: str, episodes: list[str] | None = None, query: str | None = None,
           parent: str | None = None, notes: str | None = None,
           holdout: float | None = None, seed: int = 0, by: str = "episode") -> dict[str, ArtifactRecord]:
    """Freeze a dataset version from episode IDs or a catalog query returning episode IDs (first column).

    Returns {"all": record} plus {"train": ..., "holdout": ...} when `holdout` is given.
    """
    if (episodes is None) == (query is None):
        raise DatasetError("give either episodes or a query")
    if holdout is not None and not 0 < holdout < 1:
        raise DatasetError("holdout must be a fraction between 0 and 1")
    if by not in BY:
        raise DatasetError("split by 'episode' or 'session'")
    aliases.parse(f"ds:{name}/1")                           # validates the name
    ids, known = _select(ctx, episodes, query)
    parent_id = aliases.resolve(ctx, parent) if parent else None

    with RegistryLock(ctx.registry):   # from version pick to alias: no orphans, no reused N
        existing = [int(v) for v in aliases.versions(ctx, "ds", name) if v.isdigit()]
        version = str(max(existing, default=0) + 1)
        parts = {"all": (name, ids)}
        if holdout is not None:
            train, held = split(ids, known, holdout, seed, by)
            parts |= {"train": (f"{name}-train", train), "holdout": (f"{name}-holdout", held)}
            for _, (n, _) in list(parts.items())[1:]:
                if version in aliases.versions(ctx, "ds", n):
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
            mpath = registry.write(ctx.registry, layout.dataset_members(record.id), "".join(e + "\n" for e in eps))
            rpath = write_record(ctx, record)
            registry.commit(ctx.registry, [mpath, rpath], f"dataset {ref}: {len(eps)} episodes")
            aliases._set_version(ctx, ref, record.id)
            out[role] = record
    return out
