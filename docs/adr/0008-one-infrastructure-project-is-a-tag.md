# 0008. One infrastructure for all projects; the project is a field on every run

Status: Accepted (2026-11-10); amended by 0017 (W&B removed)
Covers: `src/prov/core/context.py` (`prov.toml`), `src/prov/runs/schema.py` (`project`), `src/prov/core/runenv.py` (`PROV_PROJECT`)
PR: https://github.com/v-sangli/prov/pull/2

## Context
Robot-learning projects share sessions, checkpoints and benchmarks. Separate registries or
stores per project would split lineage at exactly the points where projects reuse each other's
artifacts. Formerly design decision D8.

## Decision
- One machine config (`$PROV_CONFIG` or `~/.config/prov/config.toml`) names one registry, one
  store and one catalog for every project on the machine.
- A project is a repo with a `prov.toml`, found by walking up from the working directory:
  `project = "<name>"` (required) and `repos = [...]` (ADR 0005).
- `prov run` refuses to start without a `prov.toml`. The run record's required `project` field
  is that name; it is passed to the wrapped process as `PROV_PROJECT`, is the default W&B
  project (ADR 0003), and is a column of the catalog's `runs` table.
- Artifacts, episodes and datasets carry no project; they belong to the shared registry and are
  reached from a project through the runs that made or used them.
- Free-form key-value labels on a run are `--tag key=value` (`run_tags`), separate from the
  project.

Not built: `prov run --project`. The project comes only from `prov.toml`.

## Consequences
- Easier: one `prov q` sees every project; a checkpoint from one project is an input to another
  with no export.
- Harder: alias names are one namespace shared by every project.
- Rules out per-project registries and stores.

## Enforced by
- `tests/test_run.py::test_run_writes_record_and_commits_it` (`project == "demo"` from `prov.toml`)
- `tests/test_run.py::test_no_prov_toml`
- `tests/test_phase5.py::test_wandb_init_offline_records_run_path` (W&B project = prov project)
- `prov.runs.schema.RunRecord.project` is a required field.
