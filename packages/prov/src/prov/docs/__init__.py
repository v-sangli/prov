"""Layer 3: docs, Markdown files in a git repo that cite prov IDs. Imports core, storage, artifacts.

schema    DocRecord, DocVersion
register  give a doc its doc_ ID and record a version of what it cites
tables    catalog tables: docs, doc_cites (latest version); lineage nodes and `cites` edges
"""
