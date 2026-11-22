"""Registering docs. A doc is a Markdown file inside a git repo; its ID is `id:` in its frontmatter.

Everything in the file counts as a citation: every prov ID and alias, frontmatter or body,
aliases resolved, the doc's own ID left out; each must be in the registry. A version is appended
only when (commit, dirty, cites) differs from the last one.
"""

import subprocess
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


def register(ctx, path: Path) -> DocRecord:
    """Give the doc at `path` an ID (written into its frontmatter) and record its current version."""
    path = path.resolve()
    top = _git(path.parent, "rev-parse", "--show-toplevel")
    if top.returncode:
        raise DocError(f"{path} is in no git repo; fold it into a journal first")
    root = Path(top.stdout.strip())
    text = path.read_text()
    front, body = _split(text)
    doc_id = (yaml.safe_load("".join(front)) or {}).get("id")
    if doc_id is not None and kind_of(doc_id) != "doc":
        raise DocError(f"{path}: id {doc_id} is not a doc ID")
    cited = {m.group(0) for m in ID_RE.finditer(text)}
    cited |= {aliases.resolve(ctx, m.group(0)) for m in aliases.ALIAS_RE.finditer(text)}
    cites = sorted(cited - {doc_id})
    with catalog.connect(ctx) as con:
        known = {i for (i,) in con.execute("SELECT id FROM nodes WHERE list_contains(?, id)", [cites]).fetchall()}
    unknown = [c for c in cites if c not in known]
    if unknown:
        raise DocError(f"{path}: cites what is not in the registry: {', '.join(unknown)}")

    if doc_id is None:
        doc_id = new_id("doc")
        path.write_text(f"---\nid: {doc_id}\n{''.join(front)}---\n{''.join(body)}")
    rel = str(path.relative_to(root))
    title = next((line[2:].strip() for line in body if line.startswith("# ")), path.name)
    origin = _git(root, "remote", "get-url", "origin")
    now = datetime.now(timezone.utc)
    version = DocVersion(commit=_git(root, "log", "-1", "--format=%H", "--", rel).stdout.strip() or None,
                         dirty=bool(_git(root, "status", "--porcelain", "--", rel).stdout.strip()),
                         registered=now, cites=cites)

    with RegistryLock(ctx.registry):
        rec = ctx.registry / layout.doc_record(doc_id)
        old = DocRecord.from_yaml(rec) if rec.is_file() else None
        if old and _key(old.versions[-1]) == _key(version):
            return old
        record = DocRecord(id=doc_id, repo=root.name, remote=origin.stdout.strip() if origin.returncode == 0 else None,
                           path=rel, title=title, created=old.created if old else now,
                           versions=[*(old.versions if old else []), version])
        p = registry.write(ctx.registry, layout.doc_record(doc_id), record.to_yaml())
        registry.commit(ctx.registry, p, f"doc {doc_id} ({root.name}/{rel})")
    return record


def load(ctx, doc_id: str) -> DocRecord:
    p = ctx.registry / layout.doc_record(doc_id)
    if not p.is_file():
        raise DocError(f"no record for {doc_id}")
    return DocRecord.from_yaml(p)


def all_docs(ctx) -> list[DocRecord]:
    return [DocRecord.from_yaml(p) for p in sorted((ctx.registry / layout.DOCS_DIR).glob("*.yaml"))]
