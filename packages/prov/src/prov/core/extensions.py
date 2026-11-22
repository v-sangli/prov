"""The extension points. `prov.wiring` builds the Extensions bundle from the built-ins; tests and
future code add their own entries to a bundle the same way.

    CatalogTables   DDL plus a row source for some catalog tables (storage.catalog builds them),
                    and the lineage nodes and edges they contribute
    IngestFormat    reads a recording folder into session meta + episode rows (episodes.ingest)
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CatalogTables:
    name: str
    ddl: str                                             # CREATE TABLE / VIEW statements
    rows: Callable[[Any], dict[str, Iterable[tuple]]]    # ctx -> {table: rows}
    nodes: str = ""                                      # SELECT id, label ... ("" = none)
    edges: str = ""                                      # SELECT src, rel, dst ... ("" = none)


@dataclass(frozen=True)
class IngestFormat:
    name: str
    # folder -> (session meta incl. "fps", [{"episode_index", "length", "tasks"}]); raises StoreError
    read: Callable[[Path], tuple[dict[str, Any], list[dict[str, Any]]]]


@dataclass(frozen=True)
class Extensions:
    tables: list[CatalogTables] = field(default_factory=list)
    formats: dict[str, IngestFormat] = field(default_factory=dict)
