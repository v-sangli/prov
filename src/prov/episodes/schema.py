"""Episode and annotation schemas: JSONL lines in `<registry>/records/{episodes,annotations}/<ses_id>.jsonl`."""

from datetime import datetime
from typing import Literal

from prov.core.schema import Record


class EpisodeSource(Record):
    kind: Literal["teleop", "mcap"]
    raw: str | None = None         # raw_ ID of the MCAP, when registered
    path: str | None = None        # MCAP path
    start_s: float | None = None   # time range within the MCAP
    end_s: float | None = None


class EpisodeRecord(Record):
    id: str
    session: str                   # ses_ ID
    episode_index: int             # position in the LeRobot folder; not an identity
    length: int                    # frames
    fps: float
    duration_s: float
    tasks: list[str] = []
    source: EpisodeSource
    calibrations: list[str] = []   # calib_ IDs in use when recorded


class Annotation(Record):
    episode: str
    key: str
    value: str
    time: datetime
