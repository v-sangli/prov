# 0021. Skills ship as a Claude Code plugin, installed once per machine

Status: Accepted (2026-11-24)
Covers: `.claude-plugin/`, `packages/prov-skills/`
PR: (pending); commits `cc5cd5f` (spec), `5d08052` (plan, `docs/superpowers/plans/2026-11-24-skills-plugin.md`), `bdb5caf`, `9da2836`, `4f9a2d6`, `2b6e4c8`

## Context

ADR 0018 shipped the skills as directories inside the `prov_skills` package, linked into each
project by `prov-skills install <project>`. A machine runs several workspaces against one
registry, one store and one config, but the skills had to be linked into each one, and the
links pointed into whichever environment had the package installed. No skill told an agent how
to resolve prov IDs in general; only `plot` and `journal` existed.

## Decision

- The repo is a Claude Code marketplace named `prov` (`.claude-plugin/marketplace.json`) with one
  plugin, `prov-skills`, whose root is `packages/prov-skills/`. It is installed once per machine
  at user scope: `claude plugin marketplace add v-sangli/prov`, then
  `claude plugin install prov-skills@prov --scope user`.
- The plugin carries the skills under `packages/prov-skills/skills/`: `prov` (resolving IDs and
  aliases with `prov show / trace / uses / q`, recording with `prov run`, `prov.refs()` for other
  tools, citing IDs), `journal` and `plot`.
- The plugin carries one SessionStart hook. When a `prov.toml` is in the session's cwd or above
  it, it prints that the project uses prov and to read `journal/NOW.md`; elsewhere it prints
  nothing.
- `plugin.json`'s version is the `prov-skills` package version.
- The package keeps `prov_skills.plot`, the plot skill's code. `prov-skills install` and the
  `prov-skills` CLI are removed.

Amends ADR 0018: `prov-skills` is the plot module and the plugin, with no CLI; setting up a
project is `prov init` and `prov-journal init`. Amends ADR 0007: the plot skill is
`packages/prov-skills/skills/plot/SKILL.md`, reached through the plugin.

## Consequences

- Easier: every workspace on a machine sees the same skills, at the version the plugin was
  installed at; a new skill is one directory under `skills/`.
- Easier: an agent in a prov project is told so at session start, without a rule in each
  project.
- Harder: a skill edit reaches agents only after `claude plugin update prov-skills@prov`.
- A project that imports `prov_skills.plot` still installs the package in its own environment.

## Enforced by

`packages/prov-skills/tests/test_plugin.py`: the manifests parse and name each other, the plugin
version equals the package version, every skill directory has a SKILL.md with `name` matching
the directory, and the hook prints inside a prov project and nothing outside one.
