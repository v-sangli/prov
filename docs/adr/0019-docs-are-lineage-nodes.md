# 0019. Docs are lineage nodes; lineage walks one edges view

Status: Accepted (2026-11-21)
Covers: `packages/prov/src/prov/docs/`, `packages/prov/src/prov/lineage/graph.py`, `packages/prov/src/prov/storage/catalog.py`, `packages/prov/src/prov/core/extensions.py`, the `tables.py` of runs, artifacts, episodes and datasets, `packages/prov/src/prov/cli/docs.py`, `packages/prov-journal/src/prov_journal/`, `packages/prov-skills/src/prov_skills/journal/SKILL.md`
PR: https://github.com/v-sangli/prov/pull/6 (spec and plan 424357b)

## Context

Journal docs cite IDs as evidence, but prov did not know the docs: `prov uses ckpt_...` could not
say which docs rest on a checkpoint, and a doc had no ID of its own to be cited by. Lineage was
also per-kind code in `lineage/graph.py`: each new kind of edge meant new branches there.

## Decision

- A doc is a Markdown file inside a git repo with an ID `doc_<ULID>`, kept in its frontmatter as
  `id:`. `prov.docs` (layer 3) holds `DocRecord` (id, repo, remote, path, title, created,
  versions) and `DocVersion` (commit, dirty, registered, cites), stored at
  `records/docs/<doc_id>.yaml`.
- Everything counts as a citation: every prov ID and alias anywhere in the file; aliases
  resolve to IDs; the doc's own ID is not one. A cite not in the registry fails the
  registration before the file or the registry is touched. A version is appended only when
  (commit, dirty, cites) differs from the last.
- A file in no git repo is refused: "fold it into a journal first". Folding is an agent rule in
  the journal skill, not code. Registration is explicit: `prov doc register PATH...`, and
  `prov-journal register` for every dated journal doc; `prov-journal new` writes `id:`.
- Each `CatalogTables` bundle may contribute `nodes` SQL (`id, label`) and `edges` SQL
  (`src, rel, dst`); the catalog builds the views `nodes` and `edges` as their unions, adding
  `ord`, the bundle's position in the wiring. `prov.lineage` walks `edges` and labels from
  `nodes` with no per-kind code; a node's neighbours come in (`ord`, ID) order, which keeps the
  previous output order. Edges: `input` (runs), `produced` (artifacts), `parent` and `member`
  (datasets), `cites` (docs). Episodes are nodes, so docs can cite them.
- The catalog is current only when both the registry HEAD and a hash of every bundle's SQL
  match what it was built from (amends ADR 0002), so an upgrade that changes the tables
  rebuilds a stale catalog instead of failing on a missing view.
- The journal lint's known IDs are the `nodes` view, so docs may cite docs.
- Versions: prov 0.5.0, prov-journal 0.2.0, prov-skills 0.1.1.

## Consequences

- Easier: `prov trace doc_...` shows what a doc rests on; `prov uses <id>` lists the docs citing
  it; `prov q` can join `docs` and `doc_cites`.
- Easier: a new kind of lineage edge is SQL in its own bundle; `lineage/graph.py` is unchanged.
- Harder: a doc must live in a git repo, and every ID or alias-shaped string in it must exist.
- Changed: a run's downstream edges now come from its artifacts' `produced_by` (as upstream did)
  rather than from `run_outputs`; the two agree for every finished run.
- Variation axes: unchanged; catalog tables now also contribute nodes and edges.

## Enforced by

- `packages/prov/tests/test_phase5.py` (trace / uses output, unedited)
- `packages/prov/tests/test_extensions.py::test_new_catalog_edges_join_lineage`
- `packages/prov/tests/test_docs.py`
- `packages/prov/tests/test_layers.py` (`prov.docs` at layer 3)
- `packages/prov-journal/tests/test_journal.py::test_new_doc_has_a_doc_id`
- `packages/prov-journal/tests/test_journal.py::test_register_every_dated_doc`
- `packages/prov-journal/tests/test_journal.py::test_lint_knows_registered_doc_ids`
- `packages/prov/tests/test_extensions.py::test_catalog_rebuilds_when_its_tables_change`
