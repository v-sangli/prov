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
