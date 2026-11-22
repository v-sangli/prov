# 0001. A custom registry, not DVC or MLflow, owns records and dataset versions

Status: Accepted (2026-11-09)
Covers: `src/prov/core/layout.py`, `src/prov/storage/registry.py`, `src/prov/datasets/`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Every number, figure, model and dataset must trace back to what made it, across all projects,
without people typing commit hashes or paths. Datasets are selections of episodes spread over
many recording sessions; copying bytes per version is too expensive on one disk. DVC and MLflow
each cover part of this and bring their own storage model. Formerly design decision D1.

## Decision
The `prov` package (this repo) writes all records into a separate git repo, the registry. The
registry is the source of truth; it holds text only.

Registry layout (`core/layout.py` is the one place these paths are built):

```
records/runs/<run_id>.yaml
records/artifacts/<kind>/<id>.yaml
records/episodes/<ses_id>.jsonl       one EpisodeRecord per line, written at ingest
records/annotations/<ses_id>.jsonl    append-only, latest value per (episode, key) wins
datasets/<ds_id>.txt                  member episode IDs, one per line, sorted
aliases/<alias kind>/<name>.yaml      versions and labels (ADR 0004)
```

- Writes are atomic (temp file, then rename); annotation files are appended to.
- Each write is committed by `storage.registry.commit` under the identity `prov <prov@localhost>`.
  When the registry has no `.git`, the commit is silently skipped.
- prov never pushes the registry; pushing it to its private remote is done by hand (ADR 0010).

Dataset versions (`datasets/freeze.py`, `prov dataset freeze`):
- A version is a `ds_` artifact record with `uri: null` plus its members file. No bytes are
  copied. Its `meta` holds `alias`, `name`, `version`, `role` (`all` / `train` / `holdout`),
  `parent` (ds ID or null), `siblings` ({role: ds ID}), `episodes` and `sessions` (counts),
  `selection` (the query text, or "explicit list"), `split` and `notes`.
- Episodes come from an explicit ID list or a catalog SQL query (first column). Every ID must be
  a registered episode; an empty selection is refused. The resulting IDs are stored, not the
  filter, so later annotations never change a frozen version.
- Versions are numbered 1, 2, 3 ... per name (highest numeric version + 1) and aliased
  `ds:<name>/<n>`. With `--holdout F` the same number also goes to `ds:<name>-train/<n>` and
  `ds:<name>-holdout/<n>`.
- Split by episode holds out `round(F * n)` episodes (at least one); split by session holds out
  whole sessions in shuffled order until at least `F * n` episodes are held, and refuses to hold
  out everything. Both are deterministic for a seed (`random.Random(seed)`).
- `prov.dataset_sessions(ref)` returns `{ses_id: [episode_index]}` for loading with
  `MultiLeRobotDataset` straight from `store/sessions`.
- A freeze does not record itself as a run output: `produced_by` stays unset even inside
  `prov run`.

Not built: registry `blobs/` (copies of small results), and materialised dataset folders
(`store/datasets/` exists as a kind folder but freeze never writes to it).

## Consequences
- Easier: one versioning model for every artifact kind; a dataset version is a small text diff.
- Easier: history of every record is `git log` on the registry.
- Harder: prov carries its own versioning code and tests instead of borrowing a tool's.
- Rules out DVC and MLflow as dataset or model registries.

## Enforced by
- `tests/test_datasets.py::test_freeze_numbers_versions_and_old_versions_stay`
- `tests/test_datasets.py::test_freeze_rejects_bad_selection`
- `tests/test_datasets.py::test_split_by_episode`
- `tests/test_datasets.py::test_split_by_session`
- `tests/test_datasets.py::test_dataset_sessions_for_lerobot`
- `tests/test_store.py::test_publish_moves_folder_under_its_id` (record committed, registry clean)
- Not using DVC or MLflow: nothing mechanical; the user's review.
