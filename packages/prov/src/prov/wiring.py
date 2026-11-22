"""The built-in extensions, in one place: what is plugged into each extension point.

To add one, write its module and add it here (CLI groups are listed in `prov.cli.main`).
"""

from prov.artifacts import tables as artifact_tables
from prov.core.context import Context
from prov.core.extensions import Extensions
from prov.datasets import tables as dataset_tables
from prov.episodes import tables as episode_tables
from prov.episodes.formats import lerobot
from prov.runs import tables as run_tables


def extensions() -> Extensions:
    return Extensions(
        tables=[run_tables.TABLES, artifact_tables.TABLES, episode_tables.TABLES, dataset_tables.TABLES],
        formats={lerobot.FORMAT.name: lerobot.FORMAT},
    )


def context() -> Context:
    """The Context for this machine and process, with the built-in extensions."""
    return Context.load(extensions())
