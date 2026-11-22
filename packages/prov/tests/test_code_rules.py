"""Code-stance rules that can be checked on the source, over every package and test in the repo."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _python_files() -> list[Path]:
    return sorted(p for p in [*ROOT.glob("packages/*/src/**/*.py"), *ROOT.glob("packages/*/tests/*.py"),
                              ROOT / "conftest.py"])


def test_no_attribute_probes():
    """`hasattr` and `getattr(obj, name, default)` are banned: contracts are typed and closed."""
    offenders = [
        f"{p.relative_to(ROOT)}:{n.lineno}"
        for p in _python_files()
        for n in ast.walk(ast.parse(p.read_text()))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and (n.func.id == "hasattr" or (n.func.id == "getattr" and len(n.args) == 3))
    ]
    assert offenders == []
