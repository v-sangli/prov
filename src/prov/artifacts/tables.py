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


def rows(ctx) -> dict[str, list[tuple]]:
    vrows, lrows = aliases.all_aliases(ctx)
    return {
        "artifacts": [(a.id, a.kind, a.uri, str(store.resolve(ctx, a.uri)) if a.uri else None, utc(a.created),
                       a.source, a.produced_by, json.dumps(a.meta, sort_keys=True)) for a in all_artifacts(ctx)],
        "aliases": vrows,
        "alias_labels": lrows,
    }


TABLES = CatalogTables("artifacts", DDL, rows)
