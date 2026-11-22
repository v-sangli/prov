"""Docs: Markdown files in a git repo, registered with a `doc_` ID and the IDs they cite."""

from pathlib import Path

import pytest

from conftest import git
from prov.artifacts import aliases
from prov.artifacts.publish import publish
from prov.cli import main
from prov.core.errors import DocError
from prov.core.ids import kind_of, new_id
from prov.docs import register as docs
from prov.episodes.ingest import ingest
from prov.lineage import graph as lineage
from prov.storage import catalog
from test_episodes import make_lerobot
from test_phase5 import chain  # noqa: F401


def _publish(ctx, tmp_path: Path, kind: str, alias: str | None = None) -> str:
    src = tmp_path / f"{kind}.bin"
    src.write_bytes(b"x")
    return publish(ctx, src, kind, alias=alias).id


def _doc(repo: Path, text: str, name: str = "note.md") -> Path:
    path = repo / "notes" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    return path


def test_register_adds_frontmatter_with_id(repo, ctx):
    path = _doc(repo, "# Grasp notes\n\nNothing cited.\n")
    record = docs.register(ctx, [path])[0]
    assert kind_of(record.id) == "doc"
    assert path.read_text() == f"---\nid: {record.id}\n---\n# Grasp notes\n\nNothing cited.\n"
    assert (record.repo, record.path, record.title) == ("proj", "notes/note.md", "Grasp notes")
    assert docs.load(ctx, record.id) == record
    assert f"doc {record.id}" in git(ctx.registry, "log", "-1", "--format=%s")


def test_register_writes_id_into_existing_frontmatter(repo, ctx):
    path = _doc(repo, "---\nstatus: open\n---\nNo heading here.\n")
    record = docs.register(ctx, [path])[0]
    assert path.read_text() == f"---\nid: {record.id}\nstatus: open\n---\nNo heading here.\n"
    assert record.title == "note.md"
    assert docs.register(ctx, [path])[0].id == record.id


def test_cites_ids_and_aliases_anywhere(repo, ctx, tmp_path):
    ckpt = _publish(ctx, tmp_path, "checkpoint", alias="model:cube/1")
    fig = _publish(ctx, tmp_path, "figure")
    own = new_id("doc")
    path = _doc(repo, f"---\nid: {own}\nevidence: [model:cube/1]\n---\n# T\n\nSee {fig} and {own}.\n")
    record = docs.register(ctx, [path])[0]
    assert record.id == own
    assert record.versions[-1].cites == sorted([ckpt, fig])
    with catalog.connect(ctx) as con:
        assert set(con.execute("SELECT doc, target FROM doc_cites").fetchall()) == {(own, ckpt), (own, fig)}
        assert con.execute("SELECT repo, path, title FROM docs").fetchall() == [("proj", "notes/note.md", "T")]


def test_cites_a_registered_doc_and_an_alias_at_sentence_end(repo, ctx, tmp_path):
    ckpt = _publish(ctx, tmp_path, "checkpoint", alias="model:cube/0.1")
    first = docs.register(ctx, [_doc(repo, "# First\n", "first.md")])[0]
    second = docs.register(ctx, [_doc(repo, f"# Second\n\nBuilds on {first.id}, using model:cube/0.1.\n", "second.md")])[0]
    assert second.versions[-1].cites == sorted([ckpt, first.id])


def test_unknown_cite_fails_and_leaves_the_file(repo, ctx):
    text = f"# T\n\nUses {new_id('figure')}.\n"
    path = _doc(repo, text)
    with pytest.raises(DocError, match="not in the registry"):
        docs.register(ctx, [path])[0]
    assert path.read_text() == text


def test_loose_file_is_refused(ctx, tmp_path):
    loose = tmp_path / "loose" / "idea.md"
    loose.parent.mkdir()
    loose.write_text("# Idea\n")
    with pytest.raises(DocError, match="fold it into a journal first"):
        docs.register(ctx, [loose])[0]


