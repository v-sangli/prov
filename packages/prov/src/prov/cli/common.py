"""Helpers shared by the command groups.

Every handler is `handler(args, get_ctx) -> exit code`; `get_ctx()` loads the Context, so commands
that need no machine config (journal new / index, --help) never read it.
"""

from prov.core.errors import ConfigError


def pairs(items: list[str]) -> dict[str, str]:
    for item in items:
        if "=" not in item:
            raise ConfigError(f"expected key=value, got {item!r}")
    return dict(item.split("=", 1) for item in items)
