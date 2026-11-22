# Registry Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Serialize every registry write and catalog rebuild behind one registry-wide `flock`, so concurrent agents never collide on git or race on versions.

**Architecture:** A `RegistryLock` context manager in `prov.storage.lock` (layer 1) locks `<registry>/.prov.lock`. Each write operation takes it once at its entry; operations that call other write operations use their unlocked internals (`_publish`, `_set_version`, `_set_label`). Events fire after release.

**Tech Stack:** Python 3.12, `fcntl.flock`, pytest, subprocess for multi-process tests.

## Global Constraints

- Layers import downward only (`tests/test_layers.py`); `prov.storage` is layer 1 and imports core only.
- Version: 0.1.2 → 0.2.0.
- No reentrancy, no fallback: a writer that cannot get the lock within `timeout_s` raises `RegistryLocked`.
- Run tests with `.venv/bin/python -m pytest -q`; lint with `uvx ruff@0.8.4 check src tests`.

## Contract

- Decision: one exclusive, registry-wide `flock` is held for each whole write operation, taken once at its entry; never held while a user's command runs; failing to get it in 60 s raises `RegistryLocked`.
- Sketch: as agreed, in the spec (`docs/superpowers/specs/2026-11-21-registry-lock.md`, "Agreed interface sketch"), unchanged.
- Variation axes: none new; the lock is one concrete `fcntl.flock` implementation.

---

### Task 1: `RegistryLock`

**Files:**
- Modify: `src/prov/core/layout.py` (add `registry_lock`, document the file in the module docstring)
- Modify: `src/prov/core/errors.py` (add `RegistryLocked`)
- Create: `src/prov/storage/lock.py`
- Modify: `src/prov/storage/__init__.py` (list `lock`)
- Test: `tests/test_lock.py`

**Interfaces:**
- Produces: `prov.storage.lock.RegistryLock(registry: Path, timeout_s: float = 60.0)` (context manager), `prov.core.errors.RegistryLocked(ProvError)`, `prov.core.layout.registry_lock(registry: Path) -> Path`.

**Step 1: Write the failing tests** (`tests/test_lock.py`)

```python
import subprocess
import sys

import pytest

from prov.core.errors import RegistryLocked
from prov.storage.lock import RegistryLock

HOLD = """
import sys, time
from pathlib import Path
from prov.storage.lock import RegistryLock
with RegistryLock(Path(sys.argv[1])):
    print("held", flush=True)
    time.sleep(60)
"""


def test_nested_acquire_fails_loudly(registry):
    with RegistryLock(registry):
        with pytest.raises(RegistryLocked, match=".prov.lock"):
            with RegistryLock(registry, timeout_s=0.2):
                pass


def test_lock_excludes_other_processes_and_dies_with_its_holder(registry):
    p = subprocess.Popen([sys.executable, "-c", HOLD, str(registry)], stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "held"
        with pytest.raises(RegistryLocked):
            with RegistryLock(registry, timeout_s=0.2):
                pass
    finally:
        p.kill()
        p.wait()
    with RegistryLock(registry, timeout_s=2):
        pass
```

**Step 2:** Run `.venv/bin/python -m pytest -q tests/test_lock.py`. Expected: FAIL, `ModuleNotFoundError: prov.storage.lock`.

**Step 3: Implement**

`src/prov/core/errors.py`, after `StoreError`:

```python
class RegistryLocked(ProvError):
    pass
```

`src/prov/core/layout.py`: add `from pathlib import Path`, the line `    .prov.lock                               the write lock (untracked)` under `registry/` in the docstring, and:

```python
LOCK_FILE = ".prov.lock"


def registry_lock(registry: Path) -> Path:
    return registry / LOCK_FILE
```

`src/prov/storage/lock.py`:

