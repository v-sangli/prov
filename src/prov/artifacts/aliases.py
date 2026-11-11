"""Aliases: readable names for IDs.

    <kind>:<name>/<version>   a numbered version; set once, never changes
    <kind>:<name>@<label>     a moving label pointing at a version; every move is a registry commit

Stored as `<registry>/aliases/<kind>/<name>.yaml`:
    versions: {"1": ds_..., "2": ds_...}
    labels: {best: "2"}
"""

import re
from pathlib import Path

import yaml

from prov.core import layout
from prov.core.errors import AliasError
from prov.core.ids import kind_of
from prov.storage import registry

KINDS = {"ds": "dataset", "model": "checkpoint", "bench": "benchmark", "calib": "calibration",
         "ses": "session", "res": "result", "fig": "figure"}
_REF = re.compile(r"^(?P<kind>[a-z]+):(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:/(?P<version>[0-9][A-Za-z0-9.]*)|@(?P<label>[A-Za-z][A-Za-z0-9._-]*))$")


def parse(ref: str) -> tuple[str, str, str | None, str | None]:
    """(kind, name, version, label); exactly one of version/label is set."""
    m = _REF.match(ref)
    if not m or m["kind"] not in KINDS:
        raise AliasError(f"not an alias: {ref!r} (expected kind:name/version or kind:name@label, "
                         f"kind one of {sorted(KINDS)})")
    return m["kind"], m["name"], m["version"], m["label"]


def _read(reg: Path, kind: str, name: str) -> dict:
    path = reg / layout.alias_file(kind, name)
    data = yaml.safe_load(path.read_text()) if path.is_file() else {}
    return {"versions": data.get("versions") or {}, "labels": data.get("labels") or {}}


def _save(reg: Path, kind: str, name: str, data: dict, message: str) -> None:
    path = registry.write(reg, layout.alias_file(kind, name), yaml.safe_dump(data, sort_keys=True))
    registry.commit(reg, path, message)


def versions(ctx, kind: str, name: str) -> dict[str, str]:
    return _read(ctx.registry, kind, name)["versions"]


def set_version(ctx, ref: str, id_: str) -> None:
    kind, name, version, _ = parse(ref)
    if version is None:
        raise AliasError(f"{ref} is a label; set a version with kind:name/version")
    if kind_of(id_) != KINDS[kind]:
        raise AliasError(f"{id_} is not a {KINDS[kind]} ({kind}: aliases name a {KINDS[kind]})")
    reg = ctx.registry
    data = _read(reg, kind, name)
    existing = data["versions"].get(version)
    if existing == id_:
        return
    if existing:
        raise AliasError(f"{ref} already points at {existing}; versions never change")
    data["versions"][version] = id_
    _save(reg, kind, name, data, f"alias {ref} -> {id_}")


def set_label(ctx, ref: str, target: str) -> None:
    kind, name, _, label = parse(ref)
    tkind, tname, tversion, _ = parse(target)
    if label is None or tversion is None or (kind, name) != (tkind, tname):
        raise AliasError(f"use: label {kind}:{name}@<label> {kind}:{name}/<version>")
    reg = ctx.registry
    data = _read(reg, kind, name)
    if tversion not in data["versions"]:
        raise AliasError(f"{target} does not exist")
    old = data["labels"].get(label)
    if old == tversion:
        return
    data["labels"][label] = tversion
    _save(reg, kind, name, data, f"label {ref} -> {tversion}" + (f" (was {old})" if old else ""))


def resolve(ctx, ref: str) -> str:
    """An ID, `kind:name/version` or `kind:name@label` -> ID."""
    if ":" not in ref:
        kind_of(ref)        # validates
        return ref
    kind, name, version, label = parse(ref)
    data = _read(ctx.registry, kind, name)
    if label is not None:
        if label not in data["labels"]:
            raise AliasError(f"no label {ref}")
        version = data["labels"][label]
    if version not in data["versions"]:
        raise AliasError(f"no version {kind}:{name}/{version}")
    return data["versions"][version]


def all_aliases(ctx) -> tuple[list[tuple], list[tuple]]:
    """([(ref, kind, name, version, id)], [(ref, kind, name, label, version)]) for the catalog."""
    reg = ctx.registry
    vrows, lrows = [], []
    for path in sorted((reg / layout.ALIASES_DIR).glob("*/*.yaml")):
        kind, name = path.parent.name, path.stem
        data = _read(reg, kind, name)
        vrows += [(f"{kind}:{name}/{v}", kind, name, v, i) for v, i in data["versions"].items()]
        lrows += [(f"{kind}:{name}@{l}", kind, name, l, v) for l, v in data["labels"].items()]
    return vrows, lrows


def alias_of(ctx, id_: str) -> str | None:
    """The first version alias pointing at this ID, if any."""
    vrows, _ = all_aliases(ctx)
    return next((ref for ref, _, _, _, i in vrows if i == id_), None)
