"""Public plotting API: `from prov import plot`. House style and figure publishing; see
`prov.integrations.plot` for the palette and rules.

    with plot.style():
        fig, ax = plt.subplots()
        ...
    rec = plot.save_figure(fig, "closure", caption="Hand closure per checkpoint")
    plot.to_journal(rec, doc_dir)          # copies <fig_id>.png next to the journal doc
"""

from pathlib import Path
from typing import Any

from prov.artifacts.schema import ArtifactRecord
from prov.integrations import plot as _plot
from prov.integrations.plot import (BASELINE, CATEGORICAL, GRID, MUTED, RC, SEQUENTIAL_BLUE, STATUS,  # noqa: F401
                                    SURFACE, TEXT, TEXT_SECONDARY, style)
from prov.wiring import context


def save_figure(fig, name: str, caption: str | None = None, alias: str | None = None,
                meta: dict[str, Any] | None = None) -> ArtifactRecord:
    """Write `name`.png and `name`.pdf, publish them as one figure artifact, return its record.
    Inside `prov run` the figure becomes the run's output."""
    return _plot.save_figure(context(), fig, name, caption=caption, alias=alias, meta=meta)


def to_journal(record: ArtifactRecord, doc_dir: Path) -> Path:
    """Copy the figure's PNG into a journal doc folder as <fig_id>.png; returns the copy."""
    return _plot.to_journal(context(), record, doc_dir)
