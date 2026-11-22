"""Journal docs: `journal/<year>/<month>/<YYYY-MM-DD>-<topic>/README.md`, one per topic per day.

Locating the journal, starting a doc from the template, parsing docs and frontmatter, and the
generated INDEX.md. Needs no Context: everything is relative to the project's prov.toml.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from prov.core.context import load_project
from prov.core.errors import JournalError
from prov.core.ids import new_id

TEMPLATES = Path(__file__).parent / "templates"
STATUSES = {"open", "concluded", "superseded"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class Doc:
    path: Path
    rel: str                   # relative to the project root, for messages
    text: str
    meta: dict | None          # None when missing or invalid
    body_start: int            # line number where the body starts


def journal_root(start: Path | None = None) -> Path:
    project = load_project(start or Path.cwd())
    root = project.root / "journal"
    if not root.is_dir():
        raise JournalError(f"no journal/ in {project.root}; run `prov-journal init`")
    return root


def new_doc(topic: str, continues: str | None = None, today: date | None = None,
            start: Path | None = None) -> Path:
    if not SLUG_RE.match(topic):
        raise JournalError(f"topic must be lowercase words joined by '-', got {topic!r}")
    root = journal_root(start)
    d = today or date.today()
    folder = root / f"{d:%Y}" / f"{d:%m}" / f"{d.isoformat()}-{topic}"
    if folder.exists():
        raise JournalError(f"{folder.relative_to(root)} exists; one doc per topic per day")
    cont = None
    if continues:
        target = (root / continues).resolve() if not Path(continues).is_absolute() else Path(continues)
        if target.name == "README.md":
            target = target.parent
        if not (target / "README.md").is_file():
            raise JournalError(f"--continues {continues}: no such doc")
        cont = str(Path("../../..") / target.relative_to(root.resolve()) / "README.md")
    folder.mkdir(parents=True)
    title = topic.replace("-", " ").capitalize()
    text = (TEMPLATES / "doc.md").read_text().format(id=new_id("doc"), date=d.isoformat(),
                                                    continues=cont or "null", title=title)
    (folder / "README.md").write_text(text)
    return folder / "README.md"


def frontmatter(text: str) -> tuple[dict | None, int]:
    """(frontmatter, line number where the body starts); None if missing or invalid."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            try:
                data = yaml.safe_load("\n".join(lines[1:i])) or {}
            except yaml.YAMLError:
                return None, i + 1
            return (data if isinstance(data, dict) else None), i + 1
    return None, 1


def docs(root: Path) -> list[Doc]:
    out = []
    for p in sorted(root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*/README.md")):
        text = p.read_text()
        meta, body_start = frontmatter(text)
        out.append(Doc(p, str(p.relative_to(root.parent)), text, meta, body_start))
    return out


def index_text(rows: list[tuple[str, str, str, str, str]]) -> str:
    lines = ["# Index", "", "Every doc, newest first. Rebuilt by `prov-journal index`; don't edit by hand.", "",
             "| Date | Doc | Status | Evidence |", "| --- | --- | --- | --- |"]
    lines += [f"| {d} | [{t}]({p}) | {s} | {e} |" for d, t, p, s, e in rows]
    return "\n".join(lines) + "\n"


def index(root: Path) -> Path:
    rows = []
    for doc in docs(root):
        meta = doc.meta or {}
        title = next((l[2:].strip() for l in doc.text.splitlines() if l.startswith("# ")), doc.path.parent.name)
        rows.append((str(meta.get("date", doc.path.parent.name[:10])), title.replace("|", "/"),
                     str(doc.path.relative_to(root)), str(meta.get("status", "?")),
                     str(len(meta.get("evidence") or []))))
    rows.sort(key=lambda r: (r[0], r[2]), reverse=True)
    path = root / "INDEX.md"
    path.write_text(index_text(rows))
    return path
