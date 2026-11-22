from datetime import date
from pathlib import Path

import pytest

from prov.cli import main
from prov.artifacts.publish import publish
from prov.core.errors import JournalError
from prov.journal.docs import index, new_doc
from prov.journal.lint import lint
from prov.journal.project import init_project

D1, D2 = date(2026, 11, 9), date(2026, 11, 10)


@pytest.fixture
def project(registry, tmp_path, monkeypatch, ctx) -> Path:
    root = tmp_path / "cube-grasp"
    root.mkdir()
    monkeypatch.chdir(root)
    init_project(ctx, root, "cube-grasp")
    return root


def _set_frontmatter(doc: Path, **fields) -> None:
    text = doc.read_text()
    for k, v in fields.items():
        lines = text.splitlines()
        lines = [f"{k}: {v}" if l.startswith(f"{k}:") else l for l in lines]
        if not any(l.startswith(f"{k}:") for l in lines):
            lines.insert(1, f"{k}: {v}")
        text = "\n".join(lines) + "\n"
    doc.write_text(text)


def test_init_project(project, tmp_path, ctx):
    for p in ("prov.toml", "journal/README.md", "journal/NOW.md", "journal/INDEX.md"):
        assert (project / p).is_file(), p
    assert (project / "journal" / "media").resolve() == (tmp_path / "store" / "media").resolve()
    for skill in ("plotting", "journal"):
        assert (project / ".claude" / "skills" / skill / "SKILL.md").is_file()
    assert "journal/media" in (project / ".gitignore").read_text().splitlines()
    assert 'project = "cube-grasp"' in (project / "prov.toml").read_text()
    assert init_project(ctx, project, "cube-grasp") == []                     # idempotent, never overwrites


def test_new_doc(project):
    doc = new_doc("grasp-closure", today=D1)
    assert doc == project / "journal/2026/11/2026-11-09-grasp-closure/README.md"
    text = doc.read_text()
    assert "date: 2026-11-09" in text and "status: open" in text and "# Grasp closure" in text
    with pytest.raises(JournalError, match="one doc per topic per day"):
        new_doc("grasp-closure", today=D1)
    with pytest.raises(JournalError, match="lowercase"):
        new_doc("Grasp Closure", today=D1)


def test_continues_link_resolves(project, ctx):
    new_doc("grasp-closure", today=D1)
    doc = new_doc("grasp-closure", continues="2026/11/2026-11-09-grasp-closure", today=D2)
    assert "continues: ../../../2026/11/2026-11-09-grasp-closure/README.md" in doc.read_text()
    assert lint(ctx, project / "journal") == []
    with pytest.raises(JournalError, match="no such doc"):
        new_doc("other", continues="2026/11/nope", today=D2)


def test_lint_evidence(project, tmp_path, ctx):
    f = tmp_path / "evals.jsonl"
    f.write_text("{}\n")
    res = publish(ctx, f, "result", alias="res:evals/1")
    doc = new_doc("evals", today=D1)
    _set_frontmatter(doc, evidence=f"[{res.id}, res:evals/1]")
    assert lint(ctx, project / "journal") == []

    _set_frontmatter(doc, evidence="[res:evals/2, fig_00000000000000000000000000, /data/ckpt/model.pt]")
    problems = lint(ctx, project / "journal")
    assert len(problems) == 3
    assert "no version res:evals/2" in problems[0]
    assert "fig_00000000000000000000000000 is not in the registry" in problems[1]
    assert "not an ID or alias" in problems[2]


def test_lint_body_ids_images_and_frontmatter(project, tmp_path, ctx):
    f = tmp_path / "r.json"
    f.write_text("{}")
    res = publish(ctx, f, "result")
    doc = new_doc("body", today=D1)
    doc.write_text(doc.read_text() + f"\n- **verified:** see {res.id} and run_00000000000000000000000000\n"
                                      "![fig_X — caption](missing.png)\n")
    _set_frontmatter(doc, status="done", date="2026-11-08")
    problems = "\n".join(lint(ctx, project / "journal"))
    assert res.id not in problems
    assert "run_00000000000000000000000000 is not in the registry" in problems
    assert "image missing.png not found" in problems
    assert "status 'done'" in problems and "does not match folder" in problems


def test_lint_superseded_needs_link(project, ctx):
    old = new_doc("first", today=D1)
    _set_frontmatter(old, status="superseded")
    assert any("superseded without superseded_by" in p for p in lint(ctx, project / "journal"))
    new_doc("second", today=D2)
    _set_frontmatter(old, superseded_by="../../../2026/11/2026-11-10-second/README.md")
    assert lint(ctx, project / "journal") == []


def test_lint_now_thread_rows(project, ctx):
    now = project / "journal" / "NOW.md"
    now.write_text(now.read_text().replace(
        "| --- | --- | --- |", "| --- | --- | --- |\n| grasp | " + "detail " * 60 + "| [doc](x) |"))
    [problem] = lint(ctx, project / "journal")
    assert problem.startswith("journal/NOW.md:") and "one line" in problem


def test_index_lists_docs_newest_first(project):
    a = new_doc("first", today=D1)
    new_doc("second", today=D2)
    _set_frontmatter(a, status="concluded")
    text = index(project / "journal").read_text()
    rows = [l for l in text.splitlines() if l.startswith("| 2026")]
    assert rows == [
        "| 2026-11-10 | [Second](2026/11/2026-11-10-second/README.md) | open | 0 |",
        "| 2026-11-09 | [First](2026/11/2026-11-09-first/README.md) | concluded | 0 |",
    ]


def test_cli(project, capsys):
    assert main(["journal", "new", "closure"]) == 0
    doc = Path(capsys.readouterr().out.strip())
    assert doc.is_file()
    assert main(["journal", "lint"]) == 0 and "journal OK" in capsys.readouterr().out
    _set_frontmatter(doc, evidence="[ckpt_00000000000000000000000000]")
    assert main(["journal", "lint"]) == 1
    assert main(["journal", "index"]) == 0
    assert main(["init", "cube-grasp"]) == 0 and "already set up" in capsys.readouterr().out.splitlines()[-1]
