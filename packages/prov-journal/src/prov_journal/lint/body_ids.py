"""Every ID mentioned in a doc's body is in the registry."""

from prov_journal.lint.check import LintCheck
from prov.core.ids import ID_RE


def check(view) -> list[str]:
    problems = []
    for doc in view.with_meta():
        for n, line in enumerate(doc.text.splitlines()[doc.body_start:], start=doc.body_start + 1):
            for m in ID_RE.finditer(line):
                if m.group(0) not in view.known:
                    problems.append(f"{doc.rel}:{n}: {m.group(0)} is not in the registry")
    return problems


CHECK = LintCheck("body_ids", check)
