"""The DuckDB catalog: an index rebuilt from the registry. Deleting it loses nothing.

Tables:
    runs          one row per run
    run_code      repo snapshots per run
    run_inputs    (run, artifact)
    run_outputs   (run, artifact)
    run_tags      (run, key, value)
    run_summary   (run, key, value DOUBLE, text)   value is NULL for non-numeric entries
    artifacts     one row per artifact; `path` is the resolved store path
    episodes      one row per episode, with its source (teleop / MCAP path and time range)
    annotation_log  every annotation ever made
    annotations   view: latest value per (episode, key)
    dataset_members (dataset ID, alias, episode)
    aliases       (ref `kind:name/version`, kind, name, version, id)
    alias_labels  (ref `kind:name@label`, kind, name, label, version)
    catalog_meta  registry HEAD the catalog was built from

All timestamps are UTC.

`connect()` rebuilds first when the registry has changed since the last build.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import yaml

from prov import aliases, config, store
from prov.records import Annotation, ArtifactRecord, EpisodeRecord, RunRecord

SCHEMA = """
CREATE TABLE runs (id VARCHAR PRIMARY KEY, kind VARCHAR, project VARCHAR, started TIMESTAMP,
    finished TIMESTAMP, status VARCHAR, exit_code INTEGER, host VARCHAR, cwd VARCHAR,
    command VARCHAR[], wandb VARCHAR, notes VARCHAR);
CREATE TABLE run_code (run VARCHAR, repo VARCHAR, path VARCHAR, base VARCHAR, snapshot VARCHAR,
    ref VARCHAR, dirty BOOLEAN, pushed BOOLEAN);
CREATE TABLE run_inputs (run VARCHAR, artifact VARCHAR);
CREATE TABLE run_outputs (run VARCHAR, artifact VARCHAR);
CREATE TABLE run_tags (run VARCHAR, key VARCHAR, value VARCHAR);
CREATE TABLE run_summary (run VARCHAR, key VARCHAR, value DOUBLE, text VARCHAR);
CREATE TABLE artifacts (id VARCHAR PRIMARY KEY, kind VARCHAR, uri VARCHAR, path VARCHAR,
    created TIMESTAMP, source VARCHAR, produced_by VARCHAR, meta JSON);
CREATE TABLE episodes (id VARCHAR PRIMARY KEY, session VARCHAR, episode_index INTEGER,
    length INTEGER, fps DOUBLE, duration_s DOUBLE, tasks VARCHAR[], source_kind VARCHAR,
    source_raw VARCHAR, source_path VARCHAR, start_s DOUBLE, end_s DOUBLE, calibrations VARCHAR[]);
CREATE TABLE annotation_log (episode VARCHAR, key VARCHAR, value VARCHAR, time TIMESTAMP);
CREATE VIEW annotations AS
    SELECT episode, key, arg_max(value, time) AS value, max(time) AS time
    FROM annotation_log GROUP BY episode, key;
CREATE TABLE dataset_members (dataset VARCHAR, alias VARCHAR, episode VARCHAR);
CREATE TABLE aliases (ref VARCHAR PRIMARY KEY, kind VARCHAR, name VARCHAR, version VARCHAR, id VARCHAR);
CREATE TABLE alias_labels (ref VARCHAR PRIMARY KEY, kind VARCHAR, name VARCHAR, label VARCHAR, version VARCHAR);
CREATE TABLE catalog_meta (registry_head VARCHAR);
"""


def _registry_head(reg: Path) -> str | None:
    if not (reg / ".git").exists():
        return None
    p = subprocess.run(["git", "-C", str(reg), "rev-parse", "-q", "--verify", "HEAD"],
                       capture_output=True, text=True)
    return p.stdout.strip() or None


def _lines(paths, model):
    for p in sorted(paths):
        for line in p.read_text().splitlines():
            if line.strip():
                yield model.model_validate_json(line)


def _utc(t: datetime | None) -> datetime | None:
    """Naive UTC: every catalog timestamp is UTC (avoids DuckDB's pytz dependency for TIMESTAMPTZ)."""
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t else None


def _insert(con: duckdb.DuckDBPyConnection, table: str, rows: list[tuple]) -> None:
    if rows:
        con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)


