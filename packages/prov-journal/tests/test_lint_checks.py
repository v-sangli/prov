"""The lint extension point takes a new rule without touching the code that runs the rules."""

from prov.core.context import init_project
from prov_journal.docs import new_doc
from prov_journal.lint import CHECKS, LintCheck, lint
from prov_journal.project import init_journal


def test_new_lint_check(ctx, tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    monkeypatch.chdir(root)
    init_project(root, "p")
    init_journal(ctx, root)
    new_doc("first")
    no_todo = LintCheck("no_todo", lambda view: [f"{d.rel}:1: TODO left" for d in view.docs if "TODO" in d.text])
    checks = [*CHECKS, no_todo]
    assert lint(ctx, root / "journal", checks) == []
    doc = [d for d in (root / "journal").rglob("README.md") if "first" in str(d)][0]
    doc.write_text(doc.read_text() + "\nTODO\n")
    assert [p.split(": ", 1)[1] for p in lint(ctx, root / "journal", checks)] == ["TODO left"]
