"""The contract between `prov run` and the process it wraps.

`prov run` sets these variables; prov calls inside the process append to the files they name, and
`prov run` folds the files into the run record when the process exits.

    PROV_RUN_ID        the run's ID; artifacts published inside get `produced_by` = this
    PROV_PROJECT       the project name
    PROV_RUN_INPUTS    file: one artifact ID per line, appended by prov.load
    PROV_RUN_OUTPUTS   file: one artifact ID per line, appended by prov.publish
    PROV_RUN_SUMMARY   file: one JSON object per line, appended by prov.summary (later keys win)
"""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

RUN_ID = "PROV_RUN_ID"
PROJECT = "PROV_PROJECT"
INPUTS = "PROV_RUN_INPUTS"
OUTPUTS = "PROV_RUN_OUTPUTS"
SUMMARY = "PROV_RUN_SUMMARY"


@dataclass(frozen=True)
class RunEnv:
    run_id: str
    project: str | None = None
    inputs: Path | None = None
    outputs: Path | None = None
    summary: Path | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> "RunEnv | None":
        """The current run, or None outside `prov run`."""
        if not environ.get(RUN_ID):
            return None
        file = lambda key: Path(environ[key]) if environ.get(key) else None   # noqa: E731
        return cls(run_id=environ[RUN_ID], project=environ.get(PROJECT), inputs=file(INPUTS),
                   outputs=file(OUTPUTS), summary=file(SUMMARY))

    def to_env(self) -> dict[str, str]:
        pairs = {RUN_ID: self.run_id, PROJECT: self.project, INPUTS: self.inputs, OUTPUTS: self.outputs,
                 SUMMARY: self.summary}
        return {k: str(v) for k, v in pairs.items() if v is not None}

    @staticmethod
    def _append(path: Path | None, line: str) -> None:
        if path is not None:
            with open(path, "a") as f:
                f.write(line + "\n")

    def inputs_so_far(self) -> list[str]:
        """Artifact IDs prov.load-ed so far in this run: load order, first occurrence kept."""
        if self.inputs is None or not self.inputs.is_file():
            return []
        return list(dict.fromkeys(line for line in self.inputs.read_text().splitlines() if line))

    def record_input(self, id_: str) -> None:
        self._append(self.inputs, id_)

    def record_output(self, id_: str) -> None:
        self._append(self.outputs, id_)

    def add_summary(self, values: dict) -> bool:
        """False when this run has no summary file."""
        self._append(self.summary, json.dumps(values))
        return self.summary is not None

