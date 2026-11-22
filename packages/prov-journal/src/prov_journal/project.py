"""Adding the journal to a prov project. Never overwrites; reports what it created."""

from pathlib import Path

from prov.core import layout
from prov_journal.docs import TEMPLATES, index_text

GITIGNORE_LINES = ["journal/media", "journal/.obsidian/workspace*.json"]


def init_journal(ctx, root: Path) -> list[str]:
    """Give `root` a journal/ skeleton, the journal/media link and the .gitignore lines; returns
    what it created."""
    made = []

    def create(path: Path, text: str) -> None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            made.append(str(path.relative_to(root)))

    journal = root / "journal"
    for name in ("README.md", "NOW.md"):
        create(journal / name, (TEMPLATES / name).read_text())
    create(journal / "INDEX.md", index_text([]))
    media = journal / "media"
    if not media.exists() and not media.is_symlink():
        media.symlink_to(ctx.store_root / layout.MEDIA_DIR, target_is_directory=True)
        made.append("journal/media -> store media/")
    gitignore = root / ".gitignore"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [line for line in GITIGNORE_LINES if line not in lines]
    if missing:
        gitignore.write_text("\n".join([*lines, *missing]) + "\n")
        made.append(f".gitignore += {', '.join(missing)}")
    return made
