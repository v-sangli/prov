# research-infra

`prov`: IDs, provenance records, a local store, datasets of episodes, and the project journal for
robot-learning research. Design decisions: [docs/adr/](docs/adr/).

**Using it: [docs/usage.md](docs/usage.md)**: concepts, a start-to-finish workflow, every command,
the Python API, catalog tables with example queries, the journal, and troubleshooting.

## Setup (once per machine)

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e ".[test,wandb,plot]"
.venv/bin/python -m pytest -q
```

Machine config, `~/.config/prov/config.toml`:

```toml
registry = "~/registry"        # git repo of records (push it to a private remote)
store_root = "~/store"         # artifact bytes
# catalog = "~/.cache/prov/catalog.duckdb"
# sites_dir = "~/.cache/prov/sites"
quartz = "<path>/quartz"       # only for `prov site`
node = "<path>/node/bin"
```

The registry is a git repo: `git init -b main ~/registry`, then `echo .prov.lock > ~/registry/.gitignore`
(the write lock, ADR 0016) in its first commit, and a private remote.

## Sites (`prov site`)

Quartz **v4.5.2** with Node **22.14** (Quartz needs npm >= 10.9.2; Node 22.11 ships 10.9.0):

```bash
curl -fsSL https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz | tar -xJ --strip-components=1 -C node
git clone --depth 1 --branch v4.5.2 https://github.com/jackyzha0/quartz.git quartz
(cd quartz && PATH=../node/bin:$PATH npm ci --no-audit --no-fund)
```

`prov site build` writes `src/prov/integrations/site/quartz.config.ts` into the checkout before building
(no analytics, local fonts, `media/` ignored). Serve with `prov site serve --host tailscale`.

## A project

```bash
cd <project repo>
prov init <project-name>      # prov.toml, journal/, skills
prov run --kind train -- python train.py
prov journal new <topic>; prov journal lint; prov journal index
prov site build && prov site serve
```

`prov --help` and `prov <command> --help` list everything; `prov -v ...` logs debug detail,
`prov -q ...` only warnings.

## Package map

Layers, lowest first. A package imports only from its own layer's lower rungs (`tests/test_layers.py`
enforces it); each `__init__.py` says what the package owns.

| Layer | Package | Owns |
| --- | --- | --- |
| 0 | `prov.core` | errors, IDs, registry/store layout, record base, run env contract, Context, extension types, events, logging |
| 1 | `prov.storage` | registry git writes, store bytes, DuckDB catalog engine |
| 2 | `prov.runs` | run records, code snapshots, `prov run` lifecycle, rerun, run tables |
| 2 | `prov.artifacts` | artifact records, publish / load, aliases, artifact tables |
| 3 | `prov.episodes` | episode records, ingest formats (`formats/lerobot`), ingest, annotate, episode tables |
| 4 | `prov.datasets` | freeze, split, members, dataset table |
| 5 | `prov.lineage` | trace / uses |
| 6 | `prov.journal` | `prov init`, docs, index, lint checks (`lint/`, one rule per module), templates, skills |
| 6 | `prov.integrations` | W&B event subscriber, plot house style, Quartz site build / serve |
| 7 | `prov.wiring` | the built-in extensions: catalog tables, ingest formats, lint checks, subscribers |
| 8 | `prov.api`, `prov.plot` | the public Python API (`import prov`, `from prov import plot`) |
| 9 | `prov.cli` | the command line, one module per command group |

Library functions take a `Context` (`prov.context()`) first; the public API and the CLI build it.

Extending: a new recording format is a module in `episodes/formats/` exposing an `IngestFormat`; a
lint rule is a module in `journal/lint/` exposing a `LintCheck`; new catalog tables are a
`CatalogTables`; a new integration subscribes to `artifact.published`, `artifact.loaded` or
`run.summary`. Each is then one line in `wiring.py`. A CLI group is a module in `cli/` with
`register`, listed in `cli/main.py`.

## Variation axes

The dimensions along which `prov` expects more than one variant. Each has a fixed interface
in `prov.core.extensions` and is registered in `wiring.py`:

- recording formats (`IngestFormat`); one today: LeRobot
- catalog tables (`CatalogTables`)
- journal lint rules (`LintCheck`)
- event subscribers (`artifact.published`, `artifact.loaded`, `run.summary`); one today: W&B
- CLI command groups (`cli/`)

## Repo

CI (`.github/workflows/ci.yml`) runs ruff and the test suite on every PR and push to `main`;
the Quartz site test skips there, as it needs `tools/quartz` beside the repo. Deviations are
registered in `DEVIATIONS.md`.
