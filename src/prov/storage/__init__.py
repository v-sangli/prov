"""Layer 1: where records and bytes are kept. Imports core only.

registry  atomic writes and git commits in the registry repo
store     placing bytes under an ID, read-only; resolving store:// URIs; free-space warning
catalog   the DuckDB catalog engine: builds the tables the Extensions declare, rebuilds when stale
"""
