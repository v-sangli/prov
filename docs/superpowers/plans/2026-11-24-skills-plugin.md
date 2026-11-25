# prov-skills plugin Implementation Plan

> **For agentic workers:** executed inline (superpowers:executing-plans).

**Goal:** ship the prov skills as one user-scope Claude Code plugin, `prov-skills@prov`, and remove
`prov-skills install`.

**Architecture:** the repo root holds the marketplace manifest; `packages/prov-skills/` is both the
Python package (plot module) and the plugin root (manifest, skills, hook).

**Tech stack:** Claude Code plugin manifests (JSON), Bash hook, pytest.

## Global Constraints

- prov-skills version 0.2.0 in `packages/prov-skills/pyproject.toml` and `plugin.json`.
- No `$(...)` or backticks-as-substitution in the hook script.
- Ruff 0.8.4 clean.

## Contract

- Decision: the repo is the `prov` marketplace with one plugin `prov-skills` rooted at
  `packages/prov-skills/`; skills `prov`, `journal`, `plot`; a SessionStart hook that speaks only
  inside a prov project; the installer CLI is deleted.
- Sketch: as in the spec (agreed 2026-11-24).
- Variation axes: skills (one directory under `skills/`); one plugin fixed.

---

### Task 1: plugin skeleton, moved skills, installer removed

Files: create `.claude-plugin/marketplace.json`, `packages/prov-skills/.claude-plugin/plugin.json`,
`packages/prov-skills/tests/test_plugin.py`; move `src/prov_skills/{journal,plot}/SKILL.md` to
`skills/{journal,plot}/SKILL.md`; delete `src/prov_skills/cli.py`, `tests/test_install.py`,
`[project.scripts]`; version 0.2.0.

1. Write `test_plugin.py`: manifests parse; marketplace names `prov-skills` with source
   `./packages/prov-skills`; plugin name and version equal the pyproject's; each `skills/*/`
   holds a SKILL.md whose frontmatter `name` is the directory name; skill set is
   `{prov, journal, plot}`.
2. Run: `.venv/bin/python -m pytest -q packages/prov-skills` → FAIL (no manifests).
3. Add manifests, `git mv` the SKILL.md files, delete the installer, bump the version.
4. `claude plugin validate .` and `claude plugin validate packages/prov-skills` pass.
5. Commit.

### Task 2: the `prov` skill

File: `packages/prov-skills/skills/prov/SKILL.md`: when to use (any `<prefix>_<ULID>` or alias,
any run, dataset, figure or doc), resolving (`prov show / trace / uses / q`), recording (`prov
run`, `prov.load`, `prov.publish`), other tools (`prov.refs()`), citing (IDs, never paths),
docs (`prov doc register`, `prov-journal register`). The Task 1 test turns green. Commit.

### Task 3: SessionStart hook

Files: `packages/prov-skills/hooks/hooks.json`, `packages/prov-skills/hooks/session_start.sh`
(executable); tests in `test_plugin.py`: run the script with cwd a subdirectory of a tmp project
holding `prov.toml` → stdout names prov and the project root; cwd a tmp dir with none → empty
stdout, exit 0. Red first, then the script. Commit.

### Task 4: docs and ADRs

README (setup, project, package map, extending, axes), `docs/usage.md` (workflow step 1, command
list), `prov_skills/__init__.py` docstring, ADR 0018 status line names 0021. Commit.
