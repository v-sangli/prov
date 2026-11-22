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
