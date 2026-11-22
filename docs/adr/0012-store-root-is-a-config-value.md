# 0012. The store lives at `~/store` on the main NVMe; its root is a config value and records use `store://` URIs

Status: Accepted (2026-11-09)
Covers: `src/prov/storage/store.py`, `src/prov/core/layout.py` (`KIND_DIRS`), `src/prov/core/context.py` (`store_root`)
PR: https://github.com/v-sangli/prov/pull/2

## Context
There is no dedicated data disk yet; the store shares the system NVMe (ext4) after cleanup. A
data disk may come later, so moving the bytes must not rewrite every record. Formerly design
decision D12.

## Decision
- The store root is the machine config's required `store_root` key; this machine uses
  `~/store`. There is no default in code.
- Records never hold absolute store paths. An artifact's `uri` is
  `store://<kind dir>/<id>[/<file name>]`, resolved against `store_root` by `store.resolve`;
  the catalog's `artifacts.path` is the resolved path at build time. Moving the store is a config
  change plus a copy.
- Layout: one folder per artifact, named by ID, never by meaning, under its kind's folder:

  | Kind | Folder | Kind | Folder |
  | --- | --- | --- | --- |
  | raw | `raw/` | calibration | `calibrations/` |
  | session | `sessions/` | result | `results/` |
  | dataset | `datasets/` | figure | `figures/` |
  | checkpoint | `checkpoints/` | video | `media/` |
  | benchmark | `benchmarks/` | | |

  A published folder becomes `<kind dir>/<id>/`; a single file keeps its name inside it. Only
  these kinds can be published; `run` and `episode` have no bytes.
- `prov publish` and `prov run` log a warning when the store disk has under 50 GB free.

Not built: a managed `scratch/` folder; nothing in prov creates or reads it.

## Consequences
- Easier: the store can move to a dedicated disk without touching the registry.
- Harder: a full disk stops training and the OS together.
- Harder: ext4 has no reflinks, so any copy into the store costs its full size.
- Rules out absolute paths in records.

## Enforced by
- `tests/test_store.py::test_publish_moves_folder_under_its_id` (`uri == store://sessions/<id>`)
- `tests/test_store.py::test_publish_single_file` (`store://figures/<id>/closure.png`)
- `tests/test_store.py::test_unpublishable_kinds`
- `tests/test_store.py::test_cli_publish_and_show` (resolved path under `store_root`)
- Free-space warning: no test.
