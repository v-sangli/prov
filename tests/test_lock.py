import os
import subprocess
import sys

import pytest

from conftest import git
from prov.artifacts import aliases
from prov.core.errors import RegistryLocked
from prov.episodes.ingest import ingest
from prov.storage.lock import RegistryLock
from test_episodes import make_lerobot

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
    assert git(registry, "status", "--porcelain") == ""
    assert int(git(registry, "rev-list", "--count", "HEAD")) == N


def test_concurrent_freezes_number_versions_without_orphans(ctx, registry, tmp_path):
    ingest(ctx, make_lerobot(tmp_path / "s0", [10, 12]))
    _run_all([[FREEZE]] * N)
    assert sorted(aliases.versions(ctx, "ds", "race"), key=int) == [str(i) for i in range(1, N + 1)]
    assert len(list((registry / "records/artifacts/dataset").glob("*.yaml"))) == N
    assert len(list((registry / "datasets").glob("*.txt"))) == N
    assert git(registry, "status", "--porcelain") == ""
