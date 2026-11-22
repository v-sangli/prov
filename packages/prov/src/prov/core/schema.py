"""Base for record schemas. Records are YAML (or JSONL) files in the registry; their pydantic models
are their only definition. Unknown fields are rejected."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, path: Path):
        return cls.model_validate(yaml.safe_load(path.read_text()))
