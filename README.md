# research-infra

Provenance for robot-learning research, as three packages in one uv workspace. Design decisions:
[docs/adr/](docs/adr/).

| Package | Import | CLI | What it is |
| --- | --- | --- | --- |
| `packages/prov` | `prov` | `prov` | the core: IDs, provenance records, a local store, datasets of episodes, docs, lineage |
| `packages/prov-journal` | `prov_journal` | `prov-journal` | the project journal: docs, lint, index, Quartz sites |
| `packages/prov-skills` | `prov_skills` | — | agent skills (`prov`, `prov-journal`, `prov-plot`) and the plot module |

prov imports neither tool; both depend on prov (ADR 0018, `test_layers.py` enforces it).

**Using it: [docs/usage.md](docs/usage.md)**: concepts, a start-to-finish workflow, every command,
the Python API, catalog tables with example queries, the journal, and troubleshooting.

## Install on a machine (once, for every workspace)

One clone per machine, checked out at a release tag, with its own venv; every workspace uses it.
agent-md's `.claude-workflow/install_prov.sh <tag>` does all of this (agent-md ADR 0011):

```bash
H=~/.local/share/prov
git clone https://github.com/v-sangli/prov "$H" && git -C "$H" checkout --detach <tag>
uv venv "$H/.venv" --python 3.12
uv pip install --python "$H/.venv/bin/python" "$H/packages/prov" "$H/packages/prov-journal"
ln -s "$H/.venv/bin/prov" "$H/.venv/bin/prov-journal" ~/.local/bin/
for d in "$H"/packages/prov-skills/skills/*/; do ln -s "${d%/}" ~/.claude/skills/; done
```

The skills (`prov`, `prov-journal`, `prov-plot`) are plain directories at
`packages/prov-skills/skills/<name>/` (ADR 0022). A project whose code imports `prov` (for
`prov.refs()`, `load`, `publish`) or `prov_skills.plot` installs them into its own environment
from the same clone: `uv pip install "$H/packages/prov"` (add `"$H/packages/prov-skills[plot]"`
for figures).

## Development setup

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e packages/prov -e packages/prov-journal -e "packages/prov-skills[plot]" pytest
.venv/bin/python -m pytest -q
uvx ruff@0.8.4 check packages conftest.py
```

Machine config, `~/.config/prov/config.toml`:

```toml
registry = "~/registry"        # git repo of records (push it to a private remote)
store_root = "~/store"         # artifact bytes
# catalog = "~/.cache/prov/catalog.duckdb"
# sites_dir = "~/.cache/prov/sites"
quartz = "<path>/quartz"       # only for `prov-journal site`
node = "<path>/node/bin"
```

The registry is a git repo: `git init -b main ~/registry`, then `echo .prov.lock > ~/registry/.gitignore`
(the write lock, ADR 0016) in its first commit, and a private remote.

## Sites (`prov-journal site`)

Quartz **v4.5.2** with Node **22.14** (Quartz needs npm >= 10.9.2; Node 22.11 ships 10.9.0):

```bash
curl -fsSL https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz | tar -xJ --strip-components=1 -C node
git clone --depth 1 --branch v4.5.2 https://github.com/jackyzha0/quartz.git quartz
(cd quartz && PATH=../node/bin:$PATH npm ci --no-audit --no-fund)
```

`prov-journal site build` writes `packages/prov-journal/src/prov_journal/site/quartz.config.ts`
into the checkout before building (no analytics, local fonts, `media/` ignored). Serve with
`prov-journal site serve --host tailscale`.

## A project

```bash
cd <project repo>
prov init <project-name>      # prov.toml
prov-journal init             # journal/, journal/media link, .gitignore lines
prov run --kind train -- python train.py
prov-journal new <topic>; prov-journal lint; prov-journal index; prov-journal register
prov-journal site build && prov-journal site serve
```

`prov --help` and `prov <command> --help` list everything (likewise `prov-journal`); `prov -v ...` and `prov-journal -v ...` log debug detail, `-q` only warnings.

## Package map

### prov

Layers, lowest first. A package imports only from its own layer's lower rungs
(`packages/prov/tests/test_layers.py` enforces it); each `__init__.py` says what the package owns.

| Layer | Package | Owns |
| --- | --- | --- |
| 0 | `prov.core` | errors, IDs, registry/store layout, record base, run env contract, Context, `prov.toml`, extension types, logging |
| 1 | `prov.storage` | registry git writes, store bytes, DuckDB catalog engine |
| 2 | `prov.runs` | run records, code snapshots, `prov run` lifecycle, rerun, run tables |
| 2 | `prov.artifacts` | artifact records, publish / load, aliases, artifact tables |
| 3 | `prov.episodes` | episode records, ingest formats (`formats/lerobot`), ingest, annotate, episode tables |
| 3 | `prov.docs` | doc records (`doc_` IDs, versions, cites), `prov doc register`, doc tables |
| 4 | `prov.datasets` | freeze, split, members, dataset table |
| 5 | `prov.lineage` | trace / uses, walking the catalog's `nodes` and `edges` views |
| 7 | `prov.wiring` | the built-in extensions: catalog tables, ingest formats |
| 8 | `prov.api` | the public Python API (`import prov`) |
| 9 | `prov.cli` | the command line, one module per command group |

Library functions take a `Context` (`prov.context()`) first; the public API and the CLI build it.

### prov-journal

| Module | Owns |
| --- | --- |
| `prov_journal.project` | `prov-journal init`: journal skeleton, media link, `.gitignore` lines |
| `prov_journal.docs` | journal location, new doc, reading docs and frontmatter, INDEX.md |
| `prov_journal.lint` | `prov-journal lint`: `LintCheck`, `CHECKS`, one rule per module |
| `prov_journal.templates` | journal README / NOW / doc templates |
| `prov_journal.site` | Quartz site build and the server that adds store media |
| `prov_journal.cli` | the `prov-journal` command line (`register` registers every dated doc via `prov.docs`) |

### prov-skills

`prov_skills.plot`: the house style, `save_figure`, `to_journal` (`from prov_skills import plot`).
The skills are `packages/prov-skills/skills/<name>/SKILL.md` for `prov`, `prov-journal` and
`prov-plot`, each `name` equal to its directory; installers link the directories (ADR 0022).

Extending: a new recording format is a module in `prov/episodes/formats/` exposing an
`IngestFormat`, and new catalog tables are a `CatalogTables`; each is then one line in
`prov/wiring.py`. A CLI group is a module in `prov/cli/` with `register`, listed in
`cli/main.py`. A lint rule is a module in `prov_journal/lint/` exposing a `LintCheck`, listed in
`CHECKS`. A skill is a directory under `packages/prov-skills/skills/` with a SKILL.md. Other tools integrate by
reference: they carry prov IDs (`prov.refs()`) in their own configs; prov imports none of them
(ADR 0017).

## Variation axes

The dimensions along which each package expects more than one variant:

- prov: recording formats (`IngestFormat`, one today: LeRobot), catalog tables
  (`CatalogTables`, each also contributing lineage `nodes` and `edges` SQL), both in
  `prov.core.extensions` and registered in `wiring.py`; CLI command groups (`prov/cli/`)
- prov-journal: journal lint rules (`LintCheck`, listed in `prov_journal.lint.CHECKS`)
- prov-skills: skills (one directory each; adding one touches nothing else)

## Repo

CI (`.github/workflows/ci.yml`) installs the three packages and runs ruff and the test suite on
every PR and push to `main`; the Quartz site test skips there, as it needs `tools/quartz` beside
the repo. Deviations are registered in `DEVIATIONS.md`.
