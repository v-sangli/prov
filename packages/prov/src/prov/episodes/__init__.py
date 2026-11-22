"""Layer 3: sessions (recording folders) and their episodes. Imports core, storage, artifacts.

schema    EpisodeRecord, EpisodeSource, Annotation
formats/  one module per recording format (an IngestFormat each); lerobot is the built-in
ingest    publish a folder as a session, register one ep_ ID per episode
annotate  append labels to episodes (latest value wins)
tables    catalog tables: episodes, annotation_log, annotations (view); episode lineage nodes
"""
