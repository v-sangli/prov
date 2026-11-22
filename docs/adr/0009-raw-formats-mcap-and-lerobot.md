# 0009. Raw formats are MCAP (exported to LeRobot) and LeRobot written directly by teleop

Status: Accepted (2026-11-10)
Covers: `src/prov/episodes/`, `src/prov/cli/episodes.py`, `src/prov/core/extensions.py` (`IngestFormat`)
PR: https://github.com/v-sangli/prov/pull/2

## Context
Recordings arrive two ways: teleop writes LeRobot folders directly, and other rigs record MCAP,
which training cannot read and must be exported to LeRobot. Training (LeRobot, GR00T) reads
LeRobot. Both paths must end as sessions with per-episode IDs, and an exported episode must
point back at its MCAP. Formerly design decision D9.

## Decision
- MCAP recordings are `raw_` artifacts (`prov publish --kind raw`, store `raw/<raw_id>/`).
- LeRobot folders become `ses_` artifacts through `prov ingest lerobot <dir>`
  (`episodes/ingest.py`), with one `ep_` ID per episode. Formats are `IngestFormat`s listed in
  `wiring.py`; the one built in is `episodes/formats/lerobot.py`, reading LeRobot v2.x
  (`meta/episodes.jsonl`) and v3.0 (`meta/episodes/**/*.parquet`).
- Session `meta` from LeRobot: `format`, `codebase_version`, `robot_type`, `fps`, `cameras`
  (video features), `total_episodes`, `total_frames`, plus any `--meta k=v`.
- Episode record (one JSONL line in `records/episodes/<ses_id>.jsonl`): `id`, `session`,
  `episode_index` (position in the folder, not an identity), `length`, `fps`, `duration_s`,
  `tasks`, `source`, `calibrations` (ADR 0015).
- `source` is `{kind: teleop}` or, from a `--source-map` JSONL (one line per episode:
  `episode_index` plus any of `path`, `raw`, `start_s`, `end_s`), `{kind: mcap, raw, path,
  start_s, end_s}`. A source map missing any episode is refused.
- The folder is read and the source map checked before anything moves. Re-ingest of the same
  source path, or of the session's store folder, returns the existing session and episodes.
- `prov annotate <ep_id> key=value ...` appends labels (outcome, failure_type, tags, note, ...)
  to `records/annotations/<ses_id>.jsonl`; the latest value per (episode, key) wins.

Not built: the MCAP to LeRobot exporter that writes the source map (and its `export` run).
Episodes record no capture metadata beyond the fields above.

## Consequences
- Easier: demonstrations and robot rollouts share lookup, annotation and lineage.
- Easier: a new recording format is one module and one line in `wiring.py`.
- Harder: MCAP data is not usable for training until the exporter exists.
- Rules out training directly from MCAP.

## Enforced by
- `tests/test_episodes.py::test_ingest_v3_session`, `::test_ingest_v2_session`
- `tests/test_episodes.py::test_source_map_references_mcap`
- `tests/test_episodes.py::test_incomplete_source_map_moves_nothing`
- `tests/test_episodes.py::test_not_lerobot_moves_nothing`
- `tests/test_episodes.py::test_reingest_is_a_noop`
- `tests/test_episodes.py::test_annotations_latest_wins`, `::test_cli_ingest_annotate_q`
- `tests/test_extensions.py::test_new_ingest_format`
