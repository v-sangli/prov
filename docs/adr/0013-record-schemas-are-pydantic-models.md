# 0013. Record schemas are pydantic models, closed to unknown fields

Status: Accepted (2026-11-09); amended by 0017 (W&B removed)
Covers: `packages/prov/src/prov/core/schema.py`, `packages/prov/src/prov/runs/schema.py`, `packages/prov/src/prov/artifacts/schema.py`, `packages/prov/src/prov/episodes/schema.py`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Records are written by tools and read back by the catalog, lineage, W&B and reruns. A field
typed by hand or added ad hoc would break readers silently. Formerly design decision D13.

## Decision
- Every record type subclasses `core.schema.Record`, a pydantic `BaseModel` with
  `extra="forbid"`. The model is the record's only definition. YAML records are written with
  `to_yaml` (`model_dump(mode="json")`, keys in field order) and read with `from_yaml`; JSONL
  lines use `model_dump_json` / `model_validate_json`.
- The CLI reports validation errors as `prov: <message>`, exit 2.

Records today:
- `RunRecord`: `id`, `kind` (`collect` | `export` | `train` | `eval` | `analysis` | `other`),
  `project`, `started`, `finished`, `status` (`running` | `ok` | `failed` | `killed`),
  `exit_code`, `host`, `cwd`, `command` (argv list), `code` (list of `CodeState`, ADR 0005),
  `env` (`python`, `platform`, `gpu` list), `inputs`, `outputs`, `wandb`, `tags`, `summary`
  (str to number or string), `notes`. Written as `running` before the command starts, then
  rewritten and committed at exit; exit by signal N gives `killed`, exit 128+N.
- `ArtifactRecord`: `id`, `kind`, `uri` (null for datasets), `created`, `source` (path before
  publishing), `produced_by` (run ID), `meta` (free dict). A checkpoint folder also gets a copy
  of its record as `manifest.yaml`.
- `EpisodeRecord`, `EpisodeSource` and `Annotation` (`episode`, `key`, `value`, `time`):
  ADR 0009.

Kind-specific artifact `meta` is not schema'd: it is whatever the publisher passes, plus what
ingest, freeze and `save_figure` write. Benchmark specs have no schema until projects exist.

Not built: the run `config` field (`path`, `resolved`) and `env.cuda`. The uv lock is in the
code snapshot, not the record.

## Consequences
- Easier: a misspelt or unknown field fails on load, not downstream.
- Harder: adding a field is a schema change that every existing record must still satisfy (new
  fields need defaults).
- Rules out ad hoc fields on records; free-form data goes in `meta`, `tags` or `summary`.

## Enforced by
- `prov.core.schema.Record` (`extra="forbid"`) rejects unknown fields on every load; no test
  pins it directly.
- `packages/prov/tests/test_store.py::test_checkpoint_gets_manifest` (manifest validates as the record)
- `packages/prov/tests/test_run.py::test_run_writes_record_and_commits_it`, `::test_failed_command_status_and_exit_code`,
  `::test_missing_command_binary`
- `packages/prov/tests/test_episodes.py::test_ingest_v3_session` (`read_episodes` round-trips)
