"""`prov-skills` command line.

    prov-skills install <project>
        Link every skill (each directory here holding a SKILL.md) into <project>/.claude/skills/.
        Never overwrites.
"""

import argparse
import sys
from pathlib import Path

SKILLS = Path(__file__).parent


def install(root: Path) -> list[str]:
    """Link every skill into `root`/.claude/skills/; returns what it created."""
    made = []
    for skill in sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()):
        link = root / ".claude" / "skills" / skill.name
        if not link.exists() and not link.is_symlink():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(skill, target_is_directory=True)
            made.append(f".claude/skills/{skill.name} -> prov-skills")
    return made


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prov-skills")
    sub = parser.add_subparsers(dest="cmd", required=True)
    inst = sub.add_parser("install", help="link every skill into <project>/.claude/skills/")
    inst.add_argument("project", type=Path)
    args = parser.parse_args(argv)
    made = install(args.project)
    print("\n".join(made) if made else "nothing to do: already set up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
