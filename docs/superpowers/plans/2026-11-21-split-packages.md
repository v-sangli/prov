# Split Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** One uv-workspace repo with `prov` (core), `prov-journal` and `prov-skills`; prov imports neither tool.

**Architecture:** Move code with `git mv` so history follows; fix imports; give each tool its own argparse CLI modelled on `prov.cli.main`; shared fixtures in a repo-root `conftest.py`.

**Tech Stack:** Python 3.12, uv workspace, hatchling, pytest, ruff 0.8.4.

## Global Constraints

- Versions: prov 0.4.0, prov-journal 0.1.0, prov-skills 0.1.0. Each package has its own `pyproject.toml` (hatchling, `src/` layout); the root `pyproject.toml` declares the workspace and the ruff/pytest config.
- Test edits are allowed only where the spec's migration table lists them.
- Commands from the repo root: `uv pip install --python .venv/bin/python -e packages/prov -e packages/prov-journal -e "packages/prov-skills[plot]" pytest` then `.venv/bin/python -m pytest -q` and `uvx ruff@0.8.4 check packages conftest.py`.
- Never use `$(...)` or backticks in shell commands.

## Contract

- Decision: the spec's Contract, unchanged.
- Sketch: the spec's "Agreed interface sketch", unchanged.
- Variation axes: the spec's list.

---

### Task 1: workspace skeleton and the prov core move
- `git mv src/prov packages/prov/src/prov`, `git mv tests packages/prov/tests`; move `tests/conftest.py` to the repo root; root `pyproject.toml` becomes the workspace (`[tool.uv.workspace] members = ["packages/*"]`, pytest `testpaths = ["packages/prov/tests", "packages/prov-journal/tests", "packages/prov-skills/tests"]`, the ruff config); `packages/prov/pyproject.toml` carries the old project metadata at 0.4.0 (dependencies pydantic, pyyaml, duckdb; extra `test`).
- Verify: full suite passes from the root before anything else moves.

### Task 2: prov-journal
- `git mv` journal docs/project/lint/templates and `integrations/site` into `packages/prov-journal/src/prov_journal/`; `LintCheck` and the rule list move into `prov_journal.lint` (`CHECKS`); `Extensions` loses `lint_checks`, `prov.wiring` loses the lint imports; `prov_journal/cli.py` holds the journal and site commands (from `prov.cli.journal` / `prov.cli.site`) under `prov-journal`; `prov_journal.project.init_journal` makes journal/, media link, .gitignore lines; `prov init` writes prov.toml only. Move the journal, site and lint-extension tests to `packages/prov-journal/tests/` with migration-table edits only.
- Verify: full suite.

### Task 3: prov-skills
- `git mv integrations/plot.py` → `prov_skills/plot/` (style, save_figure, to_journal; `prov/plot.py` facade deleted), the two SKILL.md files → `prov_skills/plot/SKILL.md`, `prov_skills/journal/SKILL.md`; `prov_skills/cli.py` `install <project>` links every directory holding a SKILL.md (the logic from the old `init_project`). Extra `plot` = matplotlib. Split `test_plot_rerun.py`: plot tests → `packages/prov-skills/tests/`, rerun tests → `packages/prov/tests/test_rerun.py` reproducing a written file.
- Verify: full suite.

### Task 4: invariants, CI, docs
- `packages/prov/tests/test_layers.py`: LAYERS without journal/integrations/plot; new test: no module under `packages/prov/src` imports `prov_journal` or `prov_skills`.
- CI installs the three packages and runs pytest and ruff over `packages`.
- README (repo root): what each package is, setup, package map, axes; `docs/usage.md` command names; ADR 0018 (Accepted at finalize) "prov is the core; tools depend on it"; ADR 0006 and 0007 statuses "amended by 0018 (moved)"; ADR index row.
- Verify: full suite, lint, `grep -rn 'prov.journal\|prov.integrations\|from prov import plot' packages docs README.md` empty (outside ADR history).
