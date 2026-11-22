"""Catalog tables built from doc records."""

from prov.core.extensions import CatalogTables
from prov.docs.register import all_docs
from prov.storage.catalog import utc

DDL = """
CREATE TABLE docs (id VARCHAR PRIMARY KEY, repo VARCHAR, remote VARCHAR, path VARCHAR, title VARCHAR,
    created TIMESTAMP);
-- what each doc's latest version cites
CREATE TABLE doc_cites (doc VARCHAR, target VARCHAR);
"""

# Lineage: a doc is labelled with its title and place; what it cites flows into it.
NODES = "SELECT id, id || '  doc, ' || title || ' (' || repo || '/' || path || ')' AS label FROM docs"
EDGES = "SELECT target AS src, 'cites' AS rel, doc AS dst FROM doc_cites"


def rows(ctx) -> dict[str, list[tuple]]:
    docs = all_docs(ctx)
    return {
        "docs": [(d.id, d.repo, d.remote, d.path, d.title, utc(d.created)) for d in docs],
        "doc_cites": [(d.id, t) for d in docs for t in d.versions[-1].cites],
    }


TABLES = CatalogTables("docs", DDL, rows, NODES, EDGES)
