"""`continues` and `superseded_by` point at docs that exist; superseded docs name their successor."""

from prov.core.extensions import LintCheck


def check(view) -> list[str]:
    problems = []
    for doc in view.with_meta():
        links = {"continues": doc.meta.get("continues")}
        if doc.meta.get("status") == "superseded":
            if not doc.meta.get("superseded_by"):
                problems.append(f"{doc.rel}:1: superseded without superseded_by")
            links["superseded_by"] = doc.meta.get("superseded_by")
        for key, link in links.items():
            if link and not (doc.path.parent / link).resolve().is_file():
                problems.append(f"{doc.rel}:1: {key} {link} does not exist")
    return problems


CHECK = LintCheck("links", check)
