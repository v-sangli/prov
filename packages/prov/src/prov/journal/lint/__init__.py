"""`prov journal lint`: every LintCheck in `ctx.ext.lint_checks` runs over a JournalView.

Each rule is one module here exposing CHECK; register new ones in `prov.wiring`. A check returns
`path:line: message` strings, empty when its rule holds. Checks other than `frontmatter` skip docs
whose frontmatter is missing or invalid.
"""

from dataclasses import dataclass
from pathlib import Path

from prov.artifacts import aliases
from prov.journal.docs import Doc, docs
from prov.storage import catalog


@dataclass(frozen=True)
class JournalView:
    ctx: object
    root: Path
    docs: list[Doc]
    known: set[str]            # every run, artifact and episode ID in the registry

    def resolve(self, ref: str) -> str:
        """An alias or ID -> ID (raises AliasError)."""
        return aliases.resolve(self.ctx, ref) if ":" in ref else ref

    def with_meta(self) -> list[Doc]:
        return [d for d in self.docs if d.meta is not None]


def view(ctx, root: Path) -> JournalView:
    with catalog.connect(ctx) as con:
        known = {i for (i,) in con.execute(
            "SELECT id FROM runs UNION ALL SELECT id FROM artifacts UNION ALL SELECT id FROM episodes").fetchall()}
    return JournalView(ctx, root, docs(root), known)


def lint(ctx, root: Path) -> list[str]:
    """Problems as `path:line: message`; empty when the journal is clean."""
    v = view(ctx, root)
    return [problem for check in ctx.ext.lint_checks for problem in check.check(v)]
