# 0022. Skills are files in the clone; the installer links them

Status: Accepted (2026-11-25)
Covers: `packages/prov-skills/skills/`, `packages/prov-skills/tests/test_skills.py`
PR: (pending); commits `e92747c` (spec), `32b9fe0` (plan, `docs/superpowers/plans/2026-11-25-clone-install.md`), `fe5ded1`, `e37d7a9`

## Context

ADR 0021 shipped the skills as a Claude Code plugin from this repo's marketplace manifest. A
machine has one clone of prov at a release tag, with its own venv, and the harness installs
prov from that clone (agent-md ADR 0011). The plugin was a second copy of the same files,
kept by Claude Code, with its own update step, and its session-start hook duplicated what the
harness's own session start can say. As user-level skills without a plugin namespace,
`journal` and `plot` would collide with other skills of those names.

## Decision

- The skills are files at a fixed path: `packages/prov-skills/skills/<name>/SKILL.md`, its
  frontmatter `name` equal to `<name>`. That path is the contract with installers, which link
  each directory into `~/.claude/skills/<name>`.
- The skills are `prov`, `prov-journal` and `prov-plot`.
- This repo ships no plugin, no marketplace manifest and no hook. Telling a session that prov
  is installed, or that its cwd is a prov project, is the harness's job.

Supersedes ADR 0021.

## Consequences

- Easier: one clone holds the CLIs' code, the skills and the docs; an upgrade is one checkout.
- Easier: a new skill is one directory under `skills/`; the installer picks it up.
- Harder: a skill edit reaches sessions only when the machine's clone moves to a release with it.

## Enforced by

`packages/prov-skills/tests/test_skills.py`: the skill set is exactly `prov`, `prov-journal`,
`prov-plot`, and each SKILL.md's `name` is its directory's name.
