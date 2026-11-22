# 0007. Plotting is our own module, `prov.plot`; figures4papers ideas only, no code copied

Status: Accepted (2026-11-10); amended by 0018 (moved)
Covers: `src/prov/plot.py`, `src/prov/integrations/plot.py`, `src/prov/journal/skills/plotting/`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Journal plots and paper figures should share one house style, be artifacts like everything else
(ADR 0001), and regenerate to identical bytes. figures4papers has good design ideas, but its
code is CC BY-NC 4.0. Formerly design decision D7.

## Decision
- `from prov import plot` is the public surface; the implementation is
  `prov.integrations.plot`. matplotlib is an optional extra (`.[plot]`).
- `plot.style()`: a context manager applying the house rcParams (`RC`) with the `CATEGORICAL`
  palette as the colour cycle; the previous rcParams are restored on exit. Palette and colour
  constants (`CATEGORICAL`, `SEQUENTIAL_BLUE`, `STATUS`, `SURFACE`, ...) are exported.
- `plot.save_figure(fig, name, caption=None, alias=None, meta=None)`: writes `<name>.png` and
  `<name>.pdf` into a folder with PNG `Software` and PDF `Creator` / `Producer` /
  `CreationDate` stripped, and publishes the folder as one `fig_` artifact (`meta`: `name`,
  `caption`, `files`). Inside `prov run` it becomes the run's output.
- `plot.to_journal(record, doc_dir)`: copies `<name>.png` next to a journal doc as
  `<fig_id>.png`.
- A `plotting` agent skill ships in `src/prov/journal/skills/plotting/SKILL.md` and is linked
  into projects by `prov init`. Helpers for recurring figures wait until projects show which
  recur.
- No figures4papers code is copied.

## Consequences
- Easier: one style for journal and paper; every figure has an ID, a producing run and a code
  snapshot.
- Easier: a rerun can be checked byte for byte.
- Harder: house style is ours to maintain.
- Rules out copying figures4papers code.

## Enforced by
- `tests/test_plot_rerun.py::test_style_applies_palette_and_restores`
- `tests/test_plot_rerun.py::test_save_figure_and_journal_copy`
- `tests/test_plot_rerun.py::test_rerun_reproduces_figure_byte_for_byte`
- No copied figures4papers code: nothing mechanical; the user's review.
