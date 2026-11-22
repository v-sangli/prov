"""NOW.md's open-threads table keeps one short line per thread."""

from prov_journal.lint.check import LintCheck

MAX_THREAD_ROW = 300


def check(view) -> list[str]:
    now = view.root / "NOW.md"
    if not now.is_file():
        return []
    problems, in_threads = [], False
    for n, line in enumerate(now.read_text().splitlines(), start=1):
        if line.startswith("## "):
            in_threads = line.strip().lower() == "## open threads"
        elif in_threads and line.startswith("|") and not set(line) <= set("|- :"):
            if len(line) > MAX_THREAD_ROW:
                problems.append(f"journal/NOW.md:{n}: thread row is {len(line)} chars; keep it to one "
                                f"line ({MAX_THREAD_ROW} max) and put the detail in the doc")
    return problems


CHECK = LintCheck("now", check)
