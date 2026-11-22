"""The `prov` logger: `prov: <message>` on stderr, INFO and above by default.

Library code logs through `get(<module>)`; the CLI's `-v` / `-q` call `set_verbosity`. The handler
looks up sys.stderr at each message, so redirected or captured stderr still gets it.
"""

import logging
import sys

_root = logging.getLogger("prov")


class _Stderr(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stderr.write(self.format(record) + "\n")
        except Exception:                       # logging must never break the caller
            self.handleError(record)


if not _root.handlers:
    _handler = _Stderr()
    _handler.setFormatter(logging.Formatter("prov: %(message)s"))
    _root.addHandler(_handler)
    _root.setLevel(logging.INFO)
    _root.propagate = False


def get(name: str) -> logging.Logger:
    return _root.getChild(name)


def set_verbosity(verbosity: int) -> None:
    """-1 quiet (warnings and errors), 0 normal (info), 1 verbose (debug)."""
    _root.setLevel({-1: logging.WARNING, 0: logging.INFO}.get(verbosity, logging.DEBUG))
