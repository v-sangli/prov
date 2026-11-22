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
