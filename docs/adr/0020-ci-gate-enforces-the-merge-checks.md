# 0020. A CI gate enforces the dev-flow merge checks

Status: Accepted (2026-11-22)
Covers: `scripts/pr_gate.py`, `.github/workflows/ci.yml`
PR: https://github.com/v-sangli/prov/pull/9

## Context

The dev-flow rules lean on mechanical checks that no test ran: unique ADR numbers, deviations
matching their registry, branch-only files deleted before merge, and a version raised on every
merge. Until now the PR review was their only enforcer.

## Decision

- `scripts/pr_gate.py` (standard library only) runs as the CI job `gate`, required on `main`
  beside `test`.
- Always: ADR file numbers under `docs/adr/` are unique; every `DEVIATION(<id>)` comment in a
  tracked file has a row in `DEVIATIONS.md`, and every row has a comment.
- On pull requests (`--base origin/<base>`): `spikes/`, `docs/superpowers/specs/` and
  `docs/superpowers/plans/` are gone; every package under `packages/` whose files changed raises
  its version above the base's; at least one package raises its version; a major bump comes with
  a change under `docs/adr/`.
- A branch behind `main` is refused by branch protection (strict status checks), not the gate.

## Consequences

- Every merge raises at least one package version, docs-only changes included.
- Adding a package means adding its `pyproject.toml` under `packages/`; the gate finds it.

## Enforced by

`.github/workflows/ci.yml` (`gate` job) and branch protection on `main` (required checks `test`
and `gate`).