def test_versions_follow_commit_dirty_and_cites(repo, ctx, tmp_path):
    path = _doc(repo, "# T\n")
    record = docs.register(ctx, [path])[0]
    assert [(v.commit, v.dirty, v.cites) for v in record.versions] == [(None, True, [])]
    assert len(docs.register(ctx, [path])[0].versions) == 1          # nothing changed: nothing appended
    git(repo, "add", "notes/note.md")
    git(repo, "commit", "-q", "-m", "note")
    head = git(repo, "rev-parse", "HEAD")
    record = docs.register(ctx, [path])[0]
    assert (record.versions[-1].commit, record.versions[-1].dirty) == (head, False)
    path.write_text(path.read_text() + "More.\n")
    record = docs.register(ctx, [path])[0]
    assert (record.versions[-1].commit, record.versions[-1].dirty) == (head, True)
    fig = _publish(ctx, tmp_path, "figure")
    path.write_text(path.read_text() + f"{fig}\n")
    record = docs.register(ctx, [path])[0]
    assert len(record.versions) == 4 and record.versions[-1].cites == [fig]


def test_remote_is_origin_or_none(repo, ctx, tmp_path):
    assert docs.register(ctx, [_doc(repo, "# T\n")])[0].remote == str(tmp_path / "origin.git")
    bare = tmp_path / "local"
    bare.mkdir()
    git(bare, "init", "-q", "-b", "main")
    assert docs.register(ctx, [_doc(bare, "# T\n")])[0].remote is None


def test_cli_register_and_show(repo, ctx, capsys, tmp_path):
    a, b = _doc(repo, "# A\n", "a.md"), _doc(repo, "# B\n", "b.md")
    assert main(["doc", "register", str(a), str(b)]) == 0
    ids = capsys.readouterr().out.split()
    assert [kind_of(i) for i in ids] == ["doc", "doc"]
    assert main(["show", ids[0]]) == 0
    out = capsys.readouterr().out
    assert f"id: {ids[0]}" in out and "path: notes/a.md" in out
    loose = tmp_path / "idea.md"
    loose.write_text("# Idea\n")
    assert main(["doc", "register", str(loose)]) == 2


def test_doc_joins_lineage(chain, repo, ctx):  # noqa: F811
    ckpt = aliases.resolve(ctx, "model:cube/0.1")
    record = docs.register(ctx, [_doc(repo, "# Result\n\nTrained as model:cube/0.1.\n")])[0]
    trace = lineage.trace(ctx, record.id)
    assert trace[0] == (0, record.id, f"{record.id}  doc, Result (proj/notes/note.md)")
    assert trace[1][1] == ckpt and trace[2][1] == chain["train"].id
    assert (1, record.id) in [(d, n) for d, n, _ in lineage.uses(ctx, ckpt)]


def test_doc_cites_an_episode(repo, ctx, tmp_path):
    _, eps = ingest(ctx, make_lerobot(tmp_path / "rec", [5]))
    record = docs.register(ctx, [_doc(repo, f"# T\n\nEpisode {eps[0].id}.\n")])[0]
    assert lineage.trace(ctx, record.id)[1] == (1, eps[0].id, f"{eps[0].id}  episode")


def test_batch_cites_an_unregistered_doc_in_the_same_batch(ctx, repo):
    a_id = new_id("doc")
    a = _doc(repo, f"---\nid: {a_id}\n---\n# A\n", "a.md")
    b = _doc(repo, f"# B\n\nBuilds on {a_id}.\n", "b.md")
    ra, rb = docs.register(ctx, [a, b])
    assert ra.id == a_id and rb.versions[-1].cites == [a_id]


def test_batch_with_one_unknown_cite_changes_no_file(ctx, repo):
    good = _doc(repo, "# Good\n", "good.md")
    bad = _doc(repo, f"# Bad\n\nUses {new_id('checkpoint')}.\n", "bad.md")
    before = good.read_text(), bad.read_text()
    with pytest.raises(DocError, match="bad.md"):
        docs.register(ctx, [good, bad])
    assert (good.read_text(), bad.read_text()) == before


def test_batch_is_one_registry_commit(ctx, repo, registry):
    paths = [_doc(repo, f"# Doc {i}\n", f"d{i}.md") for i in range(3)]
    docs.register(ctx, paths[:1])
    count = int(git(registry, "rev-list", "--count", "HEAD"))
    records = docs.register(ctx, paths)
    assert len(records) == 3
    assert int(git(registry, "rev-list", "--count", "HEAD")) == count + 1
