"""The plugin (ADR 0021): manifests, skills, and the SessionStart hook."""

import json
import subprocess
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


def run_hook(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(PLUGIN / "hooks" / "session_start.sh")], cwd=cwd,
                          capture_output=True, text=True, check=True)


def test_hook_is_registered():
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    [entry] = hooks["SessionStart"]
    assert entry["hooks"] == [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.sh"}]


def test_hook_speaks_inside_a_prov_project(tmp_path):
    (tmp_path / "prov.toml").write_text('project = "demo"\n')
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "NOW.md").write_text("# Now\n")
    (tmp_path / "src" / "deep").mkdir(parents=True)
    out = run_hook(tmp_path / "src" / "deep").stdout
    assert f"prov.toml at {tmp_path}" in out
    assert f"{tmp_path}/journal/NOW.md" in out


def test_hook_is_silent_outside_one(tmp_path):
    assert run_hook(tmp_path).stdout == ""