```python
"""One exclusive lock per registry, held for a whole write operation.

`fcntl.flock` on `<registry>/.prov.lock`. The kernel releases it when its holder exits, so a crash
leaves no stale lock. Not reentrant: code that already holds it calls the unlocked internals, and
an accidental nesting fails with RegistryLocked after the timeout.
"""

import fcntl
import time
from pathlib import Path

from prov.core import layout
from prov.core.errors import RegistryLocked

_POLL_S = 0.05


class RegistryLock:
    TIMEOUT_S: float = 60.0

    def __init__(self, registry: Path, timeout_s: float = TIMEOUT_S) -> None:
        self.path = layout.registry_lock(registry)
        self.timeout_s = timeout_s

    def __enter__(self) -> "RegistryLock":
        self._file = open(self.path, "a")
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._file.close()
                    raise RegistryLocked(f"{self.path} still held after {self.timeout_s:g}s")
                time.sleep(_POLL_S)

    def __exit__(self, *exc) -> None:
        fcntl.flock(self._file, fcntl.LOCK_UN)
        self._file.close()
```

`src/prov/storage/__init__.py` docstring: add `lock      the registry-wide write lock (flock)`.

**Step 4:** Run `.venv/bin/python -m pytest -q tests/test_lock.py tests/test_layers.py`. Expected: PASS.

**Step 5:** Commit: `git add src/prov/core src/prov/storage tests/test_lock.py && git commit -m "Add RegistryLock: one flock per registry"`.

### Task 2: Every write operation takes the lock

**Files:**
- Modify: `src/prov/artifacts/publish.py`, `src/prov/artifacts/aliases.py`, `src/prov/datasets/freeze.py`, `src/prov/episodes/ingest.py`, `src/prov/episodes/annotate.py`, `src/prov/runs/records.py`, `src/prov/storage/catalog.py`
- Test: `tests/test_lock.py`

**Interfaces:**
- Consumes: `RegistryLock` from Task 1.
- Produces: unlocked internals `publish._publish(ctx, path, kind, meta=None, copy=False, alias=None) -> ArtifactRecord` (everything `publish` did except emitting the event), `aliases._set_version(ctx, ref, id_) -> None`, `aliases._set_label(ctx, ref, target) -> None`.

**Step 1: Write the failing tests** (append to `tests/test_lock.py`)

```python
import os

from conftest import git
from prov.artifacts import aliases
from prov.episodes.ingest import ingest
from test_episodes import make_lerobot

PUBLISH = """
import sys
from prov.wiring import context
from prov.artifacts.publish import publish
publish(context(), sys.argv[1], "result")
"""

FREEZE = """
from prov.wiring import context
from prov.datasets.freeze import freeze
freeze(context(), "race", query="SELECT id FROM episodes")
"""

N = 8


def _run_all(scripts: list[list[str]]) -> None:
    procs = [subprocess.Popen([sys.executable, "-c", *s], env=os.environ, stderr=subprocess.PIPE, text=True)
             for s in scripts]
    errs = [(p.wait(), p.stderr.read()) for p in procs]
    assert [rc for rc, _ in errs] == [0] * len(procs), [e for rc, e in errs if rc]


def test_concurrent_publishes_all_commit(ctx, registry, tmp_path):
    files = []
    for i in range(N):
        f = tmp_path / f"r{i}.txt"
        f.write_text(str(i))
        files.append(f)
    _run_all([[PUBLISH, str(f)] for f in files])
    assert len(list((registry / "records/artifacts/result").glob("*.yaml"))) == N
    assert git(registry, "status", "--porcelain") == "?? .prov.lock"
    assert int(git(registry, "rev-list", "--count", "HEAD")) == N


def test_concurrent_freezes_number_versions_without_orphans(ctx, registry, tmp_path):
    ingest(ctx, make_lerobot(tmp_path / "s0", [10, 12]))
    _run_all([[FREEZE]] * N)
    assert sorted(aliases.versions(ctx, "ds", "race"), key=int) == [str(i) for i in range(1, N + 1)]
    assert len(list((registry / "records/artifacts/dataset").glob("*.yaml"))) == N
    assert len(list((registry / "datasets").glob("*.txt"))) == N
    assert git(registry, "status", "--porcelain") == "?? .prov.lock"
```

