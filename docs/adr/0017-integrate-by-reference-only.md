# 0017. prov integrates by reference only; the W&B integration and the event system go

Status: Accepted (2026-11-21)
Covers: `src/prov/api.py`, `src/prov/core/runenv.py`, `src/prov/core/extensions.py`, `src/prov/runs/`, `src/prov/wiring.py`
PR: pending

## Context

prov is the reference grounding for a development and research workspace: any ID resolves to
what it is, and its lineage and references can be walked. ADR 0003 had prov call W&B itself:
`prov.wandb_init`, W&B reference artifacts logged on every load and publish, and the summary
mirrored to W&B, all through an event system whose only subscriber was W&B. That inverted the
dependency: prov knew about a tool that uses it.

## Decision

- prov imports none of the tools that use it. A tool carries prov IDs in its own config or
  metadata.
- `prov.refs()` returns the IDs that ground the current run, as a plain dict:
  `{"prov_run": "run_...", "prov_project": "<project>", "prov_inputs": ["ds_...", ...]}`. The
  inputs are the artifacts `prov.load`-ed so far, in load order, without duplicates. Outside
  `prov run` it raises `RunError`. For example:
  `wandb.init(config={**cfg, **prov.refs()})`.
- Removed: `prov.wandb_init`, `prov.integrations.wandb`, the run record's `wandb` field, the
  `runs.wandb` catalog column, `PROV_RUN_WANDB`, the `wandb` extra.
- Removed with it: the event system (`prov.core.events`, `Extensions.subscribers`, every
  `emit`). "Event subscribers" is no longer a variation axis.
- `prov.summary` records into the run only.

Supersedes ADR 0003. Amends:

- ADR 0008: the project is no longer the default W&B project. Its "Enforced by" entry
  `test_wandb_init_offline_records_run_path` is deleted with the integration.
- ADR 0013: run records have no `wandb` field.
- ADR 0014: W&B's `checksum=False` no longer applies.
- ADR 0016: there is no event to emit after the lock.

## Consequences

- prov has no third-party runtime dependency beyond pydantic, PyYAML and DuckDB.
- W&B no longer draws prov lineage; prov's own `trace` and `uses` are the lineage view.
- Existing run records lose their `wandb` key: records are closed to unknown fields
  (ADR 0013), so a record still carrying it fails to load until the key is removed.

## Enforced by

- `tests/test_run.py::test_refs_outside_a_run_raises`
- `tests/test_run.py::test_refs_inside_a_run_lists_run_project_and_inputs`
- `tests/test_layers.py::test_imports_go_down`, together with the `wandb` extra being gone: an
  import of `wandb` anywhere in prov fails in CI.
