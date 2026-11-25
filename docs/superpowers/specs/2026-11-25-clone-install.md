# Skills as files in the clone; no plugin

Mode: `feat/` extend (replaces ADR 0021's delivery). Branch: `feat/clone-install`.

## Problem

ADR 0021 shipped the skills as a Claude Code plugin from a marketplace manifest. The user's
model is simpler: one clone of this repo per machine, at a release tag, with its own venv; the
harness links what it needs from that clone. A plugin is a second copy managed by Claude Code
and adds a mechanism nobody needs. Skill names `journal` and `plot`, loaded at user level with
no plugin namespace, would also collide with other skills.

## Contract

- The skills are files at a fixed path: `packages/prov-skills/skills/<name>/SKILL.md`, the
  frontmatter `name` equal to `<name>`. An installer (the harness) links each directory into
  `~/.claude/skills/<name>`. This repo ships no installer and no plugin.
- Skills: `prov`, `prov-journal` (was `journal`), `prov-plot` (was `plot`).
- Removed: `.claude-plugin/marketplace.json`, `packages/prov-skills/.claude-plugin/`,
  `packages/prov-skills/hooks/` (the session-start context moves to the harness).
- prov-skills 0.2.0 -> 0.3.0.

## Variation axes

Skills stay the axis: one directory under `skills/`, nothing else touched.

## Intake shape

Full integration: as if skills had always been plain files read by the installer.

## Sketch (agreed 2026-11-25)

```
packages/prov-skills/skills/prov/SKILL.md
packages/prov-skills/skills/prov-journal/SKILL.md     renamed from journal/
packages/prov-skills/skills/prov-plot/SKILL.md        renamed from plot/
packages/prov-skills/tests/test_skills.py             replaces test_plugin.py: name == directory, the set
```
