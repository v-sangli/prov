# 0006. The journal is an Obsidian vault of Markdown in each project repo, checked by `prov journal lint`

Status: Accepted (2026-11-10); amended by 0018 (moved)
Covers: `packages/prov-journal/src/prov_journal/`, `packages/prov-journal/src/prov_journal/cli.py`
PR: https://github.com/v-sangli/prov/pull/2

## Context
The last project's journal worked (NOW.md, one doc per topic per day, frozen past docs, verified
vs inferred claims), but evidence was cited by path and hand-typed commit, paths moved, and the
commit was often "uncommitted". It needs to stay plain text in git, readable in Obsidian, GitHub
and a served site (ADR 0011). Formerly design decision D6.

## Decision
- Each project repo has a `journal/` folder: an Obsidian vault of Markdown, committed with the
  project.
- `prov init <project>` creates, never overwriting: `prov.toml` (`project`, `repos = ["."]`),
  `journal/README.md` (the rules), `journal/NOW.md`, `journal/INDEX.md`, a `journal/media`
  symlink to `<store>/media`, `.gitignore` lines `journal/media` and
  `journal/.obsidian/workspace*.json`, and `.claude/skills/{journal,plotting}` symlinked to the
  skills shipped in `packages/prov-skills/src/prov_skills/`.
- Docs live at `journal/<YYYY>/<MM>/<YYYY-MM-DD>-<topic>/README.md`, one per topic per day; the
  topic is lowercase words joined by `-`. `prov journal new <topic> [--continues <doc>]` writes
  one from `templates/doc.md`.
- Frontmatter: `date`, `status` (`open` | `concluded` | `superseded`), `continues`,
  `superseded_by`, `evidence` (a list of IDs or aliases).
- `prov journal lint` runs every `LintCheck` in `wiring.py` and exits 1 on any problem:
  - `frontmatter`: present and valid, `date` matches the folder, known `status`
  - `links`: `continues` / `superseded_by` exist; a superseded doc names its successor
  - `evidence`: each entry resolves to a run, artifact or episode ID in the registry; paths fail
  - `body_ids`: every prov ID in the body is in the registry
  - `images`: every local `![...](path)` exists beside the doc
  - `now`: rows of NOW.md's `## Open threads` table are at most 300 characters
- `prov journal index` rewrites `journal/INDEX.md`: every doc, newest first, with status and
  evidence count.

## Consequences
- Easier: evidence that does not resolve fails lint, in frontmatter and body.
- Easier: INDEX.md renders the same in Obsidian, Quartz and GitHub (no Dataview).
- Harder: "past docs are frozen" and "mark every claim verified or inferred" are rules in the
  journal README and skill, not checks.
- Rules out citing evidence by path.

## Enforced by
- `packages/prov/tests/test_init.py::test_init_project`, `packages/prov-journal/tests/test_journal.py::test_init_journal`, `packages/prov-skills/tests/test_install.py::test_install`, `::test_new_doc`, `::test_continues_link_resolves`
- `packages/prov-journal/tests/test_journal.py::test_lint_evidence`
- `packages/prov-journal/tests/test_journal.py::test_lint_body_ids_images_and_frontmatter`
- `packages/prov-journal/tests/test_journal.py::test_lint_superseded_needs_link`, `::test_lint_now_thread_rows`
- `packages/prov-journal/tests/test_journal.py::test_index_lists_docs_newest_first`, `::test_cli`
- `packages/prov-journal/tests/test_lint_checks.py::test_new_lint_check`
- Frozen past docs and verified/inferred marks: nothing mechanical; the user's review.
