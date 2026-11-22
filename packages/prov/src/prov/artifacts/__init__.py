"""Layer 2: artifacts, the immutable files and folders runs read and make. Imports core, storage.

schema    ArtifactRecord
publish   publish (bytes into the store + record + alias), load, path; emits artifact.published
aliases   `kind:name/version` and `kind:name@label` names for IDs
tables    catalog tables: artifacts, aliases, alias_labels
"""
