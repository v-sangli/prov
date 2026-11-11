"""Project setup and the journal: init, new doc, lint, index."""

import re
from datetime import date
from pathlib import Path

import yaml

from prov import aliases, catalog, config

PKG = Path(__file__).parent
TEMPLATES = PKG / "templates" / "journal"
SKILLS = PKG / "skills"
STATUSES = {"open", "concluded", "superseded"}
ID_RE = re.compile(r"\b(?:run|ses|ep|ds|ckpt|bench|res|fig|vid|raw|calib)_[0-9A-HJKMNP-TV-Z]{26}\b")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_THREAD_ROW = 300
GITIGNORE_LINES = ["journal/media", "journal/.obsidian/workspace*.json"]


class JournalError(Exception):
    pass


# setup

def init_project(root: Path, project: str) -> list[str]:
    """Make `root` a prov project. Never overwrites; returns what it created."""
    machine = config.load_machine()
    made = []

    def create(path: Path, text: str) -> None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            made.append(str(path.relative_to(root)))

    create(root / "prov.toml", f'project = "{project}"\nrepos = ["."]\n')
    journal = root / "journal"
    for name in ("README.md", "NOW.md"):
        create(journal / name, (TEMPLATES / name).read_text())
    create(journal / "INDEX.md", _index_text([]))
    media = journal / "media"
    if not media.exists() and not media.is_symlink():
        media.symlink_to(machine.store_root / "media", target_is_directory=True)
        made.append("journal/media -> store media/")
    gitignore = root / ".gitignore"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    missing = [line for line in GITIGNORE_LINES if line not in lines]
    if missing:
        gitignore.write_text("\n".join([*lines, *missing]) + "\n")
        made.append(f".gitignore += {', '.join(missing)}")
    for skill in sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()):
        link = root / ".claude" / "skills" / skill.name
        if not link.exists() and not link.is_symlink():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(skill, target_is_directory=True)
            made.append(f".claude/skills/{skill.name} -> prov")
    return made


def journal_root(start: Path | None = None) -> Path:
    project = config.load_project(start or Path.cwd())
    root = project.root / "journal"
    if not root.is_dir():
        raise JournalError(f"no journal/ in {project.root}; run `prov init`")
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
    text = (TEMPLATES / "doc.md").read_text().format(date=d.isoformat(), continues=cont or "null", title=title)
    (folder / "README.md").write_text(text)
    return folder / "README.md"


# reading docs

def _docs(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/*/README.md"))


def _frontmatter(text: str) -> tuple[dict | None, int]:
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


# lint

def lint(root: Path) -> list[str]:
    """Problems as `path:line: message`; empty when the journal is clean."""
    problems: list[str] = []
    rel = lambda p: str(p.relative_to(root.parent))     # noqa: E731
    with catalog.connect() as con:
        known = {i for (i,) in con.execute(
            "SELECT id FROM runs UNION ALL SELECT id FROM artifacts UNION ALL SELECT id FROM episodes").fetchall()}

    def check_ref(ref: str, where: str) -> None:
        try:
            id_ = aliases.resolve(ref) if ":" in ref else ref
        except aliases.AliasError as exc:
            problems.append(f"{where}: {exc}")
            return
        if not ID_RE.fullmatch(id_):
            problems.append(f"{where}: {ref!r} is not an ID or alias (evidence is IDs, not paths)")
        elif id_ not in known:
            problems.append(f"{where}: {ref} is not in the registry")

    for doc in _docs(root):
        text = doc.read_text()
        meta, body_start = _frontmatter(text)
        if meta is None:
            problems.append(f"{rel(doc)}:1: missing or invalid frontmatter")
            continue
        folder_date = doc.parent.name[:10]
        if str(meta.get("date")) != folder_date:
            problems.append(f"{rel(doc)}:1: date {meta.get('date')} does not match folder {folder_date}")
        status = meta.get("status")
        if status not in STATUSES:
            problems.append(f"{rel(doc)}:1: status {status!r} not one of {sorted(STATUSES)}")
        links = {"continues": meta.get("continues")}
        if status == "superseded":
            if not meta.get("superseded_by"):
                problems.append(f"{rel(doc)}:1: superseded without superseded_by")
            links["superseded_by"] = meta.get("superseded_by")
        for key, link in links.items():
            if link and not (doc.parent / link).resolve().is_file():
                problems.append(f"{rel(doc)}:1: {key} {link} does not exist")
        evidence = meta.get("evidence") or []
        if not isinstance(evidence, list):
            problems.append(f"{rel(doc)}:1: evidence must be a list")
            evidence = []
        for ref in evidence:
            check_ref(str(ref), f"{rel(doc)}:1")
        for n, line in enumerate(text.splitlines()[body_start:], start=body_start + 1):
            for m in ID_RE.finditer(line):
                if m.group(0) not in known:
                    problems.append(f"{rel(doc)}:{n}: {m.group(0)} is not in the registry")
            for m in IMAGE_RE.finditer(line):
                target = m.group(1)
                if "://" not in target and not (doc.parent / target).exists():
                    problems.append(f"{rel(doc)}:{n}: image {target} not found")

    now = root / "NOW.md"
    if now.is_file():
        in_threads = False
        for n, line in enumerate(now.read_text().splitlines(), start=1):
            if line.startswith("## "):
                in_threads = line.strip().lower() == "## open threads"
            elif in_threads and line.startswith("|") and not set(line) <= set("|- :"):
                if len(line) > MAX_THREAD_ROW:
                    problems.append(f"journal/NOW.md:{n}: thread row is {len(line)} chars; keep it to one "
                                    f"line ({MAX_THREAD_ROW} max) and put the detail in the doc")
    return problems


# index

def _index_text(rows: list[tuple[str, str, str, str, str]]) -> str:
    lines = ["# Index", "", "Every doc, newest first. Rebuilt by `prov journal index`; don't edit by hand.", "",
             "| Date | Doc | Status | Evidence |", "| --- | --- | --- | --- |"]
    lines += [f"| {d} | [{t}]({p}) | {s} | {e} |" for d, t, p, s, e in rows]
    return "\n".join(lines) + "\n"


def index(root: Path) -> Path:
    rows = []
    for doc in _docs(root):
        text = doc.read_text()
        meta, _ = _frontmatter(text)
        meta = meta or {}
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), doc.parent.name)
        rows.append((str(meta.get("date", doc.parent.name[:10])), title.replace("|", "/"),
                     str(doc.relative_to(root)), str(meta.get("status", "?")), str(len(meta.get("evidence") or []))))
    rows.sort(key=lambda r: (r[0], r[2]), reverse=True)
    path = root / "INDEX.md"
    path.write_text(_index_text(rows))
    return path
