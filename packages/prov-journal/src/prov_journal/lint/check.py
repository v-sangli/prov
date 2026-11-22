"""The LintCheck type: one journal rule. Each rule module in this package exposes one as CHECK."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LintCheck:
    name: str
    check: Callable[[Any], list[str]]                    # JournalView -> ["path:line: message"]
