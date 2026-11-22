# 0010. No backup disk is assumed; git repos pushed to private GitHub remotes are the only off-machine copy

Status: Accepted (2026-11-10)
Covers: `src/prov/runs/snapshot.py` (ref push), `src/prov/storage/registry.py`
PR: pending

## Context
There is one machine and no second disk. Cloud artifact storage is out (bytes stay on this
machine). What must survive a disk failure is the text: records, journals and the code each run
used. Formerly design decision D10.

## Decision
- Text lives in git repos with private GitHub remotes: the registry, each project repo (code,
  `prov.toml`, journal) and this repo.
- Code snapshots reach the remote: `prov run` pushes `refs/prov/<run_id>` to `origin` at run
  start, so uncommitted and local-only code survives a lost disk (ADR 0005). A failed push is
  recorded as `pushed: false`, not raised.
- Registry records are committed by prov on every write, but prov does not push the registry;
  pushing it is the user's job.
- Store bytes (raw MCAP, sessions, checkpoints, results, figures, media) have no off-machine copy.
  Journal figure PNGs copied beside a doc (ADR 0007) travel with the project repo.

Not built: registry `blobs/` (copies of small results, up to 5 MB per run, so they would survive
a disk failure). Results today exist only in the store.

## Consequences
- Easier: nothing to operate beyond `git push`.
- Harder: one disk failure loses all raw data, sessions, checkpoints and videos; records then
  describe bytes that are gone.
- Harder: a registry that is not pushed is not protected.
- Rules out cloud storage of artifact bytes.

## Enforced by
- `tests/test_gitsnap.py::test_ref_reaches_remote`
- `tests/test_run.py::test_run_writes_record_and_commits_it` (`pushed` true with an origin)
- Registry push and the absence of a backup: nothing mechanical; the user's review.
