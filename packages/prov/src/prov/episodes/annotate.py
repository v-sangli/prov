"""Episode labels (outcome, failure_type, tags, note, ...): an append-only log per session."""

from datetime import datetime, timezone

from prov.core import layout
from prov.core.errors import StoreError
from prov.core.ids import kind_of
from prov.episodes.schema import Annotation
from prov.storage import registry
from prov.storage.lock import RegistryLock


def session_of(ctx, episode_id: str) -> str:
    needle = f'"id":"{episode_id}"'
    for p in (ctx.registry / layout.EPISODES_DIR).glob("*.jsonl"):
        if needle in p.read_text():
            return p.stem
    raise StoreError(f"no episode {episode_id}")


def annotate(ctx, episode_id: str, labels: dict[str, str]) -> list[Annotation]:
    """Append labels to an episode; the latest value wins."""
    if kind_of(episode_id) != "episode":
        raise StoreError(f"{episode_id} is not an episode ID")
    with RegistryLock(ctx.registry):
        session_id = session_of(ctx, episode_id)
        now = datetime.now(timezone.utc)
        notes = [Annotation(episode=episode_id, key=k, value=v, time=now) for k, v in labels.items()]
        path = registry.append(ctx.registry, layout.annotations_file(session_id),
                               "".join(a.model_dump_json() + "\n" for a in notes))
        registry.commit(ctx.registry, path, f"annotate {episode_id}: {', '.join(labels)}")
    return notes
