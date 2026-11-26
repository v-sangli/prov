"""Where everything lives. Registry paths are relative to the registry root, store paths to the
store root; every other module builds paths through these functions.

registry/
    records/runs/<run_id>.yaml
    records/artifacts/<kind>/<id>.yaml
    records/episodes/<ses_id>.jsonl          one EpisodeRecord per line
    records/annotations/<ses_id>.jsonl       one Annotation per line, append-only
    records/docs/<doc_id>.yaml               a doc and its versions
    datasets/<ds_id>.txt                     member episode IDs, one per line (episode selections)
    aliases/<alias kind>/<name>.yaml         versions and labels
    .prov.lock                               the write lock (untracked)
store/
    <kind dir>/<id>/...                      bytes, read-only once published
"""

from pathlib import Path

RUNS_DIR = "records/runs"
ARTIFACTS_DIR = "records/artifacts"
EPISODES_DIR = "records/episodes"
ANNOTATIONS_DIR = "records/annotations"
DOCS_DIR = "records/docs"
DATASETS_DIR = "datasets"
ALIASES_DIR = "aliases"

# Artifact kind -> store folder. Only these kinds have bytes in the store.
KIND_DIRS = {
    "raw": "raw",
    "session": "sessions",
    "dataset": "datasets",
    "checkpoint": "checkpoints",
    "benchmark": "benchmarks",
    "calibration": "calibrations",
    "result": "results",
    "figure": "figures",
    "video": "media",
}
MEDIA_DIR = KIND_DIRS["video"]
LOCK_FILE = ".prov.lock"


def registry_lock(registry: Path) -> Path:
    return registry / LOCK_FILE


def run_record(run_id: str) -> str:
    return f"{RUNS_DIR}/{run_id}.yaml"


def artifact_record(kind: str, id_: str) -> str:
    return f"{ARTIFACTS_DIR}/{kind}/{id_}.yaml"


def episodes_file(session_id: str) -> str:
    return f"{EPISODES_DIR}/{session_id}.jsonl"


def annotations_file(session_id: str) -> str:
    return f"{ANNOTATIONS_DIR}/{session_id}.jsonl"


def doc_record(doc_id: str) -> str:
    return f"{DOCS_DIR}/{doc_id}.yaml"


def dataset_members(ds_id: str) -> str:
    return f"{DATASETS_DIR}/{ds_id}.txt"


def alias_file(kind: str, name: str) -> str:
    return f"{ALIASES_DIR}/{kind}/{name}.yaml"


def store_dir(kind: str, id_: str) -> str:
    return f"{KIND_DIRS[kind]}/{id_}"
