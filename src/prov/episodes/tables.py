"""Catalog tables built from episode and annotation logs."""

from prov.core import layout
from prov.core.extensions import CatalogTables
from prov.episodes.schema import Annotation, EpisodeRecord
from prov.storage.catalog import utc

DDL = """
CREATE TABLE episodes (id VARCHAR PRIMARY KEY, session VARCHAR, episode_index INTEGER,
    length INTEGER, fps DOUBLE, duration_s DOUBLE, tasks VARCHAR[], source_kind VARCHAR,
    source_raw VARCHAR, source_path VARCHAR, start_s DOUBLE, end_s DOUBLE, calibrations VARCHAR[]);
-- every annotation ever made; `annotations` is the latest value per (episode, key)
CREATE TABLE annotation_log (episode VARCHAR, key VARCHAR, value VARCHAR, time TIMESTAMP);
CREATE VIEW annotations AS
    SELECT episode, key, arg_max(value, time) AS value, max(time) AS time
    FROM annotation_log GROUP BY episode, key;
"""


def _lines(folder, model):
    for p in sorted(folder.glob("*.jsonl")):
        for line in p.read_text().splitlines():
            if line.strip():
                yield model.model_validate_json(line)


def rows(ctx) -> dict[str, list[tuple]]:
    eps = _lines(ctx.registry / layout.EPISODES_DIR, EpisodeRecord)
    notes = _lines(ctx.registry / layout.ANNOTATIONS_DIR, Annotation)
    return {
        "episodes": [(e.id, e.session, e.episode_index, e.length, e.fps, e.duration_s, e.tasks,
                      e.source.kind, e.source.raw, e.source.path, e.source.start_s, e.source.end_s,
                      e.calibrations) for e in eps],
        "annotation_log": [(a.episode, a.key, a.value, utc(a.time)) for a in notes],
    }


TABLES = CatalogTables("episodes", DDL, rows)
