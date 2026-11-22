"""Train / holdout splits. Deterministic for a given seed."""

import random

from prov.core.errors import DatasetError

BY = ("episode", "session")


def split(ids: list[str], sessions: dict[str, str], holdout: float, seed: int, by: str) -> tuple[list, list]:
    """(train, held) sorted. By episode: round(holdout * n) episodes, at least one. By session: whole
    sessions in shuffled order until at least holdout * n episodes are held."""
    rng = random.Random(seed)
    if by == "episode":
        shuffled = sorted(ids)
        rng.shuffle(shuffled)
        k = max(1, round(holdout * len(ids)))
        return sorted(shuffled[k:]), sorted(shuffled[:k])
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(sessions[i], []).append(i)
    order = sorted(groups)
    rng.shuffle(order)
    held: list[str] = []
    for ses in order:
        if len(held) >= holdout * len(ids):
            break
        held += groups[ses]
    if len(held) == len(ids):
        raise DatasetError("session split would hold out every episode; use more sessions or a smaller fraction")
    return sorted(set(ids) - set(held)), sorted(held)
