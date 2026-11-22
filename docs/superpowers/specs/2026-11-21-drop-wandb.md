# Spec: prov integrates by reference only; the W&B integration goes

Branch: `feat/drop-wandb` · Mode: `feat/` (changes the contract) · Version: 0.3.0

## Decision being implemented

prov is the reference grounding for the workspace. It imports none of the tools that use it;
other tools carry prov IDs in their own configs and metadata. The W&B integration (ADR 0003)
inverts that and is removed.

## Contract

- Removed: `prov.wandb_init`, `prov.integrations.wandb` (reference artifacts on load and
  publish, the summary mirror), `RunEnv.wandb` / `PROV_RUN_WANDB`, `RunRecord.wandb`, the
  `runs.wandb` catalog column, the `wandb` extra.
- Added: `prov.refs()`, the IDs that ground the current run, as a plain dict for any tool's
  config or metadata. It imports no tool.
- `prov.summary` records into the run only.
- ADR 0017 supersedes ADR 0003 and amends the W&B lines of ADR 0008 and ADR 0013.
- Migration: existing run records drop their `wandb` key (one record in `~/registry`).

## Variation axes

The event-subscriber axis loses its only implementation (W&B); see the sketch.

## Agreed interface sketch (2026-11-21; events option A)

```python
# src/prov/api.py
def refs() -> dict[str, str | list[str] | None]:
    """{"prov_run": "run_...", "prov_project": "cube-grasp", "prov_inputs": ["ds_...", ...]}
    inputs = artifacts prov.load-ed so far in this run, load order, deduplicated.
    Raises RunError outside `prov run`."""

# src/prov/core/runenv.py
class RunEnv:                 # wandb field and PROV_RUN_WANDB removed
    def inputs_so_far(self) -> list[str]: ...

# src/prov/core/errors.py
class RunError(ProvError): ...
```

Removed besides W&B (option A): the event system — `core/events.py`,
`Extensions.subscribers`, the subscriber wiring and every `events.emit` call; "event
subscribers" leaves the README's variation axes.
