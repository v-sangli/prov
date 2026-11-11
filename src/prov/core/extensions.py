"""The extension points. `prov.wiring` builds the Extensions bundle from the built-ins; tests and
future code add their own entries to a bundle the same way.

    CatalogTables   DDL plus a row source for some catalog tables (storage.catalog builds them)
    IngestFormat    reads a recording folder into session meta + episode rows (episodes.ingest)
    LintCheck       one journal rule (journal.lint)
    subscribers     event name -> functions called with (ctx, payload) (core.events)
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


@dataclass(frozen=True)
class IngestFormat:
    name: str
    # folder -> (session meta incl. "fps", [{"episode_index", "length", "tasks"}]); raises StoreError
    read: Callable[[Path], tuple[dict[str, Any], list[dict[str, Any]]]]


@dataclass(frozen=True)
class LintCheck:
    name: str
    check: Callable[[Any], list[str]]                    # JournalView -> ["path:line: message"]


@dataclass(frozen=True)
class Extensions:
    tables: list[CatalogTables] = field(default_factory=list)
    formats: dict[str, IngestFormat] = field(default_factory=dict)
    lint_checks: list[LintCheck] = field(default_factory=list)
    subscribers: dict[str, list[Callable[[Any, Any], None]]] = field(default_factory=dict)
