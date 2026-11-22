"""The DuckDB catalog: an index rebuilt from the registry. Deleting it loses nothing.

The tables are declared by the CatalogTables in `ctx.ext.tables` (one bundle per domain:
runs, artifacts, episodes, datasets); this module only builds and opens the database.
`catalog_meta` records the registry HEAD the catalog was built from; `connect()` rebuilds first
when the registry has moved since. All timestamps are naive UTC.
"""

from datetime import datetime, timezone
from pathlib import Path

import duckdb

from prov.core import log
from prov.storage import registry
from prov.storage.lock import RegistryLock

_log = log.get("catalog")


def utc(t: datetime | None) -> datetime | None:
    """Naive UTC: every catalog timestamp is UTC (avoids DuckDB's pytz dependency for TIMESTAMPTZ)."""
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t else None


def _insert(con: duckdb.DuckDBPyConnection, table: str, rows: list[tuple]) -> None:
    if rows:
        con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)


def rebuild(ctx) -> Path:
    db = ctx.catalog
    with RegistryLock(ctx.registry):
        db.parent.mkdir(parents=True, exist_ok=True)
        tmp = db.with_name(db.name + ".tmp")
        tmp.unlink(missing_ok=True)
        con = duckdb.connect(str(tmp))
        for bundle in ctx.ext.tables:
            con.execute(bundle.ddl)
        for bundle in ctx.ext.tables:
            for table, rows in bundle.rows(ctx).items():
                _insert(con, table, list(rows))
        con.execute("CREATE TABLE catalog_meta (registry_head VARCHAR)")
        con.execute("INSERT INTO catalog_meta VALUES (?)", [registry.head(ctx.registry)])
        con.close()
        tmp.replace(db)
    _log.debug("catalog rebuilt at %s", db)
    return db


def _is_current(ctx) -> bool:
    head = registry.head(ctx.registry)
    if head is None or not ctx.catalog.is_file():
        return False
    try:
        with duckdb.connect(str(ctx.catalog), read_only=True) as con:
            return con.execute("SELECT registry_head FROM catalog_meta").fetchone()[0] == head
    except duckdb.Error:
        return False


def connect(ctx) -> duckdb.DuckDBPyConnection:
    """Read-only connection to an up-to-date catalog."""
    if not _is_current(ctx):
        rebuild(ctx)
    return duckdb.connect(str(ctx.catalog), read_only=True)
