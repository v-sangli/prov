"""Configuration.

Machine config: `$PROV_CONFIG` or `~/.config/prov/config.toml`:
    registry = "~/registry"        # registry repo
    store_root = "~/store"

Project config: `prov.toml`, found by walking up from the working directory:
    project = "cube-grasp"
    repos = [".", "../Isaac-GR00T"]   # repos to snapshot, relative to prov.toml
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class MachineConfig:
    registry: Path
    store_root: Path


@dataclass(frozen=True)
class ProjectConfig:
    project: str
    root: Path
    repos: list[Path]


def load_machine() -> MachineConfig:
    path = Path(os.environ.get("PROV_CONFIG", "~/.config/prov/config.toml")).expanduser()
    if not path.is_file():
        raise ConfigError(f"no machine config at {path}")
    data = tomllib.loads(path.read_text())
    try:
        return MachineConfig(
            registry=Path(data["registry"]).expanduser(),
            store_root=Path(data["store_root"]).expanduser(),
        )
    except KeyError as exc:
        raise ConfigError(f"{path}: missing {exc}") from None


def load_project(start: Path) -> ProjectConfig:
    for d in [start, *start.parents]:
        path = d / "prov.toml"
        if path.is_file():
            data = tomllib.loads(path.read_text())
            if "project" not in data:
                raise ConfigError(f"{path}: missing 'project'")
            repos = [(d / r).resolve() for r in data.get("repos", ["."])]
            return ProjectConfig(project=data["project"], root=d, repos=repos)
    raise ConfigError(f"no prov.toml in {start} or its parents")
