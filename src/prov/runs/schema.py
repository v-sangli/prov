"""Run record schema: `<registry>/records/runs/<run_id>.yaml`."""

from datetime import datetime
from typing import Literal

from prov.core.schema import Record

KINDS = ["collect", "export", "train", "eval", "analysis", "other"]


class ExcludedFile(Record):
    path: str
    bytes: int


class CodeState(Record):
    repo: str                      # directory name of the repo
    path: str                      # absolute path at run time
    base: str                      # HEAD commit when the run started
    snapshot: str                  # commit of the full working tree (== base when clean)
    ref: str                       # refs/prov/<run_id>
    dirty: bool
    pushed: bool                   # ref reached the remote
    excluded: list[ExcludedFile] = []   # untracked files over the size cap, not in the snapshot


class Env(Record):
    python: str
    platform: str
    gpu: list[str] = []


class RunRecord(Record):
    id: str
    kind: Literal["collect", "export", "train", "eval", "analysis", "other"]
    project: str
    started: datetime
    finished: datetime | None = None
    status: Literal["running", "ok", "failed", "killed"]
    exit_code: int | None = None
    host: str
    cwd: str
    command: list[str]
    code: list[CodeState]
    env: Env
    inputs: list[str] = []
    outputs: list[str] = []
    tags: dict[str, str] = {}
    summary: dict[str, float | int | str] = {}
    notes: str | None = None
