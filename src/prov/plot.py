"""House style and figure publishing.

    from prov import plot
    with plot.style():
        fig, ax = plt.subplots()
        ...
    rec = plot.save_figure(fig, "closure", caption="Hand closure per checkpoint")
    plot.to_journal(rec, doc_dir)          # copies <fig_id>.png next to the journal doc

Palette: the dataviz reference categorical order (light surface), validated with its
validate_palette.js: all gates pass; slots 3-5 sit below 3:1 contrast, so every chart with two or
more series carries a legend or direct labels. Assign series in this order, never cycled; a ninth
series folds into "Other" or small multiples. One y-axis per chart.

Figures are written as PNG (journal) and PDF (paper) with timestamps and version strings stripped,
so the same inputs give the same bytes.
"""

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from prov import store
from prov.records import ArtifactRecord

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
SURFACE, TEXT, TEXT_SECONDARY, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"

RC = {
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "figure.figsize": (6.4, 4.0), "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight",
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "text.color": TEXT, "axes.labelcolor": TEXT_SECONDARY, "axes.edgecolor": BASELINE,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": TEXT_SECONDARY,
    "ytick.labelcolor": TEXT_SECONDARY, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "lines.linewidth": 2.0, "lines.markersize": 6, "lines.markeredgecolor": SURFACE,
    "lines.markeredgewidth": 1.0, "patch.linewidth": 0,
    "legend.frameon": False, "legend.fontsize": 9, "image.cmap": "Blues",
    "pdf.fonttype": 42, "svg.hashsalt": "prov",
}
_METADATA = {"png": {"Software": None}, "pdf": {"Creator": None, "Producer": None, "CreationDate": None}}


@contextmanager
def style():
    """Apply the house style inside a `with` block."""
    import matplotlib as mpl
    from cycler import cycler
    with mpl.rc_context({**RC, "axes.prop_cycle": cycler(color=CATEGORICAL)}):
        yield


def save_figure(fig, name: str, caption: str | None = None, alias: str | None = None,
                meta: dict[str, Any] | None = None) -> ArtifactRecord:
    """Write `name`.png and `name`.pdf, publish them as one figure artifact, return its record.
    Inside `prov run` the figure becomes the run's output."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / name
        folder.mkdir()
        for ext in ("png", "pdf"):
            fig.savefig(folder / f"{name}.{ext}", metadata=_METADATA[ext])
        return store.publish(folder, "figure", alias=alias,
                             meta={"name": name, "caption": caption, "files": [f"{name}.png", f"{name}.pdf"],
                                   **(meta or {})})


def to_journal(record: ArtifactRecord, doc_dir: Path) -> Path:
    """Copy the figure's PNG into a journal doc folder as <fig_id>.png; returns the copy."""
    src = store.resolve(record.uri) / f"{record.meta['name']}.png"
    dest = Path(doc_dir) / f"{record.id}.png"
    shutil.copyfile(src, dest)
    return dest
