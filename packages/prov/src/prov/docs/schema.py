"""Doc record schema: `<registry>/records/docs/<doc_id>.yaml`."""

from datetime import datetime

from prov.core.schema import Record


class DocVersion(Record):
    commit: str | None             # last commit that touched the file; None when never committed
    dirty: bool                    # the file differs from that commit (or is untracked)
    registered: datetime
    cites: list[str]               # sorted IDs, aliases resolved, the doc's own ID excluded


class DocRecord(Record):
    id: str
    repo: str                      # repo directory name
    remote: str | None             # origin URL
    path: str                      # relative to the repo root
    title: str                     # first "# " heading, else the file name
    created: datetime
    versions: list[DocVersion]
