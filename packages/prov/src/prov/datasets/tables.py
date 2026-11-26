"""Catalog table built from dataset members files."""

from prov.artifacts.publish import all_artifacts
from prov.core import layout
from prov.core.extensions import CatalogTables

DDL = """
-- (dataset ID, its alias, member episode ID)
CREATE TABLE dataset_members (dataset VARCHAR, alias VARCHAR, episode VARCHAR);
"""

# Lineage: a dataset's parent dataset and the sessions of its episodes flow into it.
EDGES = """
SELECT meta->>'parent' AS src, 'parent' AS rel, id AS dst FROM artifacts
WHERE kind = 'dataset' AND meta->>'parent' IS NOT NULL
UNION ALL
SELECT DISTINCT e.session, 'member', m.dataset FROM dataset_members m JOIN episodes e ON e.id = m.episode
"""


def rows(ctx) -> dict[str, list[tuple]]:
    """One row per line of every members file; a files dataset has none (ADR 0023)."""
    alias = {a.id: a.meta.get("alias") for a in all_artifacts(ctx, "dataset")}
    return {"dataset_members": [
        (f.stem, alias[f.stem], e) for f in sorted((ctx.registry / layout.DATASETS_DIR).glob("*.txt"))
        for e in f.read_text().split()]}


TABLES = CatalogTables("datasets", DDL, rows, edges=EDGES)
