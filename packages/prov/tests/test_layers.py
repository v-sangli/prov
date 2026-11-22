"""The package's dependency rule, checked on the source: a module imports only from its own package
or from lower layers, and never imports prov inside a function (hidden, late dependencies)."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
LAYERS = {
    "prov.core": 0,
    "prov.storage": 1,
    "prov.runs": 2, "prov.artifacts": 2,
    "prov.episodes": 3,
    "prov.datasets": 4,
    "prov.lineage": 5,
    "prov.journal": 6, "prov.integrations": 6,
    "prov.wiring": 7,
    "prov.api": 8, "prov.plot": 8,
    "prov.cli": 9, "prov": 9,
}


def _unit(module: str) -> str:
    """The layered unit a module belongs to: its top package under prov, or prov itself."""
    parts = module.split(".")
    return ".".join(parts[:2]) if len(parts) > 1 and ".".join(parts[:2]) in LAYERS else "prov"


def _modules() -> dict[str, Path]:
    out = {}
    for path in sorted((SRC / "prov").rglob("*.py")):
        parts = list(path.relative_to(SRC).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = path
    return out


def _prov_imports(path: Path):
    """(line, imported module, at top level?) for every prov import."""
    tree = ast.parse(path.read_text())
    top = {id(n) for n in tree.body}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
            if node.module == "prov":
                names = [f"prov.{a.name}" for a in node.names]
        else:
            continue
        for name in names:
            if name == "prov" or name.startswith("prov."):
                yield node.lineno, name, id(node) in top


MODULES = _modules()


@pytest.mark.parametrize("module", sorted(MODULES))
def test_imports_go_down(module):
    unit = _unit(module)
    problems = []
    for line, target, at_top in _prov_imports(MODULES[module]):
        if not at_top:
            problems.append(f"line {line}: imports {target} inside a function")
        tunit = _unit(target)
        if tunit != unit and LAYERS[tunit] >= LAYERS[unit]:
            problems.append(f"line {line}: {unit} (layer {LAYERS[unit]}) imports {target} "
                            f"(layer {LAYERS[tunit]})")
    assert not problems, "\n".join(problems)


def test_every_module_has_a_layer():
    assert all(_unit(m) in LAYERS for m in MODULES)
    assert {_unit(m) for m in MODULES} == set(LAYERS)


def test_library_code_does_not_print():
    offenders = [m for m, p in MODULES.items() if _unit(m) not in ("prov.cli",)
                 and any(isinstance(n, ast.Call) and getattr(n.func, "id", None) == "print"
                         for n in ast.walk(ast.parse(p.read_text())))]
    assert offenders == []
