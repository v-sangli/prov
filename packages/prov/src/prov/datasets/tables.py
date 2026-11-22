"""Catalog table built from dataset members files."""

from prov.artifacts.publish import all_artifacts
from prov.core import layout
from prov.core.extensions import CatalogTables

DDL = """
-- (dataset ID, its alias, member episode ID)
CREATE TABLE dataset_members (dataset VARCHAR, alias VARCHAR, episode VARCHAR);
"""


def rows(ctx) -> dict[str, list[tuple]]:
    return {"dataset_members": [
        (a.id, a.meta.get("alias"), e) for a in all_artifacts(ctx, "dataset")
        for e in (ctx.registry / layout.dataset_members(a.id)).read_text().split()]}


TABLES = CatalogTables("datasets", DDL, rows)
