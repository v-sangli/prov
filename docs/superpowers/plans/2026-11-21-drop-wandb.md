# Drop W&B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** prov integrates by reference only: add `prov.refs()`, remove the W&B integration and the event system.

**Architecture:** `refs()` reads the run's env contract (`RunEnv`); nothing in prov imports a tool. The event system's only consumer was W&B, so it goes with it.

**Tech Stack:** Python 3.12, pytest, ruff 0.8.4.

## Global Constraints

- Version 0.2.0 → 0.3.0. Layers import downward only (`tests/test_layers.py`).
- Tests: `.venv/bin/python -m pytest -q`; lint: `uvx ruff@0.8.4 check src tests`.

## Contract

- Decision: prov imports none of the tools that use it; `prov.refs()` hands a run's IDs to any tool. W&B integration and the event system are removed.
- Sketch: the spec's "Agreed interface sketch", unchanged.
- Variation axes: "event subscribers" is removed; the others are unchanged.

---

### Task 1: `prov.refs()`

**Files:** Modify `src/prov/core/errors.py`, `src/prov/core/runenv.py`, `src/prov/api.py`, `src/prov/__init__.py`. Test: `tests/test_run.py`.

**Interfaces:** Produces `prov.refs() -> dict[str, str | list[str] | None]`, `RunEnv.inputs_so_far() -> list[str]`, `RunError(ProvError)`.

**Step 1: failing tests** (append to `tests/test_run.py`)

```python
def test_refs_outside_a_run_raises(registry, monkeypatch):
    import prov
    from prov.core.errors import RunError
    monkeypatch.delenv("PROV_RUN_ID", raising=False)
    with pytest.raises(RunError):
        prov.refs()


def test_refs_inside_a_run_lists_run_project_and_inputs(registry, monkeypatch, tmp_path):
    import prov
    inputs = tmp_path / "inputs"
    inputs.write_text("ds_A\nckpt_B\nds_A\n")
    monkeypatch.setenv("PROV_RUN_ID", "run_X")
    monkeypatch.setenv("PROV_PROJECT", "cube")
    monkeypatch.setenv("PROV_RUN_INPUTS", str(inputs))
    assert prov.refs() == {"prov_run": "run_X", "prov_project": "cube", "prov_inputs": ["ds_A", "ckpt_B"]}
```

**Step 2:** run them; expected FAIL (`AttributeError: module 'prov' has no attribute 'refs'`).

**Step 3: implement**

- `errors.py`: `class RunError(ProvError): pass` after `StoreError`.
- `runenv.py` `RunEnv`:

```python
    def inputs_so_far(self) -> list[str]:
        """Artifact IDs prov.load-ed so far in this run: load order, first occurrence kept."""
        if self.inputs is None or not self.inputs.is_file():
            return []
        return list(dict.fromkeys(line for line in self.inputs.read_text().splitlines() if line))
```

- `api.py`:

```python
def refs() -> dict[str, str | list[str] | None]:
    """The prov IDs that ground the current run, for any tool's config or metadata."""
    ctx = context()
    if ctx.run is None:
        raise RunError("prov.refs() needs a run: launch the script with `prov run`")
    return {"prov_run": ctx.run.run_id, "prov_project": ctx.run.project,
            "prov_inputs": ctx.run.inputs_so_far()}
```

  and add `"refs"` to `__all__` in `api.py` and `prov/__init__.py` (import too).

**Step 4:** run them; expected PASS. **Step 5:** commit "Add prov.refs()".

### Task 2: remove the W&B integration and the event system

**Files:** Delete `src/prov/integrations/wandb.py`, `src/prov/core/events.py`. Modify `src/prov/api.py` (drop `wandb_init`, both `events.emit`, the `_wandb` and `events` imports; `summary` docstring loses its W&B sentence), `src/prov/__init__.py`, `src/prov/wiring.py` (drop the wandb import and `subscribers=`), `src/prov/core/extensions.py` (drop `subscribers` and its docstring line), `src/prov/core/__init__.py` and `src/prov/integrations/__init__.py` (docstrings), `src/prov/core/runenv.py` (drop `WANDB`, the `wandb` field, `set_wandb`, its docstring line; `PROV_PROJECT` line drops "default W&B project"), `src/prov/runs/schema.py` (drop `wandb`), `src/prov/runs/wrapper.py` (drop the `wandb` file), `src/prov/runs/tables.py` (drop the `wandb` column and value), `src/prov/artifacts/publish.py` and `src/prov/episodes/ingest.py` (drop the emit; `publish` returns `_publish(...)` under the lock; `ingest` returns `(session, eps)` from `_ingest`, which loses the `published` flag), `pyproject.toml` (drop the `wandb` extra), `.github/workflows/ci.yml` and README (install `.[test,plot]`).
Tests: delete `tests/test_phase5.py::test_wandb_reference_artifacts_hold_paths_only`, `::test_wandb_failures_never_break_a_run`, `::test_wandb_init_offline_records_run_path`, `tests/test_extensions.py::test_subscriber_sees_events` (verdict: stale; the agreed change removes the behavior they pin).

**Step 1:** make the deletions and edits. **Step 2:** `grep -rn -i 'wandb\|events\|subscri' src tests` returns nothing. **Step 3:** full suite and lint pass. **Step 4:** commit "Remove the W&B integration and the event system".

### Task 3: records and docs

**Files:** Create `docs/adr/0017-integrate-by-reference-only.md`. ADR statuses: 0003 → "Superseded by 0017"; 0008, 0013, 0014, 0016 → "Accepted; amended by 0017" (their W&B lines). Modify `docs/adr/README.md`, README (package map, extending, axes), `docs/usage.md` (W&B lines → `prov.refs()`; `runs` table loses `wandb`; troubleshooting row removed), `pyproject.toml` 0.3.0.

**Step 1:** write them. **Step 2:** full suite and lint. **Step 3:** commit.
