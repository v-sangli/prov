"""Layer 0: the vocabulary every other package shares. Imports nothing from prov.

errors      ProvError and its subclasses
ids         `<prefix>_<ULID>` IDs
layout      every registry and store path
schema      the base record model (YAML / JSON round-trip)
runenv      the environment-variable contract between `prov run` and the wrapped process
context     machine config, project config, and the Context passed to library functions
extensions  the extension-point types and the Extensions bundle
log         the `prov` logger
"""
