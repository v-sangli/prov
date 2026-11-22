"""Configuration, loaded once per call into a Context.

Machine config: `$PROV_CONFIG` or `~/.config/prov/config.toml`:
    registry = "~/registry"                     # registry repo
    store_root = "~/store"
    catalog = "~/.cache/prov/catalog.duckdb"    # optional; rebuilt from the registry
    sites_dir = "~/.cache/prov/sites"           # optional; built sites
    quartz = "<Quartz checkout>"                # optional; only for `prov site`
    node = "<dir with node/npx>"                # optional

Project config: `prov.toml`, found by walking up from the working directory:
    project = "cube-grasp"
    repos = [".", "../Isaac-GR00T"]   # repos to snapshot, relative to prov.toml
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from prov.core.errors import ConfigError
from prov.core.extensions import Extensions
from prov.core.runenv import RunEnv

CONFIG_ENV = "PROV_CONFIG"
DEFAULT_CONFIG = "~/.config/prov/config.toml"


@dataclass(frozen=True)
class Context:
    """Everything a library function needs to know about this machine and this process."""
    registry: Path
    store_root: Path
    catalog: Path
    sites_dir: Path
    quartz: Path | None
    node: Path | None
    ext: Extensions
    run: RunEnv | None = None

    @classmethod
    def load(cls, ext: Extensions, path: Path | None = None) -> "Context":
        path = Path(path or os.environ.get(CONFIG_ENV, DEFAULT_CONFIG)).expanduser()
        if not path.is_file():
            raise ConfigError(f"no machine config at {path}")
        data = tomllib.loads(path.read_text())
        opt = lambda key: Path(data[key]).expanduser() if key in data else None   # noqa: E731
        try:
            return cls(
                registry=Path(data["registry"]).expanduser(),
                store_root=Path(data["store_root"]).expanduser(),
                catalog=Path(data.get("catalog", "~/.cache/prov/catalog.duckdb")).expanduser(),
                sites_dir=Path(data.get("sites_dir", "~/.cache/prov/sites")).expanduser(),
                quartz=opt("quartz"), node=opt("node"), ext=ext, run=RunEnv.from_env(),
            )
        except KeyError as exc:
            raise ConfigError(f"{path}: missing {exc}") from None


@dataclass(frozen=True)
class ProjectConfig:
    project: str
    root: Path
    repos: list[Path]


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
