"""Events: lower layers announce what happened; integrations listen. Subscribers are listed in the
Context's Extensions and must not raise.

    artifact.published   payload: ArtifactRecord   (artifacts.publish)
    artifact.loaded      payload: ArtifactRecord   (prov.load)
    run.summary          payload: dict of values   (prov.summary)
"""

from typing import Any

from prov.core import log

_log = log.get("events")


def emit(ctx, event: str, payload: Any) -> None:
    for fn in ctx.ext.subscribers.get(event, []):
        _log.debug("%s -> %s.%s", event, fn.__module__, fn.__qualname__)
        fn(ctx, payload)
