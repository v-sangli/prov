"""The plugin (ADR 0021): manifests, skills, and the SessionStart hook."""

import json
import tomllib
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]


def frontmatter_name(skill_md: Path) -> str:
    head = skill_md.read_text().split("---")[1]
    return next(line.split(":", 1)[1].strip() for line in head.splitlines() if line.startswith("name:"))


def test_marketplace_lists_the_plugin():
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    assert market["name"] == "prov"
    assert [(p["name"], p["source"]) for p in market["plugins"]] == [("prov-skills", "./packages/prov-skills")]


def test_plugin_version_is_the_package_version():
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    package = tomllib.loads((PLUGIN / "pyproject.toml").read_text())["project"]
    assert (plugin["name"], plugin["version"]) == (package["name"], package["version"])


def test_every_skill_names_its_directory():
    skills = {d.name: d / "SKILL.md" for d in (PLUGIN / "skills").iterdir()}
    assert set(skills) == {"prov", "journal", "plot"}
    for name, skill_md in skills.items():
        assert frontmatter_name(skill_md) == name
