# Architecture decisions

One file per decision, written against the code as it is. Numbers are sequential.

| ADR | Decision | Formerly |
| --- | --- | --- |
| [0001](0001-custom-registry-owns-dataset-versioning.md) | A custom registry, not DVC or MLflow, owns records and dataset versions | D1 |
| [0002](0002-duckdb-catalog-rebuilt-from-registry.md) | DuckDB is the query engine, rebuilt from registry records only | D2 |
| [0003](0003-wandb-reference-artifacts.md) | W&B holds runs and curves; artifacts reach it as references to registry records (superseded by 0017) | D3 |
| [0004](0004-ulid-ids-with-kind-prefix-and-aliases.md) | IDs are ULIDs with a kind prefix; readable aliases sit on top | D4 |
| [0005](0005-every-run-snapshots-its-working-tree.md) | Uncommitted code is allowed; every run snapshots each repo's working tree | D5 |
| [0006](0006-journal-is-an-obsidian-vault-per-project.md) | The journal is an Obsidian vault of Markdown in each project repo | D6 |
| [0007](0007-own-plotting-module.md) | Plotting is our own module, `prov.plot`; no figures4papers code | D7 |
| [0008](0008-one-infrastructure-project-is-a-tag.md) | One infrastructure for all projects; the project is a field on every run | D8 |
| [0009](0009-raw-formats-mcap-and-lerobot.md) | Raw formats are MCAP (exported to LeRobot) and LeRobot from teleop | D9 |
| [0010](0010-no-backup-disk-git-remotes-are-the-off-machine-copy.md) | No backup disk; git remotes are the only off-machine copy | D10 |
| [0011](0011-quartz-sites-served-over-tailscale.md) | Docs are read remotely through Quartz sites served over Tailscale | D11 |
| [0012](0012-store-root-is-a-config-value.md) | The store root is a config value; records use `store://` URIs | D12 |
| [0013](0013-record-schemas-are-pydantic-models.md) | Record schemas are pydantic models, closed to unknown fields | D13 |
| [0014](0014-no-content-hashing-id-is-identity.md) | No content hashing: the ID is the identity, folders are read-only | D14 |
| [0015](0015-calibrations-are-registry-artifacts.md) | Calibrations are registry artifacts; episodes reference theirs | D17 |
| [0016](0016-one-registry-wide-write-lock.md) | One registry-wide lock serializes every registry write | - |
| [0017](0017-integrate-by-reference-only.md) | prov integrates by reference only; the W&B integration and the event system go | - |
| [0018](0018-prov-is-the-core-tools-depend-on-it.md) | prov is the core; prov-journal and prov-skills depend on it | - |

D15 (operating knowledge in the handbook) and D16 (credentials) are machine-operating decisions
and live with the handbook, not here.
