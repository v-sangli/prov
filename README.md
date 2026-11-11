# research-infra

`prov`: IDs, provenance records, a local store, datasets of episodes, and the project journal for
robot-learning research. Design: `docs/design.md` in the planning workspace.

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

The registry is a git repo: `git init -b main ~/registry`, first commit, private remote.

## Sites (`prov site`)

Quartz **v4.5.2** with Node **22.14** (Quartz needs npm >= 10.9.2; Node 22.11 ships 10.9.0):

```bash
curl -fsSL https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz | tar -xJ --strip-components=1 -C node
git clone --depth 1 --branch v4.5.2 https://github.com/jackyzha0/quartz.git quartz
(cd quartz && PATH=../node/bin:$PATH npm ci --no-audit --no-fund)
```

`prov site build` writes `src/prov/templates/quartz.config.ts` into the checkout before building
(no analytics, local fonts, `media/` ignored). Serve with `prov site serve --host tailscale`.

## A project

```bash
cd <project repo>
prov init <project-name>      # prov.toml, journal/, skills
prov run --kind train -- python train.py
prov journal new <topic>; prov journal lint; prov journal index
prov site build && prov site serve
```

`prov --help` and `prov <command> --help` list everything.
