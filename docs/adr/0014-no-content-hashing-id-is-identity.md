# 0014. No content hashing: the ID assigned at creation is the identity, and read-only folders keep artifacts from changing

Status: Accepted (2026-11-10); amended by 0017 (W&B removed)
Covers: `packages/prov/src/prov/artifacts/publish.py`, `packages/prov/src/prov/storage/store.py` (`make_read_only`), `packages/prov/src/prov/episodes/ingest.py`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Sessions and checkpoints run to many gigabytes; hashing them on every publish, and re-hashing to
verify, costs time and disk reads for little gain on one machine where the tools are the only
writers. What matters is that an ID always names the same bytes and that an episode can be
traced back to its recording. Formerly design decision D14.

## Decision
- Records carry no content hash. An artifact's identity is the `<prefix>_<ULID>` assigned when
  it is published or ingested (ADR 0004). A change is a new artifact with a new ID.
- After publishing, the artifact's store path is made read-only: write bits are cleared for
  user, group and other on the folder and everything in it (symlinks skipped). A checkpoint's
  `manifest.yaml` is written before this.
- Publishing a path already inside the store is refused.
- Re-ingest is matched by location, not content: a session's store folder, or a source path
  already recorded as a session's `source`, returns the existing session and episode IDs.
- Each episode references its origin: `source.kind = mcap` with the MCAP's `path`, `raw_` ID
  (when registered) and time range, or `teleop` (ADR 0009).
- W&B references use `checksum=False` for the same reason (ADR 0003).

## Consequences
- Easier: publishing costs a move, not a full read of the bytes.
- Harder: read-only is not tamper-proof; `chmod` stops accidents only, and nothing detects
  bytes that changed or vanished.
- Harder: the same bytes published twice get two IDs; identity is by creation, not content.
- Rules out content-addressed storage and deduplication.

## Enforced by
- `packages/prov/tests/test_store.py::test_published_folder_is_read_only`
- `packages/prov/tests/test_store.py::test_path_already_in_store`
- `packages/prov/tests/test_episodes.py::test_reingest_is_a_noop`
- `packages/prov/tests/test_episodes.py::test_source_map_references_mcap`
- No content hash: nothing mechanical; the user's review.
