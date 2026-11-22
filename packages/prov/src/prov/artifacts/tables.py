"""Catalog tables built from artifact records and aliases."""

import json

from prov.artifacts import aliases
from prov.artifacts.publish import all_artifacts
from prov.core.extensions import CatalogTables
from prov.storage import store
from prov.storage.catalog import utc

DDL = """
-- path is the resolved store path
CREATE TABLE artifacts (id VARCHAR PRIMARY KEY, kind VARCHAR, uri VARCHAR, path VARCHAR,
    created TIMESTAMP, source VARCHAR, produced_by VARCHAR, meta JSON);
CREATE TABLE aliases (ref VARCHAR PRIMARY KEY, kind VARCHAR, name VARCHAR, version VARCHAR, id VARCHAR);
CREATE TABLE alias_labels (ref VARCHAR PRIMARY KEY, kind VARCHAR, name VARCHAR, label VARCHAR, version VARCHAR);
"""

# Lineage: an artifact is labelled with its aliases and kind (sessions and datasets with their
# episode counts); its producing run flows into it.
NODES = """
SELECT a.id, a.id || coalesce('  ' || (SELECT string_agg(ref, ' ' ORDER BY ref) FROM aliases WHERE id = a.id), '')
    || '  ' || a.kind || CASE a.kind
        WHEN 'dataset' THEN (SELECT ', ' || count(*) || ' episodes in ' || count(DISTINCT e.session) || ' sessions'
                             FROM dataset_members m JOIN episodes e ON e.id = m.episode WHERE m.dataset = a.id)
        WHEN 'session' THEN (SELECT ', ' || count(*) || ' episodes' FROM episodes WHERE session = a.id)
        ELSE '' END AS label
FROM artifacts a
"""
EDGES = "SELECT produced_by AS src, 'produced' AS rel, id AS dst FROM artifacts WHERE produced_by IS NOT NULL"


def rows(ctx) -> dict[str, list[tuple]]:
    vrows, lrows = aliases.all_aliases(ctx)
    return {
        "artifacts": [(a.id, a.kind, a.uri, str(store.resolve(ctx, a.uri)) if a.uri else None, utc(a.created),
                       a.source, a.produced_by, json.dumps(a.meta, sort_keys=True)) for a in all_artifacts(ctx)],
        "aliases": vrows,
        "alias_labels": lrows,
    }


TABLES = CatalogTables("artifacts", DDL, rows, NODES, EDGES)
