# 0002. DuckDB is the query engine, rebuilt from registry records only

Status: Accepted (2026-11-10)
Covers: `packages/prov/src/prov/storage/catalog.py`, `packages/prov/src/prov/*/tables.py`, `packages/prov/src/prov/lineage/`, `packages/prov/src/prov/cli/query.py`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Records are many small text files in git (ADR 0001); finding "failed grasps in dataset 3" or
"every eval on benchmark 2" needs joins. A database that is itself a source of truth would have
to be backed up and kept in sync. LeRobot folders hold their own metadata, but reading the store
at query time ties queries to bytes that may be on another disk. Formerly design decision D2.

## Decision
- The catalog is one DuckDB file at the machine config's `catalog` key (default
  `~/.cache/prov/catalog.duckdb`). It is an index: deleting it loses nothing.
- It is built only from registry files. LeRobot metadata is read once, at ingest, into episode
  records; the catalog never reads the store.
- `rebuild` writes to `<catalog>.tmp` and renames it into place. It stores the registry HEAD in
  `catalog_meta`; `catalog.connect(ctx)` rebuilds first whenever the HEAD differs (or the
  registry has no commits), then opens read-only. `prov q` and `prov catalog rebuild` use these.
- Timestamps are stored as naive UTC.
- Tables are declared per domain as a `CatalogTables` bundle (`core/extensions.py`), listed in
  `wiring.py`:
  - runs: `runs`, `run_code`, `run_inputs`, `run_outputs`, `run_tags`, `run_summary` (one row per
    run and key; `value` DOUBLE or NULL, `text` always the string)
  - artifacts: `artifacts` (with resolved store `path`), `aliases` (ref, kind, name, version,
    id), `alias_labels` (ref, kind, name, label, version)
  - episodes: `episodes` (with `source_kind`, `source_raw`, `source_path`, `start_s`, `end_s`,
    `calibrations`), `annotation_log`, and the `annotations` view (latest value per episode and
    key)
  - datasets: `dataset_members` (`dataset` = ds ID, `alias`, `episode`)
- `run_inputs` / `run_outputs` hold IDs, never aliases. Filtering by an alias joins `aliases`
  (`JOIN aliases al ON al.id = i.artifact AND al.ref = 'bench:cube-holdout/1'`); filtering a
  dataset by alias uses `dataset_members.alias`.
- Lineage (`lineage/graph.py`, `prov trace` / `prov uses`) walks the catalog: artifact <- its
  `produced_by` run; run <- its inputs; dataset <- its parent and the sessions of its member
  episodes; session <- its producing run. Episodes are not nodes; a dataset node reports its
  episode and session counts, a run node its repos, base commits and dirty flags.

## Consequences
- Easier: ad hoc SQL over everything; lineage is a few queries.
- Easier: the catalog can be deleted or moved at will; queries never see stale data.
- Harder: every query after a registry commit pays a full rebuild.
- Rules out writing anything only to the catalog.

## Enforced by
- `packages/prov/tests/test_episodes.py::test_rebuild_from_scratch_is_identical`
- `packages/prov/tests/test_episodes.py::test_connect_rebuilds_after_registry_changes`
- `packages/prov/tests/test_datasets.py::test_catalog_tables_and_failure_query`
- `packages/prov/tests/test_phase5.py::test_summary_recorded_later_values_win`
- `packages/prov/tests/test_phase5.py::test_trace_figure_reaches_episodes_and_commits`
- `packages/prov/tests/test_phase5.py::test_uses_session_reaches_figure`
- `packages/prov/tests/test_extensions.py::test_new_catalog_table`
