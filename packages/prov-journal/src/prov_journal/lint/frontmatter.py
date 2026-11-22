"""Every doc has valid frontmatter, a date matching its folder, and a known status."""

from prov_journal.lint.check import LintCheck
from prov_journal.docs import STATUSES


def check(view) -> list[str]:
    problems = []
    for doc in view.docs:
        if doc.meta is None:
            problems.append(f"{doc.rel}:1: missing or invalid frontmatter")
            continue
        folder_date = doc.path.parent.name[:10]
        if str(doc.meta.get("date")) != folder_date:
            problems.append(f"{doc.rel}:1: date {doc.meta.get('date')} does not match folder {folder_date}")
        status = doc.meta.get("status")
        if status not in STATUSES:
            problems.append(f"{doc.rel}:1: status {status!r} not one of {sorted(STATUSES)}")
    return problems


CHECK = LintCheck("frontmatter", check)
