"""Layer 1: where records and bytes are kept. Imports core only.

registry  atomic writes and git commits in the registry repo
lock      the registry-wide write lock (flock), held for a whole write operation
store     placing bytes under an ID, read-only; resolving store:// URIs; free-space warning
catalog   the DuckDB catalog engine: builds the tables the Extensions declare, rebuilds when stale
"""
