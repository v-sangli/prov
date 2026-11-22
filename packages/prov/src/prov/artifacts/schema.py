"""Artifact record schema: `<registry>/records/artifacts/<kind>/<id>.yaml`."""

from datetime import datetime
from typing import Any

from prov.core.schema import Record


class ArtifactRecord(Record):
    id: str
    kind: str
    uri: str | None = None         # store://<relative path>; None for records without bytes (datasets)
    created: datetime
    source: str | None = None      # where it was before publishing
    produced_by: str | None = None # run ID
    meta: dict[str, Any] = {}
