"""IDs: `<prefix>_<ULID>`. A ULID is 48 bits of milliseconds + 80 random bits, 26 Crockford chars."""

import os
import re
import time

from prov.core.errors import IdError

PREFIXES = {
    "run": "run",
    "session": "ses",
    "episode": "ep",
    "dataset": "ds",
    "checkpoint": "ckpt",
    "benchmark": "bench",
    "result": "res",
    "figure": "fig",
    "video": "vid",
    "raw": "raw",
    "calibration": "calib",
    "doc": "doc",
}

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ID_RE = re.compile(r"^([a-z]+)_([0-9A-HJKMNP-TV-Z]{26})$")
# Any prov ID inside free text (journal bodies).
ID_RE = re.compile(r"\b(?:" + "|".join(PREFIXES.values()) + r")_[0-9A-HJKMNP-TV-Z]{26}\b")


def ulid() -> str:
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(_CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(26)))


def new_id(kind: str) -> str:
    return f"{PREFIXES[kind]}_{ulid()}"


def kind_of(id_: str) -> str:
    m = _ID_RE.match(id_)
    if not m:
        raise IdError(f"not a prov ID: {id_!r}")
    for kind, prefix in PREFIXES.items():
        if prefix == m.group(1):
            return kind
    raise IdError(f"unknown ID prefix in {id_!r}")
