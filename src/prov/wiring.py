"""The built-in extensions, in one place: what is plugged into each extension point.

To add one, write its module and add it here (CLI groups are listed in `prov.cli.main`).
"""

from prov.artifacts import tables as artifact_tables
from prov.core.context import Context
from prov.core.extensions import Extensions
from prov.datasets import tables as dataset_tables
from prov.episodes import tables as episode_tables
from prov.episodes.formats import lerobot
from prov.integrations import wandb
from prov.journal.lint import body_ids, evidence, frontmatter, images, links, now
from prov.runs import tables as run_tables


def extensions() -> Extensions:
    return Extensions(
        tables=[run_tables.TABLES, artifact_tables.TABLES, episode_tables.TABLES, dataset_tables.TABLES],
        formats={lerobot.FORMAT.name: lerobot.FORMAT},
        lint_checks=[frontmatter.CHECK, links.CHECK, evidence.CHECK, body_ids.CHECK, images.CHECK, now.CHECK],
        subscribers={event: list(fns) for event, fns in wandb.SUBSCRIBERS.items()},
    )


def context() -> Context:
    """The Context for this machine and process, with the built-in extensions."""
    return Context.load(extensions())
