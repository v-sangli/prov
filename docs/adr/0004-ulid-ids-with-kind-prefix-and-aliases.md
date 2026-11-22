# 0004. IDs are ULIDs with a kind prefix; readable aliases sit on top

Status: Accepted (2026-11-10)
Covers: `src/prov/core/ids.py`, `src/prov/artifacts/aliases.py`, `src/prov/cli/artifacts.py` (`alias`)
PR: pending

## Context
Records reference each other by ID, so an ID must be unique without coordination, readable
enough to tell its kind at a glance, and usable in free text (journal docs). People also need
stable names like "dataset 3" and moving names like "the best model", and a version must never
be confused with a label. Formerly design decision D4.

## Decision
IDs are `<prefix>_<ULID>`: 48 bits of milliseconds plus 80 random bits, 26 Crockford base32
characters, so they sort by creation time. `kind_of(id)` rejects anything else.

| Kind | Prefix | Kind | Prefix |
| --- | --- | --- | --- |
| run | `run_` | benchmark | `bench_` |
| session | `ses_` | result | `res_` |
| episode | `ep_` | figure | `fig_` |
| dataset | `ds_` | video | `vid_` |
| checkpoint | `ckpt_` | raw | `raw_` |
| calibration | `calib_` | | |

Aliases (`artifacts/aliases.py`), two forms:
- `<kind>:<name>/<version>`: a numbered version, set once, resolves to exactly one ID forever.
  Setting it again to the same ID is a no-op; to another ID is refused.
- `<kind>:<name>@<label>`: a moving label that points at a version of the same name, never at an
  ID directly. Every move is a registry commit (`label <ref> -> <v> (was <old>)`), so a label's
  history is `git log aliases/<kind>/<name>.yaml`.
- Syntax: name `[A-Za-z0-9][A-Za-z0-9._-]*`; version starts with a digit
  (`[0-9][A-Za-z0-9.]*`); label starts with a letter (`[A-Za-z][A-Za-z0-9._-]*`).
- Alias kinds and the artifact kind they must name: `ds` dataset, `model` checkpoint, `bench`
  benchmark, `calib` calibration, `ses` session, `res` result, `fig` figure. A version whose ID
  is of another kind is refused. There are no aliases for runs, episodes, videos or raw
  recordings.
- File: `aliases/<kind>/<name>.yaml` with `versions: {"1": <id>}` and `labels: {<label>: "1"}`.
- Set by `prov alias set|label|show`, by `prov publish --alias` / `prov.publish(alias=...)`
  (checked before anything moves, set after), and by dataset freeze (ADR 0001).
- Anywhere a reference is taken (`prov.load`, `show`, `trace`, `uses`, journal evidence), an ID
  or an alias is accepted; aliases resolve to IDs before they are recorded.

## Consequences
- Easier: IDs need no counter or server; journals and records stay greppable by prefix.
- Easier: `ds:x/3` means the same thing forever; labels carry the "current" meaning.
- Harder: a new artifact kind means a prefix in `core/ids.py`, a store folder in `core/layout.py`
  and, if it needs names, an alias kind.
- Rules out repointing a numbered version.

## Enforced by
- `tests/test_ids.py::test_format_and_kind`, `::test_unique`, `::test_sorts_by_creation_time`,
  `::test_rejects_bad_ids`
- `tests/test_datasets.py::test_parse`, `::test_parse_rejects`
- `tests/test_datasets.py::test_versions_never_change`
- `tests/test_datasets.py::test_labels_move_and_history_is_git_log`
- `tests/test_datasets.py::test_resolve`
- `tests/test_datasets.py::test_publish_alias_checked_before_moving`
- `tests/test_datasets.py::test_cli_dataset_and_alias`
