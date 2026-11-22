"""Registering docs. A doc is a Markdown file inside a git repo; its ID is `id:` in its frontmatter.

Everything in the file counts as a citation: every prov ID and alias, frontmatter or body,
aliases resolved, the doc's own ID left out; each must be in the registry. A version is appended
only when (commit, dirty, cites) differs from the last one.
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from prov.artifacts import aliases
from prov.core import layout
from prov.core.errors import DocError
from prov.core.ids import ID_RE, kind_of, new_id
from prov.docs.schema import DocRecord, DocVersion
from prov.storage import catalog, registry
from prov.storage.lock import RegistryLock


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _split(text: str) -> tuple[list[str], list[str]]:
    """(frontmatter lines without the fences, body lines); no frontmatter is []."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return [], lines
    end = [line.rstrip() for line in lines].index("---", 1)
    return lines[1:end], lines[end + 1:]


def _key(v: DocVersion) -> tuple:
    return v.commit, v.dirty, v.cites


@dataclass(frozen=True)
class _Parsed:
    path: Path
    root: Path
    front: list[str]
    body: list[str]
    doc_id: str | None
    cites: list[str]


def _parse(ctx, path: Path) -> _Parsed:
    path = path.resolve()
    top = _git(path.parent, "rev-parse", "--show-toplevel")
    if top.returncode:
        raise DocError(f"{path} is in no git repo; fold it into a journal first")
    text = path.read_text()
    front, body = _split(text)
    doc_id = (yaml.safe_load("".join(front)) or {}).get("id")
    if doc_id is not None and kind_of(doc_id) != "doc":
        raise DocError(f"{path}: id {doc_id} is not a doc ID")
    cited = {m.group(0) for m in ID_RE.finditer(text)}
    cited |= {aliases.resolve(ctx, m.group(0)) for m in aliases.ALIAS_RE.finditer(text)}
    return _Parsed(path, Path(top.stdout.strip()), front, body, doc_id, sorted(cited - {doc_id}))


def register(ctx, paths: list[Path]) -> list[DocRecord]:
    """Give each doc an ID (written into its frontmatter) and record its current version.

    The batch is checked as a whole before anything is written: docs in it may cite each other,
    and one unknown citation fails the batch with no file changed. One registry commit.
    """
    parsed = [_parse(ctx, p) for p in paths]
    batch = {d.doc_id for d in parsed if d.doc_id}
    wanted = sorted({c for d in parsed for c in d.cites} - batch)
    with catalog.connect(ctx) as con:
        known = batch | {i for (i,) in con.execute("SELECT id FROM nodes WHERE list_contains(?, id)",
                                                   [wanted]).fetchall()}
    bad = [f"{d.path}: {', '.join(c for c in d.cites if c not in known)}"
           for d in parsed if any(c not in known for c in d.cites)]
    if bad:
        raise DocError("cites what is not in the registry: " + "; ".join(bad))

    now = datetime.now(timezone.utc)
    staged = []
    for d in parsed:
        doc_id = d.doc_id
        if doc_id is None:
            doc_id = new_id("doc")
            d.path.write_text(f"---\nid: {doc_id}\n{''.join(d.front)}---\n{''.join(d.body)}")
        rel = str(d.path.relative_to(d.root))
        origin = _git(d.root, "remote", "get-url", "origin")
        staged.append((doc_id, d, rel, origin.stdout.strip() if origin.returncode == 0 else None, DocVersion(
            commit=_git(d.root, "log", "-1", "--format=%H", "--", rel).stdout.strip() or None,
            dirty=bool(_git(d.root, "status", "--porcelain", "--", rel).stdout.strip()),
            registered=now, cites=d.cites)))

    out, written, lines = [], [], []
    with RegistryLock(ctx.registry):
        for doc_id, d, rel, remote, version in staged:
            rec = ctx.registry / layout.doc_record(doc_id)
            old = DocRecord.from_yaml(rec) if rec.is_file() else None
            if old and _key(old.versions[-1]) == _key(version):
                out.append(old)
                continue
            title = next((line[2:].strip() for line in d.body if line.startswith("# ")), d.path.name)
            record = DocRecord(id=doc_id, repo=d.root.name, remote=remote, path=rel, title=title,
                               created=old.created if old else now,
                               versions=[*(old.versions if old else []), version])
            written.append(registry.write(ctx.registry, layout.doc_record(doc_id), record.to_yaml()))
            lines.append(f"doc {doc_id} ({d.root.name}/{rel})")
            out.append(record)
        if written:
            registry.commit(ctx.registry, written, "\n".join(lines))   # one line per doc
    return out


def load(ctx, doc_id: str) -> DocRecord:
    p = ctx.registry / layout.doc_record(doc_id)
    if not p.is_file():
        raise DocError(f"no record for {doc_id}")
    return DocRecord.from_yaml(p)


def all_docs(ctx) -> list[DocRecord]:
    return [DocRecord.from_yaml(p) for p in sorted((ctx.registry / layout.DOCS_DIR).glob("*.yaml"))]
