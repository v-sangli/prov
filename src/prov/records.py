"""Record schemas. Records are YAML files in the registry; these models are their only definition."""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, path: Path):
        return cls.model_validate(yaml.safe_load(path.read_text()))


class ExcludedFile(_Record):
    path: str
    bytes: int


class CodeState(_Record):
    repo: str                      # directory name of the repo
    path: str                      # absolute path at run time
    base: str                      # HEAD commit when the run started
    snapshot: str                  # commit of the full working tree (== base when clean)
    ref: str                       # refs/prov/<run_id>
    dirty: bool
    pushed: bool                   # ref reached the remote
    excluded: list[ExcludedFile] = []   # untracked files over the size cap, not in the snapshot


class Env(_Record):
    python: str
    platform: str
    gpu: list[str] = []


class RunRecord(_Record):
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
    wandb: str | None = None
    tags: dict[str, str] = {}
    summary: dict[str, float | int | str] = {}
    notes: str | None = None


class EpisodeSource(_Record):
    kind: Literal["teleop", "mcap"]
    raw: str | None = None         # raw_ ID of the MCAP, when registered
    path: str | None = None        # MCAP path
    start_s: float | None = None   # time range within the MCAP
    end_s: float | None = None


class EpisodeRecord(_Record):
    id: str
    session: str                   # ses_ ID
    episode_index: int             # position in the LeRobot folder; not an identity
    length: int                    # frames
    fps: float
    duration_s: float
    tasks: list[str] = []
    source: EpisodeSource
    calibrations: list[str] = []   # calib_ IDs in use when recorded


class Annotation(_Record):
    episode: str
    key: str
    value: str
    time: datetime


class ArtifactRecord(_Record):
    id: str
    kind: str
    uri: str | None = None         # store://<relative path>; None for records without bytes (datasets)
    created: datetime
    source: str | None = None      # where it was before publishing
    produced_by: str | None = None # run ID
    meta: dict[str, Any] = {}
