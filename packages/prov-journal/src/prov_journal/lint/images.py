"""Every local image a doc embeds with `![...](path)` exists next to it."""

import re

from prov_journal.lint.check import LintCheck

IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")


def check(view) -> list[str]:
    problems = []
    for doc in view.with_meta():
        for n, line in enumerate(doc.text.splitlines()[doc.body_start:], start=doc.body_start + 1):
            for m in IMAGE_RE.finditer(line):
                target = m.group(1)
                if "://" not in target and not (doc.path.parent / target).exists():
                    problems.append(f"{doc.rel}:{n}: image {target} not found")
    return problems


CHECK = LintCheck("images", check)
