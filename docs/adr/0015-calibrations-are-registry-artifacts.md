# 0015. Calibrations and robot config files are registry artifacts; episodes reference the calibration they were recorded with

Status: Accepted (2026-11-10)
Covers: `packages/prov/src/prov/core/ids.py` (`calib_`), `packages/prov/src/prov/core/layout.py` (`calibrations/`), `packages/prov/src/prov/artifacts/aliases.py` (`calib:`), `packages/prov/src/prov/episodes/ingest.py` (`calibrations`)
PR: https://github.com/v-sangli/prov/pull/2

## Context
Recordings depend on camera intrinsics and extrinsics, hand offsets and robot config files that
change over time. A recording is only interpretable with the calibration in force when it was
made, so that calibration must be pinned, not looked up later by path. Formerly design decision
D17.

## Decision
- A calibration is an artifact of kind `calibration`: ID prefix `calib_`, bytes under
  `<store>/calibrations/<calib_id>/`, published with `prov publish --kind calibration` or
  `prov.publish(..., "calibration")`, read-only like any artifact.
- Its alias kind is `calib`: versions `calib:<name>/<n>`, and labels such as `@current` that
  move to the version in force (`prov alias label calib:<name>@current calib:<name>/<n>`).
  `@current` is a convention; the code gives no label special meaning.
- `prov ingest ... --calib <calib_id>` (repeatable) records the IDs on every episode of the
  session as `calibrations`. Each must be a calibration ID with a record in the registry,
  checked before anything moves. Aliases are not accepted there; pass the resolved ID.
- The catalog's `episodes.calibrations` column holds the list.
- In code, `prov.path(prov.load("calib:<name>@current"))` gives the bytes and records the
  calibration as a run input.

## Consequences
- Easier: every episode names the exact calibration it was recorded with.
- Easier: moving `@current` never changes what past episodes reference.
- Harder: recording tools must pass `--calib` at ingest; an episode ingested without it records
  none.
- Rules out referencing calibrations by file path.

## Enforced by
- `packages/prov/tests/test_ids.py::test_calibration_kind`
- `packages/prov/tests/test_episodes.py::test_calibrations`
- `packages/prov/tests/test_datasets.py::test_publish_alias_checked_before_moving` (`calib:wrist/1`)
