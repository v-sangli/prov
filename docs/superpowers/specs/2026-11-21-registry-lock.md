# Spec: one lock serializes registry writes

Branch: `feat/registry-lock` · Mode: `feat/` extend · Intake: full integration · Version: 0.2.0

## Problem

Several agents and processes write one registry on one machine. Nothing serializes them:

- `registry.commit` runs `git add` then `git commit`; two processes at once hit git's
  `index.lock` and one raises `CalledProcessError`.
- `datasets.freeze` reads the highest `ds:<name>/N`, computes `N+1`, writes and commits the
  dataset record and its members, and only then calls `aliases.set_version`. Two concurrent
  freezes pick the same N; the second fails at `set_version` after its record is committed,
  which leaves an orphan dataset in the registry.
- `aliases.set_version` / `set_label` read the alias file, modify it and write it back; two
  concurrent calls can lose an update.
- `catalog.rebuild` always builds into `catalog.duckdb.tmp`; two concurrent rebuilds collide.

ADR 0001 (registry) and ADR 0002 (catalog) never covered concurrent writers, so this is a
feature gap, not a bug.

## Contract

- Every operation that writes the registry or rebuilds the catalog holds one exclusive,
  registry-wide lock for the whole operation: from the first read its result depends on to
  its last commit.
- The lock is taken once, at the operation's entry. Code running under it does not take it
  again.
- The lock is never held while a user's command runs (`prov run`), so a script inside a run
  can publish.
- A process that cannot get the lock within the timeout fails loudly with `RegistryLocked`;
  it never proceeds unlocked.
- A crashed holder cannot leave a stale lock: the kernel releases `flock` when the process
  exits.
- Readers do not lock: records are written atomically (temp file + rename) and the catalog
  is swapped in by rename.

## Variation axes

None new. The lock is one concrete `fcntl.flock` implementation (Linux and macOS, one
machine); no lock backend axis until a second variant is real.

## Out of scope

Locking across machines, pushing the registry, and locks on project repos for code snapshots.

## Agreed interface sketch (2026-11-21)

```python
# src/prov/core/layout.py
def registry_lock(registry: Path) -> Path: ...        # <registry>/.prov.lock

# src/prov/core/errors.py
class RegistryLocked(ProvError): ...                   # timeout reached; names the lock path

# src/prov/storage/lock.py     (L1, new)
class RegistryLock:
    TIMEOUT_S: float = 60.0
    def __init__(self, registry: Path, timeout_s: float = TIMEOUT_S) -> None: ...
    def __enter__(self) -> "RegistryLock": ...        # waits up to timeout_s, else RegistryLocked
    def __exit__(self, *exc) -> None: ...
```

Taken once at each write operation's entry; code under it calls the unlocked internals
(non-reentrant, so an accidental nesting fails loudly after the timeout):

| Operation | Holds the lock around |
|---|---|
| `artifacts.publish` | the whole publish (bytes placed, record written and committed, alias set); `artifact.published` is emitted after release. Unlocked internal: `_publish` |
| `datasets.freeze` | version pick → records → members → `aliases._set_version`; the catalog selection runs before the lock |
| `episodes.ingest` | the whole ingest, publishing the session through `_publish`; the event is emitted after release |
| `episodes.annotate` | lookup, append and commit |
| `aliases.set_version` / `set_label` | read → modify → write → commit. Unlocked internals: `_set_version` / `_set_label` |
| `runs.records.write` | each write of the run record; never while the user's command runs |
| `catalog.rebuild` | the build and the swap |

Lock file: `<registry>/.prov.lock`, untracked; the registry's `.gitignore` lists it.
