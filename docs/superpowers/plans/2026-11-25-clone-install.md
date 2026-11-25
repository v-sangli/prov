# Clone install Implementation Plan

> **For agentic workers:** executed inline (superpowers:executing-plans).

**Goal:** skills are plain files with prefixed names; the plugin and its hook are gone.

## Contract

As in the spec (agreed 2026-11-25). Variation axis: skills.

### Task 1: test, renames, removals

1. `test_skills.py`: skill set `{prov, prov-journal, prov-plot}`; each SKILL.md `name` equals
   its directory. Delete `test_plugin.py`. Run: FAIL.
2. `git mv skills/journal skills/prov-journal`, `skills/plot skills/prov-plot`; set the names;
   fix cross-references between skills. Delete `.claude-plugin/` (root and package) and
   `hooks/`. Version 0.3.0. Run: PASS. Commit.

### Task 2: docs

README (package table, install section, package map), `prov_skills/__init__.py`, plot module
docstring, journal template README, ADR 0021 status line, ADR 0019 Covers path. Commit.
