"""Catalog tables built from run records."""

from prov.core.extensions import CatalogTables
from prov.runs import records
from prov.storage.catalog import utc

DDL = """
CREATE TABLE runs (id VARCHAR PRIMARY KEY, kind VARCHAR, project VARCHAR, started TIMESTAMP,
    finished TIMESTAMP, status VARCHAR, exit_code INTEGER, host VARCHAR, cwd VARCHAR,
    command VARCHAR[], wandb VARCHAR, notes VARCHAR);
CREATE TABLE run_code (run VARCHAR, repo VARCHAR, path VARCHAR, base VARCHAR, snapshot VARCHAR,
    ref VARCHAR, dirty BOOLEAN, pushed BOOLEAN);
CREATE TABLE run_inputs (run VARCHAR, artifact VARCHAR);
CREATE TABLE run_outputs (run VARCHAR, artifact VARCHAR);
CREATE TABLE run_tags (run VARCHAR, key VARCHAR, value VARCHAR);
-- value is NULL for non-numeric entries; text always holds the value as a string
CREATE TABLE run_summary (run VARCHAR, key VARCHAR, value DOUBLE, text VARCHAR);
"""


def rows(ctx) -> dict[str, list[tuple]]:
    runs = records.all_runs(ctx)
    return {
        "runs": [(r.id, r.kind, r.project, utc(r.started), utc(r.finished), r.status, r.exit_code,
                  r.host, r.cwd, r.command, r.wandb, r.notes) for r in runs],
        "run_code": [(r.id, c.repo, c.path, c.base, c.snapshot, c.ref, c.dirty, c.pushed)
                     for r in runs for c in r.code],
        "run_inputs": [(r.id, a) for r in runs for a in r.inputs],
        "run_outputs": [(r.id, a) for r in runs for a in r.outputs],
        "run_tags": [(r.id, k, v) for r in runs for k, v in r.tags.items()],
        "run_summary": [(r.id, k, float(v) if isinstance(v, (int, float)) else None, str(v))
                        for r in runs for k, v in r.summary.items()],
    }


TABLES = CatalogTables("runs", DDL, rows)
