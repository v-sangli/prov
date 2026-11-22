# 0016. One registry-wide lock serializes every registry write

Status: Accepted (2026-11-21)
Covers: `src/prov/storage/lock.py`, `src/prov/core/layout.py`, `src/prov/artifacts/publish.py`, `src/prov/artifacts/aliases.py`, `src/prov/datasets/freeze.py`, `src/prov/episodes/ingest.py`, `src/prov/episodes/annotate.py`, `src/prov/runs/records.py`, `src/prov/storage/catalog.py`
PR: https://github.com/v-sangli/prov/pull/3 (spec f0dd585, plan d78538a)

## Context

Several agents and processes write one registry on one machine (0001). Nothing serialized
them:

- Concurrent commits hit git's `index.lock`, and one of them failed.
- Two concurrent `freeze` calls picked the same `ds:<name>/N`. The loser failed at the alias
  after its dataset record was committed, which left an orphan.
- Alias read-modify-writes could lose an update.
- Concurrent catalog rebuilds (0002) shared one temp file.

## Decision

- `prov.storage.lock.RegistryLock(registry, timeout_s=60.0)` holds `fcntl.flock` on
  `<registry>/.prov.lock`. The kernel releases it when its holder exits, so a crashed holder
  leaves no stale lock. If the lock is not acquired within `timeout_s`, it raises
  `RegistryLocked`; a writer never proceeds unlocked.
- The lock is taken once, at each write operation's entry, for the whole operation:

  | Operation | Holds the lock around |
  |---|---|
  | `artifacts.publish` | the whole publish: bytes placed, record written and committed, alias set |
  | `episodes.ingest` | the whole ingest, publishing its session through `_publish` |
  | `datasets.freeze` | version pick → records → members → alias; the catalog selection runs first, unlocked |
  | `episodes.annotate` | lookup, append, commit |
  | `aliases.set_version` / `set_label` | read → modify → write → commit |
  | `runs.records.write` | each record write; never while a `prov run` command runs |
  | `catalog.rebuild` | the build and the swap |

- The lock is not reentrant. Code that already holds it calls the unlocked internals:
  `publish._publish`, `aliases._set_version`, `aliases._set_label`, `ingest._ingest`. A
  mistaken nesting fails with `RegistryLocked` after the timeout.
- `artifact.published` is emitted after the lock is released, so subscribers such as W&B
  (0003) never hold it.
- Readers take no lock: records are written atomically and the catalog is swapped in by
  rename.
- `.prov.lock` is untracked; the registry's ignore rules list it (README setup).

## Consequences

- Concurrent agents can publish, ingest, freeze, annotate and rerun against one registry.
- A slow `copy=True` publish or ingest of a large folder blocks other writers for as long
  as it runs, and a writer that waits longer than 60 s fails with `RegistryLocked`. The
  default, a move, is a rename.
- One machine only. Locking across machines and pushing the registry are out of scope.

## Enforced by

- `tests/test_lock.py::test_nested_acquire_fails_loudly`
- `tests/test_lock.py::test_lock_excludes_other_processes_and_dies_with_its_holder`
- `tests/test_lock.py::test_concurrent_publishes_all_commit`
- `tests/test_lock.py::test_concurrent_freezes_number_versions_without_orphans`
