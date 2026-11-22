---
name: journal
description: Use when recording experiments, findings, investigations, plans or decisions in a project that uses prov, or when reading what was tried before. Covers the journal layout, doc rules, evidence by ID, and prov journal new / lint / index.
---

# Project journal

The journal (`journal/` in the project repo) is what was tried, why, what was seen and what was
concluded. Read `journal/NOW.md` before starting work; the rules are in `journal/README.md`.

## Writing a doc

1. `prov journal new <topic> [--continues <doc folder>]` creates
   `journal/<YYYY>/<MM>/<YYYY-MM-DD>-<topic>/README.md` from the template.
2. Fill Question, Method (enough to redo it), Findings, Next. Every finding starts with
   **verified:** (measured; give the numbers) or **inferred:**.
3. `evidence:` in the frontmatter lists the IDs or aliases the findings rest on: runs, datasets,
   models, results, figures, episodes. Find them with `prov q`, `prov show`, `prov trace`.
   Never paths.
4. Figures: plotting skill, then `prov.plot.to_journal(rec, doc_dir)`; caption carries the ID.
5. `prov journal lint` must pass before you finish. Then `prov journal index`.
6. If the doc changes the big picture, update `journal/NOW.md` (one line per thread).

## Don'ts

- Don't edit a past doc's findings. Supersede it: `status: superseded`, `superseded_by:`.
- Don't paste data, logs or checkpoints into the journal; cite their IDs.
- Don't record credentials or secrets.
