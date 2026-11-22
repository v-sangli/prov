# 0003. W&B holds runs and curves; artifacts reach it as references to registry records

Status: Accepted (2026-11-10)
Covers: `src/prov/integrations/wandb.py`, `src/prov/api.py` (`wandb_init`, `summary`), `src/prov/core/events.py`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Training curves and eval summaries are best viewed online, and an online lineage graph helps.
But there is no cloud artifact storage (one machine holds the bytes), and W&B lists a referenced
folder file by file, so referencing a store folder would bloat the manifest. MLflow (local or
hosted) would duplicate both W&B and the registry. Formerly design decision D3.

## Decision
- W&B (online) holds runs, curves and summaries. MLflow is not used.
- `prov.wandb_init(**kwargs)` calls `wandb.init` with `project` defaulting to the prov project
  and `config["prov"] = {run_id, inputs}`. Inside `prov run` the W&B run path is written to the
  run record's `wandb` field (through `PROV_RUN_WANDB`).
- The integration hears about artifacts only through events (`artifact.loaded`,
  `artifact.published`, `run.summary`); lower layers never import it.
- While a W&B run is active, `prov.load` calls `use_artifact` and `prov.publish` calls
  `log_artifact` with a W&B artifact whose only content is
  `add_reference("file://<registry>/records/artifacts/<kind>/<id>.yaml", checksum=False)`.
  Type = the prov kind; name = the alias name (or the ID when there is no alias), with characters
  outside `[A-Za-z0-9._-]` replaced by `-`; metadata = `prov_id`, `prov_alias`, `uri`. No bytes
  are read or uploaded.
- Inputs loaded before `wandb_init` are queued and logged when it starts.
- `use_artifact` / `log_artifact` failures are logged as warnings and never fail the run.
  Failures in `wandb_init` itself or in the summary update are not caught.
- `prov.summary(...)` values also go to the W&B run summary.
- The registry stays the source of truth; W&B is a view.

Not checked: the online W&B lineage graph with a real account; tests use a fake run and offline
mode.

## Consequences
- Easier: online curves and a lineage graph with nothing uploaded.
- Harder: W&B artifacts point at a local file, so they are meaningless off this machine.
- Rules out uploading artifact bytes to W&B and using MLflow.

## Enforced by
- `tests/test_phase5.py::test_wandb_reference_artifacts_hold_paths_only`
- `tests/test_phase5.py::test_wandb_failures_never_break_a_run`
- `tests/test_phase5.py::test_wandb_init_offline_records_run_path`
- `tests/test_extensions.py::test_subscriber_sees_events`
- `tests/test_layers.py::test_imports_go_down` (integrations sit above artifacts)
