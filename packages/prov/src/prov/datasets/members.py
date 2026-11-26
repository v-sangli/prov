"""Reading episode selections: `<registry>/datasets/<ds_id>.txt`, one episode ID per line, sorted.
A dataset record with no members file holds files in the store instead (ADR 0023)."""

from prov.artifacts import aliases
from prov.core import layout
from prov.core.errors import DatasetError
from prov.storage import catalog


def members(ctx, ref: str) -> list[str]:
    id_ = aliases.resolve(ctx, ref)
    path = ctx.registry / layout.dataset_members(id_)
    if path.is_file():
        return path.read_text().split()
    if (ctx.registry / layout.artifact_record("dataset", id_)).is_file():
        raise DatasetError(f"{ref} holds files, not episodes; use prov.path")
    raise DatasetError(f"{ref} is not a dataset")


def dataset_sessions(ctx, ref: str) -> dict[str, list[int]]:
    """{ses_id: [episode_index, ...]} for loading with LeRobot (repo_id = ses_id, root = store/sessions)."""
    ids = members(ctx, ref)
    with catalog.connect(ctx) as con:
        rows = con.execute("SELECT session, episode_index FROM episodes WHERE list_contains(?, id) "
                           "ORDER BY session, episode_index", [ids]).fetchall()
    out: dict[str, list[int]] = {}
    for ses, idx in rows:
        out.setdefault(ses, []).append(idx)
    return out
