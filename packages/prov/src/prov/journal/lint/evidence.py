"""`evidence:` is a list of IDs or aliases that resolve to something in the registry (not paths)."""

from prov.core.errors import AliasError
from prov.core.extensions import LintCheck
from prov.core.ids import ID_RE


def check(view) -> list[str]:
    problems = []
    for doc in view.with_meta():
        evidence = doc.meta.get("evidence") or []
        if not isinstance(evidence, list):
            problems.append(f"{doc.rel}:1: evidence must be a list")
            continue
        for ref in map(str, evidence):
            try:
                id_ = view.resolve(ref)
            except AliasError as exc:
                problems.append(f"{doc.rel}:1: {exc}")
                continue
            if not ID_RE.fullmatch(id_):
                problems.append(f"{doc.rel}:1: {ref!r} is not an ID or alias (evidence is IDs, not paths)")
            elif id_ not in view.known:
                problems.append(f"{doc.rel}:1: {ref} is not in the registry")
    return problems


CHECK = LintCheck("evidence", check)