**Step 2:** Run `.venv/bin/python -m pytest -q tests/test_lock.py`. Expected: the two new tests FAIL (git `index.lock` errors, or duplicate versions and orphan records). A race can occasionally pass unfixed; rerun once if so.

**Step 3: Implement**

`src/prov/artifacts/publish.py`: import `from prov.storage.lock import RegistryLock`; rename the current body to `_publish` (unlocked; same signature), drop its `events.emit` line, call `aliases._set_version` instead of `aliases.set_version`; then:

```python
def publish(ctx, path: Path, kind: str, meta: dict[str, Any] | None = None, copy: bool = False,
            alias: str | None = None) -> ArtifactRecord:
    """`alias` (`kind:name/version`) is checked before anything moves and set after. Holds the
    registry lock for the whole publish; `artifact.published` is emitted after release."""
    with RegistryLock(ctx.registry):
        record = _publish(ctx, path, kind, meta=meta, copy=copy, alias=alias)
    events.emit(ctx, "artifact.published", record)
    return record
```

`src/prov/artifacts/aliases.py`: import `RegistryLock`; rename `set_version` → `_set_version` and `set_label` → `_set_label` (bodies unchanged); add:

```python
def set_version(ctx, ref: str, id_: str) -> None:
    with RegistryLock(ctx.registry):
        _set_version(ctx, ref, id_)


def set_label(ctx, ref: str, target: str) -> None:
    with RegistryLock(ctx.registry):
        _set_label(ctx, ref, target)
```

`src/prov/datasets/freeze.py`: import `RegistryLock`; after `parent_id = ...`, wrap everything from `existing = ...` to the end of the loop in `with RegistryLock(ctx.registry):`, and call `aliases._set_version(ctx, ref, record.id)`; `return out` stays after the block.

`src/prov/episodes/ingest.py`: import `events` from `prov.core` and `RegistryLock`; rename the current `ingest` body to `_ingest(...) -> tuple[ArtifactRecord, list[EpisodeRecord], bool]`, where the bool is True when this call published the session; it calls `artifacts._publish(...)` instead of `artifacts.publish(...)`. Then:

```python
def ingest(ctx, path: Path, format: str = "lerobot", source_map: Path | None = None,
           calibrations: list[str] = (), meta: dict[str, Any] | None = None,
           copy: bool = False) -> tuple[ArtifactRecord, list[EpisodeRecord]]:
    """(docstring unchanged, plus:) Holds the registry lock for the whole ingest."""
    with RegistryLock(ctx.registry):
        session, eps, published = _ingest(ctx, path, format, source_map, calibrations, meta, copy)
    if published:
        events.emit(ctx, "artifact.published", session)
    return session, eps
```

`src/prov/episodes/annotate.py`: wrap from `session_id = session_of(...)` to the commit in `with RegistryLock(ctx.registry):`.

`src/prov/runs/records.py` `write`: wrap the write and the optional commit in `with RegistryLock(ctx.registry):`.

`src/prov/storage/catalog.py` `rebuild`: wrap the body from `db.parent.mkdir` to `tmp.replace(db)` in `with RegistryLock(ctx.registry):`.

**Step 4:** Run `.venv/bin/python -m pytest -q` (full suite) and `uvx ruff@0.8.4 check src tests`. Expected: all pass, lint clean.

**Step 5:** Commit: `git commit -am "Take the registry lock at every write operation"` (plus `git add` for the test file).

### Task 3: Record and document

**Files:**
- Create: `docs/adr/0016-one-registry-wide-write-lock.md` (Status Proposed, Accepted at Finalize)
- Modify: `docs/adr/README.md` (index row), `README.md` (registry setup: `echo .prov.lock > ~/registry/.gitignore` in the first commit), `pyproject.toml` (0.2.0)

**Step 1:** Write ADR 0016: Context (the four races), Decision (the contract and the operation table), Consequences (a slow `copy=True` publish blocks other writers; a waiter past 60 s fails with `RegistryLocked`; events and W&B calls run outside the lock), Enforced by (the four tests in `tests/test_lock.py`).

**Step 2:** Run the full suite and lint. Expected: pass.

**Step 3:** Commit.