def rebuild(machine: config.MachineConfig | None = None) -> Path:
    machine = machine or config.load_machine()
    reg, db = machine.registry, machine.catalog
    db.parent.mkdir(parents=True, exist_ok=True)
    tmp = db.with_name(db.name + ".tmp")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    con.execute(SCHEMA)

    runs = [RunRecord.from_yaml(p) for p in sorted((reg / "records" / "runs").glob("*.yaml"))]
    _insert(con, "runs", [(r.id, r.kind, r.project, _utc(r.started), _utc(r.finished), r.status, r.exit_code, r.host,
                           r.cwd, r.command, r.wandb, r.notes) for r in runs])
    _insert(con, "run_code", [(r.id, c.repo, c.path, c.base, c.snapshot, c.ref, c.dirty, c.pushed)
                              for r in runs for c in r.code])
    _insert(con, "run_inputs", [(r.id, a) for r in runs for a in r.inputs])
    _insert(con, "run_outputs", [(r.id, a) for r in runs for a in r.outputs])
    _insert(con, "run_tags", [(r.id, k, v) for r in runs for k, v in r.tags.items()])
    _insert(con, "run_summary", [(r.id, k, float(v) if isinstance(v, (int, float)) else None, str(v))
                                 for r in runs for k, v in r.summary.items()])

    arts = [ArtifactRecord.model_validate(yaml.safe_load(p.read_text()))
            for p in sorted((reg / "records" / "artifacts").glob("*/*.yaml"))]
    _insert(con, "artifacts", [(a.id, a.kind, a.uri, str(store.resolve(a.uri, machine.store_root)) if a.uri else None, _utc(a.created),
                                a.source, a.produced_by, json.dumps(a.meta, sort_keys=True)) for a in arts])
    eps = _lines((reg / "records" / "episodes").glob("*.jsonl"), EpisodeRecord)
    _insert(con, "episodes", [(e.id, e.session, e.episode_index, e.length, e.fps, e.duration_s, e.tasks,
                               e.source.kind, e.source.raw, e.source.path, e.source.start_s, e.source.end_s,
                               e.calibrations) for e in eps])
    notes = _lines((reg / "records" / "annotations").glob("*.jsonl"), Annotation)
    _insert(con, "annotation_log", [(a.episode, a.key, a.value, _utc(a.time)) for a in notes])
    _insert(con, "dataset_members", [(a.id, a.meta.get("alias"), e) for a in arts if a.kind == "dataset"
                                     for e in (reg / f"datasets/{a.id}.txt").read_text().split()])
    vrows, lrows = aliases.all_aliases(reg)
    _insert(con, "aliases", vrows)
    _insert(con, "alias_labels", lrows)

    con.execute("INSERT INTO catalog_meta VALUES (?)", [_registry_head(reg)])
    con.close()
    tmp.replace(db)
    return db


def _is_current(machine: config.MachineConfig) -> bool:
    head = _registry_head(machine.registry)
    if head is None or not machine.catalog.is_file():
        return False
    try:
        with duckdb.connect(str(machine.catalog), read_only=True) as con:
            return con.execute("SELECT registry_head FROM catalog_meta").fetchone()[0] == head
    except duckdb.Error:
        return False


def connect(machine: config.MachineConfig | None = None) -> duckdb.DuckDBPyConnection:
    """Read-only connection to an up-to-date catalog."""
    machine = machine or config.load_machine()
    if not _is_current(machine):
        rebuild(machine)
    return duckdb.connect(str(machine.catalog), read_only=True)
