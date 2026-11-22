# Spec: prov is the core; prov-journal and prov-skills depend on it

Branch: `feat/split-packages` · Mode: `feat/` (public import paths and CLI names change) ·
Versions: prov 0.4.0, prov-journal 0.1.0, prov-skills 0.1.0

## Contract

- One repo, a uv workspace of three packages under `packages/`. `prov` imports neither
  `prov_journal` nor `prov_skills` (a CI test pins this); both depend on `prov`.
- `prov` (core): core, storage, runs (with rerun), artifacts, episodes (with the LeRobot
  format), datasets, lineage, api, cli. `prov init` writes `prov.toml` only.
- `prov-journal` (`import prov_journal`): docs, index, lint (the six rules; `LintCheck` and
  the built-in rule list move here from `prov.core.extensions` / `prov.wiring`), templates,
  the Quartz site. CLI `prov-journal init | new | lint | index | site build | serve`;
  `init` makes `journal/`, the media link and the `.gitignore` lines.
- `prov-skills` (`import prov_skills`): one directory per skill: `plot/` (SKILL.md, house
  style, `save_figure`, `to_journal`) and `journal/` (SKILL.md). CLI
  `prov-skills install <project>` links every skill into `<project>/.claude/skills/`.
- Behavior is otherwise unchanged. The oracle is the existing suite, moved with its code;
  the only edits allowed are imports and CLI invocations, each listed in the migration
  table. One test is split: rerun (core) reproduces a plain file instead of a figure.

## Variation axes

- prov: recording formats, catalog tables, CLI groups.
- prov-journal: journal lint rules (moves here).
- prov-skills: skills (one directory each; adding one touches nothing else).

## Agreed interface sketch (2026-11-21; own CLIs; `prov init` writes prov.toml only)

```
prov/                                  repo root: uv workspace, one CI
  pyproject.toml                       [tool.uv.workspace] members = ["packages/*"]
  conftest.py                          shared fixtures (registry, ctx, repo, git, make_lerobot)
  packages/
    prov/          import prov         CLI: prov ...; prov init → prov.toml only
    prov-journal/  import prov_journal CLI: prov-journal init|new|lint|index|site build|serve
    prov-skills/   import prov_skills  CLI: prov-skills install <project>
      src/prov_skills/plot/  src/prov_skills/journal/
    <pkg>/tests/
```

## Migration table

| From | To | Verify |
|---|---|---|
| `src/prov/{core,storage,runs,artifacts,episodes,datasets,lineage,cli}`, `api.py`, `wiring.py`, `__init__.py` | `packages/prov/src/prov/...` | prov tests pass unedited except import lines |
| `prov.journal.{docs,project,lint}`, `journal/templates/` | `prov_journal.{docs,project,lint}`, `prov_journal/templates/` | `test_journal.py` passes; edits: imports, `main([...])` → `prov_journal.cli.main([...])` |
| `prov.core.extensions.LintCheck`, `Extensions.lint_checks`, the rule list in `prov.wiring` | `prov_journal.lint.LintCheck`, `prov_journal.lint.CHECKS` | `test_extensions.py::test_new_lint_check` moves to prov-journal; edits: imports, how the extra check is passed |
| `prov.integrations.site` | `prov_journal.site` | `test_site.py` passes; edits: imports |
| `prov init` (prov.toml + journal + skills) | `prov init` (prov.toml) + `prov-journal init` + `prov-skills install` | `test_init_project` split into the three; same files created in total |
| `prov.cli.journal`, `prov.cli.site` | `prov_journal.cli` | CLI tests pass; edits: entry point |
| `prov.integrations.plot`, `prov.plot` | `prov_skills.plot` | plot tests pass; edits: imports |
| `prov.journal.skills/{journal,plotting}/SKILL.md` | `prov_skills/{journal,plot}/SKILL.md` | install test: both linked |
| `test_plot_rerun.py` rerun tests (reproduce a figure) | `packages/prov/tests/test_rerun.py` (reproduce a written file) | same assertions: byte-identical output, snapshot code not current code, unknown run |
| `tests/conftest.py` | repo-root `conftest.py` | every package's tests collect |
