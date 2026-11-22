---
name: plot
description: Use when making any figure from experiment results (eval numbers, benchmark logs, training curves exported for a doc) in a project that uses prov. Covers loading inputs by ID, the house style, publishing with save_figure, and embedding in the journal.
---

# Plotting with prov

Every figure that goes into a journal doc or a paper is made by a committed script, run through
`prov run`, from inputs loaded by ID. Then `prov trace <fig_id>` explains it and `prov rerun
<run_id>` regenerates it byte for byte.

## Rules

1. **Script in the repo.** Put it in the project's `analysis/`, commit it (a dirty run still works:
   the snapshot is kept), and run it with an interpreter outside the repo:
   `prov run --kind analysis -- python analysis/<name>.py`.
2. **Inputs by ID, never by path.** `rec = prov.load("res:evals/3")` (or an ID), then
   `prov.path(rec)` for the file. A path typed into the script is not lineage.
3. **House style.** Draw inside `with prov_skills.plot.style():`. Series take `prov_skills.plot.CATEGORICAL` in
   order, never cycled; past 8 series fold into "Other" or small multiples (scatter-like charts:
   past 3). One y-axis per chart: two measures of different scale are two charts.
4. **Identity is never color alone.** Two or more series always get a legend or direct labels.
   Slots 3-5 are below 3:1 contrast on the light surface, so this is required, not optional.
5. **Publish with `prov_skills.plot.save_figure(fig, name, caption=...)`.** It writes PNG + PDF without
   timestamps and records the figure as the run's output. Don't call `fig.savefig` for anything
   that will be cited.
6. **Journal embed.** `prov_skills.plot.to_journal(rec, doc_dir)` copies `<fig_id>.png` next to the doc.
   Embed it with the ID in the caption: `![fig_01J... — caption](fig_01J....png)`, and list the
   figure ID in the doc's `evidence`.
7. **Throwaway plots stay out.** Exploratory plots can live in a scratch folder; they never go in
   a journal doc.

## Template

```python
"""<What the figure shows>. Usage: prov run --kind analysis -- python analysis/<name>.py"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import prov
from prov_skills import plot

rows = [json.loads(l) for l in open(prov.path(prov.load("res:<name>/<n>")))]
with plot.style():
    fig, ax = plt.subplots()
    ...
    ax.set_title("<claim the figure supports>")
    ax.set_xlabel("<unit>")
    ax.set_ylabel("<unit>")
    ax.legend()
    rec = plot.save_figure(fig, "<name>", caption="<one sentence>")
print(rec.id)
```
