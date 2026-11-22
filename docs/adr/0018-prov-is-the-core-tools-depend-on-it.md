# 0018. prov is the core; prov-journal and prov-skills depend on it

Status: Accepted (2026-11-21)
Covers: `pyproject.toml`, `conftest.py`, `packages/prov/`, `packages/prov-journal/`, `packages/prov-skills/`
PR: pending (spec and plan 60ad085)

## Context

ADR 0017 made prov import none of the tools that use it. The journal, its Quartz sites, the
plotting module and the agent skills still lived inside prov, so `prov init` wrote a journal and
linked skills, `Extensions` carried journal lint rules, and prov's layers had a tool layer (6)
that the core never needed. A project that wants records without a journal, or a skill without
the journal, had no way to take one part alone.

## Decision

- One repo, a uv workspace of three packages under `packages/`; the root `pyproject.toml`
  declares the workspace and the pytest / ruff config, the root `conftest.py` the shared
  fixtures. Versions: prov 0.4.0, prov-journal 0.1.0, prov-skills 0.1.0.
- `prov` (core): core, storage, runs (with rerun), artifacts, episodes (with the LeRobot format),
  datasets, lineage, api, cli. `prov init <project>` writes `prov.toml` only
  (`prov.core.context.init_project`).
- `prov-journal` (`import prov_journal`): docs, project, lint, templates, site, cli.
  `LintCheck` and the built-in rule list move here as `prov_journal.lint.LintCheck` and
  `prov_journal.lint.CHECKS`; `lint(ctx, root, checks=CHECKS)` takes the rules to run.
  `Extensions` loses `lint_checks`. CLI `prov-journal init | new | lint | index | site build |
  serve`; `init` makes `journal/`, the `journal/media` link and the `.gitignore` lines.
- `prov-skills` (`import prov_skills`): one directory per skill holding its SKILL.md: `plot/`
  (also the house style, `save_figure`, `to_journal`; `from prov_skills import plot`) and
  `journal/`. CLI `prov-skills install <project>` links every skill into
  `<project>/.claude/skills/`. matplotlib is the `plot` extra.
- prov imports neither `prov_journal` nor `prov_skills`; both depend on `prov`.
- Removed, with no alias left behind: `prov.journal`, `prov.integrations`, `prov.plot`,
  `prov journal ...`, `prov site ...`, the `plotting` skill name (now `plot`).

Amends, by moving their code without changing its behavior:

- ADR 0006: the journal is `prov_journal`; its commands are `prov-journal ...`; `prov init` no
  longer makes the journal or links skills.
- ADR 0007: plotting is `prov_skills.plot`; the skill is `plot`.

## Consequences

- Easier: a project takes prov alone, or adds the journal or the skills by installing them.
- Easier: a new skill is one directory under `prov_skills/`; nothing else changes.
- Harder: setting up a project is three commands (`prov init`, `prov-journal init`,
  `prov-skills install .`) instead of one.
- Variation axes: prov keeps recording formats, catalog tables and CLI groups; journal lint
  rules move to prov-journal; skills are prov-skills' axis.

## Enforced by

- `packages/prov/tests/test_layers.py::test_core_imports_no_tool`
- `packages/prov/tests/test_layers.py::test_every_module_has_a_layer` (no journal, integrations
  or plot layer)
- `packages/prov/tests/test_init.py::test_init_project`
- `packages/prov-journal/tests/test_journal.py::test_init_journal`
- `packages/prov-journal/tests/test_lint_checks.py::test_new_lint_check`
- `packages/prov-skills/tests/test_install.py::test_install`
- `packages/prov/tests/test_rerun.py`
