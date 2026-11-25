# prov-skills as a Claude Code plugin

Mode: `feat/` extend. Branch: `feat/skills-plugin`.

## Problem

Skills reach a project by `prov-skills install <project>`, which symlinks them into
`<project>/.claude/skills/`. Each workspace needs the step, the links point into one checkout's
site-packages, and a machine with several workspaces has no single copy. Nothing tells an agent
that IDs like `run_…` or `doc_…` resolve with `prov`: the only skills are `plot` and `journal`.

## Contract

- The prov repo is a Claude Code marketplace named `prov` with one plugin, `prov-skills`. A machine
  installs it once at user scope (`claude plugin marketplace add v-sangli/prov`,
  `claude plugin install prov-skills@prov --scope user`); every workspace on the machine sees it.
- The plugin carries three skills, `prov`, `journal` and `plot`, and one SessionStart hook. The
  hook prints a short context line only when a `prov.toml` sits in the session's cwd or above it;
  elsewhere it prints nothing and exits 0.
- The Python package `prov-skills` keeps `prov_skills.plot` (house style, `save_figure`,
  `to_journal`). The plugin's version is the package's version.
- `prov-skills install` and the `prov-skills` CLI are removed (code stance rule 10).

## Variation axes

- Skills stay the package's axis: a new skill is one directory under `packages/prov-skills/skills/`.
- Fixed: one plugin, one marketplace. A second plugin would be a second entry in
  `marketplace.json`; not built.

## Intake shape

Full integration: the plugin replaces the installer, as if skills had shipped this way from the
start.

## Sketch (agreed 2026-11-24)

```
.claude-plugin/marketplace.json        name "prov"; plugins: [{name "prov-skills", source "./packages/prov-skills"}]
packages/prov-skills/
  .claude-plugin/plugin.json           name "prov-skills", version == pyproject version (test)
  skills/prov/SKILL.md                 NEW: resolving IDs (show/trace/uses/q), prov run, prov.refs(), cite IDs
  skills/journal/SKILL.md              moved from src/prov_skills/journal/
  skills/plot/SKILL.md                 moved from src/prov_skills/plot/
  hooks/hooks.json                     SessionStart -> ${CLAUDE_PLUGIN_ROOT}/hooks/session_start.sh
  hooks/session_start.sh               prov.toml at or above cwd -> one context block; else silent
  src/prov_skills/plot/                unchanged
```

Removed: `src/prov_skills/cli.py`, `[project.scripts]`, `tests/test_install.py`,
`src/prov_skills/journal/`.

Version: prov-skills 0.1.1 -> 0.2.0.
