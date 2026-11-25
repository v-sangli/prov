"""The skills are files at a fixed path, linked by installers (ADR 0022)."""

from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def frontmatter_name(skill_md: Path) -> str:
    head = skill_md.read_text().split("---")[1]
    return next(line.split(":", 1)[1].strip() for line in head.splitlines() if line.startswith("name:"))


def test_every_skill_names_its_directory():
    skills = {d.name: d / "SKILL.md" for d in SKILLS.iterdir()}
    assert set(skills) == {"prov", "prov-journal", "prov-plot"}
    for name, skill_md in skills.items():
        assert frontmatter_name(skill_md) == name
