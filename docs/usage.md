# Using `prov`

How to record, find and reuse everything a robot-learning project makes: recording sessions,
episodes, datasets, checkpoints, results, figures, and the runs that made them. Setup is in the
[README](../README.md); the design decisions are in [docs/adr/](adr/).

- [Concepts](#concepts)
- [Workflow, start to finish](#workflow-start-to-finish)
- [IDs and aliases](#ids-and-aliases)
- [Commands](#commands)
- [Python API](#python-api)
- [Querying the catalog](#querying-the-catalog)
- [The journal](#the-journal)
- [Sites](#sites)
- [Troubleshooting](#troubleshooting)

## Concepts

| Thing | What it is | Where it lives |
| --- | --- | --- |
| **Store** | the bytes: sessions, checkpoints, figures, ... One folder per artifact, read-only once published. | `store_root` (`~/store`) |
| **Registry** | a git repo of small text records describing every run and artifact, plus episodes, annotations, dataset members and aliases. The source of truth; push it to a private remote. Every change is a commit. | `registry` (`~/registry`) |
| **Catalog** | a DuckDB index built from the registry, for `prov q` and lineage. Rebuilt automatically when the registry has moved; deleting it loses nothing. | `catalog` (`~/.cache/prov/catalog.duckdb`) |
| **Run** | one execution of a command under `prov run`: code snapshot, machine, inputs, outputs, summary numbers, status. | `registry/records/runs/` |
| **Artifact** | a published file or folder with an ID: `ses_`, `ckpt_`, `res_`, `fig_`, ... A dataset version is an artifact with no bytes. | record in the registry, bytes in the store |
| **Episode** | one episode of a session, with its own `ep_` ID, length, tasks and source. Labelled with annotations. | `registry/records/episodes/<ses_id>.jsonl` |
| **Dataset version** | a frozen list of episode IDs, named `ds:<name>/<n>`. Nothing is copied. | `registry/datasets/<ds_id>.txt` |
| **Project** | a repo with a `prov.toml`: its name and the repos to snapshot on each run. | the project repo |
| **Journal** | dated Markdown docs in the project repo, citing IDs as evidence. | `<project>/journal/` |

## Workflow, start to finish

The steps below go from a recording to a figure in the journal. Each command prints the IDs it
made; `<...>` marks values to fill in.

**1. Make the repo a project** (once):

```bash
cd ~/code/cube-grasp
prov init cube-grasp
```

This writes `prov.toml`, a `journal/` skeleton and links the journal and plotting skills into
`.claude/skills/`. It never overwrites anything. If the project's code spans several repos, list
them in `prov.toml` so every run snapshots all of them:

```toml
project = "cube-grasp"
repos = [".", "../Isaac-GR00T"]      # relative to prov.toml
```

**2. Ingest a recording session.** A LeRobot v2.x or v3.0 folder becomes a `ses_` artifact (moved
into the store) and one `ep_` ID per episode:

```bash
prov ingest lerobot ~/recordings/2026-11-09-cube --meta operator=vs --calib calib_<ULID>
# ses_01JC...    40 episodes
```

`--copy` copies instead of moving. Ingesting the same folder (or the session already in the store)
again returns the existing IDs. Recordings exported from MCAP pass `--source-map map.jsonl` so each
episode records its MCAP file and time range (format under [Episodes](#episodes)).

**3. Label episodes**:

```bash
prov annotate ep_<ULID> outcome=failure failure_type=slip
```

Labels are an append-only log; the latest value per key wins.

**4. Freeze a dataset version** from a catalog query (or a file of episode IDs):

```bash
prov dataset freeze cube-pick --holdout 0.1 --by session --notes "first 3 days" --query "
  SELECT e.id FROM episodes e
  JOIN artifacts s ON s.id = e.session
  WHERE s.meta->>'robot_type' = 'so101'
    AND e.id NOT IN (SELECT episode FROM annotations WHERE key = 'outcome' AND value = 'failure')"
# ds:cube-pick/1          ds_...  36 episodes  3 sessions
# ds:cube-pick-train/1    ds_...  32 episodes  2 sessions
# ds:cube-pick-holdout/1  ds_...   4 episodes  1 sessions
```

Versions number themselves (1, 2, ...). `--parent ds:cube-pick/1` records what a version derives from.

**5. Train inside `prov run`.** Any command works; `prov run` snapshots the code, records the run
and folds in whatever the script tells `prov`:

```bash
prov run --kind train --tag lr=1e-4 -- python train.py --dataset ds:cube-pick-train/1
```

```python
# train.py
import prov
from lerobot.datasets.lerobot_dataset import MultiLeRobotDataset

ds = prov.load(args.dataset)                    # resolves the alias; recorded as an input
sessions = prov.dataset_sessions(ds.id)         # {ses_id: [episode_index, ...]}
data = MultiLeRobotDataset(repo_ids=list(sessions), root=prov.context().store_root / "sessions",
                           episodes=sessions)
run = prov.wandb_init()                         # optional; W&B project = prov project
...
prov.publish(ckpt_dir, "checkpoint", meta={"step": step}, alias="model:cube-pick/1")   # an output
prov.summary(final_loss=loss)
```

The run ID is printed (`prov: run_...`) when the run starts. If the command fails, the run is
still recorded, with status `failed` (or `killed` on a signal) and its exit code.

Alias versions never change, so a script that hard-codes `alias="model:cube-pick/1"` fails the
second time it publishes, including under `prov rerun`. Pass the alias (or its version) as an
argument when a script will be run more than once.

**6. Evaluate** the same way, loading the checkpoint by alias and publishing results:

```bash
prov alias label model:cube-pick@best model:cube-pick/1
prov run --kind eval -- python eval.py --model model:cube-pick@best
```

```python
ckpt = prov.load("model:cube-pick@best")
policy = load_policy(prov.path(ckpt))           # the checkpoint folder, with manifest.yaml
...
prov.publish("results.parquet", "result", alias="res:cube-pick-eval/1")
prov.summary(success_rate=0.62, n_episodes=50)
```

Robot rollouts recorded during an eval are ingested like any session (step 2), so they get episode
IDs, labels and lineage too.

**7. Plot into the journal**:

```bash
prov journal new hand-closure            # journal/2026/11/2026-11-12-hand-closure/README.md
prov run --kind analysis -- python plot_closure.py
```

```python
import matplotlib.pyplot as plt
import prov
from prov import plot

res = prov.load("res:cube-pick-eval/1")
with plot.style():
    fig, ax = plt.subplots()
    ...
rec = plot.save_figure(fig, "closure", caption="Hand closure per checkpoint")
plot.to_journal(rec, "journal/2026/11/2026-11-12-hand-closure")    # copies fig_<ULID>.png
```

Write the doc, cite the figure and results in `evidence:`, then check it:

```bash
prov journal lint && prov journal index
```

**8. Trace it back**:

```bash
prov trace fig_<ULID>        # figure <- analysis run <- results <- eval run <- checkpoint <- ... <- sessions
prov uses ses_<ULID>         # every dataset, run and artifact built on a session
prov rerun run_<ULID>        # same command on the exact recorded code
```

## IDs and aliases

**IDs** are `<prefix>_<ULID>` (26 characters, time-ordered), made by `prov` and never reused:

| Prefix | Kind | Prefix | Kind |
| --- | --- | --- | --- |
| `run_` | run | `res_` | result |
| `ses_` | session | `fig_` | figure |
| `ep_` | episode | `vid_` | video |
| `ds_` | dataset version | `raw_` | raw recording (MCAP) |
| `ckpt_` | checkpoint | `calib_` | calibration |
| `bench_` | benchmark | | |

**Aliases** are readable names for artifact IDs:

| Form | Meaning |
| --- | --- |
| `<kind>:<name>/<version>` | a numbered version. Set once, never changes. |
| `<kind>:<name>@<label>` | a moving label pointing at a version (`best`, `current`). Every move is a registry commit. |

Alias kinds: `ds` (dataset), `model` (checkpoint), `bench` (benchmark), `calib` (calibration),
`ses` (session), `res` (result), `fig` (figure). Names start with a letter or digit and use
`A-Z a-z 0-9 . _ -`; versions start with a digit (`3`, `0.5`).

Every command and function that takes a reference (`show`, `trace`, `uses`, `alias show`,
`prov.load`, `--parent`, journal `evidence:`) accepts an ID, a version or a label.

## Commands

`prov --help` and `prov <command> --help` give the full option lists. Global flags go before the
command: `prov -v <command>` logs debug detail, `prov -q <command>` only warnings and errors.

### Runs

```
prov run [--kind K] [--tag KEY=VALUE ...] [--notes TEXT] -- <command ...>
prov rerun <run_id>
```

- `--kind`: `collect`, `export`, `train`, `eval`, `analysis` or `other` (default).
- **Must run inside a project** (a `prov.toml` in the working directory or a parent).
- **Code snapshot.** Each repo in `repos` is snapshotted as a commit under `refs/prov/<run_id>`,
  covering modified, staged and new untracked files. The branch, index and working tree are left
  untouched. The ref is pushed when the repo has an `origin`. Untracked files over 5 MB are left
  out and listed in the record; gitignored files are never included.
- **Exit code.** `prov run` exits with the command's code (128+N when killed by signal N).
- **Status.** The run record goes from `running` to `ok`, `failed` or `killed`.
- `rerun` checks each repo out at its snapshot as a temporary git worktree, then runs the same
  command as a new run tagged `rerun_of=<run_id>`. Not restored: gitignored files (such as a
  `.venv` inside the repo), large untracked files, and the Python environment. Use an interpreter
  that lives outside the repos. A rerun publishes new artifacts, so a hard-coded alias version in
  the script makes it fail (see step 5).

### Artifacts and aliases

```
prov publish <path> --kind K [--meta KEY=VALUE ...] [--copy] [--alias kind:name/version]
prov show <ID or alias>
prov alias set <kind:name/version> <ID>
prov alias label <kind:name@label> <kind:name/version>
prov alias show <ID or alias>
```

- **`publish` kinds:** `raw`, `session`, `dataset`, `checkpoint`, `benchmark`, `calibration`,
  `result`, `figure`, `video`.
- **What `publish` does:** moves the path into `<store>/<kind dir>/<id>/`, removes write
  permission, commits the record and prints the new ID. `--alias` is checked before anything moves.
- **Inside `prov run`,** a publish becomes that run's output.
- **Checkpoint folders** also get a `manifest.yaml` (a copy of the record).
- `show` prints the record and, for an artifact with bytes, `# path: <store path>`.

### Episodes

```
prov ingest lerobot <dir> [--source-map FILE] [--calib CALIB_ID ...] [--meta KEY=VALUE ...] [--copy]
prov annotate <ep_id> KEY=VALUE [KEY=VALUE ...]
```

Session `meta` is read from `meta/info.json`: `fps`, `robot_type`, `cameras`, `codebase_version`,
`total_episodes`, `total_frames`, plus any `--meta`. A source map is JSONL with one line per
episode, as written by the MCAP export:

```json
{"episode_index": 0, "path": "/data/raw/2026-11-09/take_01.mcap", "raw": "raw_...", "start_s": 0.0, "end_s": 18.4}
```

Every episode must have a line. Without a map, episodes are recorded as `teleop`.

### Datasets

```
prov dataset freeze <name> (--query SQL | --episodes FILE) [--parent REF] [--notes TEXT]
                           [--holdout FRACTION [--seed N] [--by episode|session]]
```

- **Selection.** `--query` takes catalog SQL whose first column is episode IDs; `--episodes` takes
  a file of IDs. Every ID must be a registered episode, and duplicates are dropped.
- **Versions** number from 1 per name.
- **`--holdout`** also writes `ds:<name>-train/<n>` and `ds:<name>-holdout/<n>`, with the same
  number as `ds:<name>/<n>`.
- **Split methods.**
  - `--by episode` holds out `round(fraction × n)` episodes, at least one.
  - `--by session` holds out whole sessions until at least `fraction × n` episodes are held, so no
    session appears on both sides.
- **Seeds.** The same seed always gives the same split.

### Catalog and lineage

```
prov q "<SQL>"                 tab-separated, with a header row
prov trace <ID or alias>       upstream: what it was made from, down to sessions and code commits
prov uses <ID or alias>        downstream: every run, dataset and artifact built on it
prov catalog rebuild           force a rebuild (normally automatic)
```

Lineage edges:
- artifact ← the run that produced it;
- run ← its inputs;
- dataset ← its parent and the sessions of its episodes.

A node reached twice is shown as `(see above)`.

### Project and journal

```
prov init <project>
prov journal new <topic> [--continues <doc folder, relative to journal/>]
prov journal lint              exits 1 when there are problems
prov journal index             rewrites journal/INDEX.md
prov site build [<folder>] [--name NAME]
prov site serve [--host 127.0.0.1|tailscale|ADDR] [--port 8090] [--rebuild-every 300]
```

See [The journal](#the-journal) and [Sites](#sites).

## Python API

`import prov` inside a script. Every function reads the machine config itself; inside `prov run`
it also records into that run. Outside `prov run` the functions still work (for notebooks), but
nothing is recorded as an input or output.

| Call | Returns | Inside `prov run` |
| --- | --- | --- |
| `prov.load(ref)` | the `ArtifactRecord` for an ID or alias (`.id`, `.kind`, `.uri`, `.meta`, `.produced_by`) | recorded as an input |
| `prov.path(record)` | the `Path` of its bytes in the store (error for a dataset, which has none) | — |
| `prov.publish(path, kind, meta=None, copy=False, alias=None)` | the new `ArtifactRecord`; same rules as `prov publish` | recorded as an output, `produced_by` = run |
| `prov.members(ref)` | a dataset version's episode IDs, sorted | — |
| `prov.dataset_sessions(ref)` | `{ses_id: [episode_index, ...]}` for `MultiLeRobotDataset` | — |
| `prov.summary(**values)` | `None`; numbers or strings, later values win | stored on the run record; logs a warning outside a run |
| `prov.wandb_init(**kwargs)` | the `wandb` run; `project` defaults to the prov project, `config["prov"]` holds the run ID | W&B run path stored on the record |
| `prov.context()` | the `Context` (paths from the machine config, the current run) for calling library modules directly | — |

**Plotting**, `from prov import plot`:

| Call | Does |
| --- | --- |
| `plot.style()` | context manager applying the house style (palette, fonts, recessive axes) |
| `plot.save_figure(fig, name, caption=None, alias=None, meta=None)` | writes `name.png` and `name.pdf` (deterministic bytes) and publishes them as one `fig_` artifact |
| `plot.to_journal(record, doc_dir)` | copies the PNG into a journal doc folder as `<fig_id>.png`; returns the copy's path |
| `plot.CATEGORICAL`, `plot.SEQUENTIAL_BLUE`, `plot.STATUS` | the palette. Assign series in `CATEGORICAL` order, never cycled; use one y-axis per chart and a legend for two or more series. |

**W&B.** After `prov.wandb_init()`, each `prov.load` and `prov.publish` also logs a W&B artifact
reference, so W&B draws lineage. Nothing is uploaded: the artifact references the registry record
by path. Loads made before `wandb_init` are logged when it starts. W&B errors are logged as
warnings and never fail the run. `use_artifact` does not work in W&B offline mode.

## Querying the catalog

The catalog has these tables. Timestamps are naive UTC; `meta` is JSON (`meta->>'key'` reads a field).

| Table | Columns |
| --- | --- |
| `runs` | `id, kind, project, started, finished, status, exit_code, host, cwd, command[], wandb, notes` |
| `run_code` | `run, repo, path, base, snapshot, ref, dirty, pushed` |
| `run_inputs`, `run_outputs` | `run, artifact` |
| `run_tags` | `run, key, value` |
| `run_summary` | `run, key, value` (DOUBLE, NULL if not numeric), `text` |
| `artifacts` | `id, kind, uri, path, created, source, produced_by, meta` |
| `aliases` | `ref, kind, name, version, id` |
| `alias_labels` | `ref, kind, name, label, version` |
| `episodes` | `id, session, episode_index, length, fps, duration_s, tasks[], source_kind, source_raw, source_path, start_s, end_s, calibrations[]` |
| `annotation_log` | `episode, key, value, time` (every label ever set) |
| `annotations` (view) | `episode, key, value, time` (latest value per episode and key) |
| `dataset_members` | `dataset, alias, episode` |

Examples:

```sql
-- failed episodes and why
SELECT a.episode, f.value AS failure_type
FROM annotations a LEFT JOIN annotations f ON f.episode = a.episode AND f.key = 'failure_type'
WHERE a.key = 'outcome' AND a.value = 'failure';

-- success rate of every eval run, newest first
SELECT r.id, r.started, s.value AS success_rate
FROM runs r JOIN run_summary s ON s.run = r.id AND s.key = 'success_rate'
WHERE r.kind = 'eval' ORDER BY r.started DESC;

-- which runs trained on a dataset version
SELECT i.run FROM run_inputs i JOIN aliases a ON a.id = i.artifact WHERE a.ref = 'ds:cube-pick-train/1';

-- episodes per session with total minutes
SELECT session, count(*) AS episodes, round(sum(duration_s) / 60, 1) AS minutes
FROM episodes GROUP BY session ORDER BY session;
```

## The journal

Each doc is `journal/<YYYY>/<MM>/<YYYY-MM-DD>-<topic>/README.md`, one per topic per day, with its
images in the same folder. `prov journal new <topic>` creates it from the template:

```markdown
---
date: 2026-11-12
status: open                 # open | concluded | superseded
continues: null              # path to the doc this one continues (set by --continues)
evidence: []                 # IDs or aliases this doc's claims rest on
---
# Hand closure

## Question
## Method
## Findings
- **verified:**
- **inferred:**
## Next
```

The journal's own rules live in `journal/README.md`, written by `prov init`. `journal/NOW.md` holds
the open threads, one table row each.

`prov journal lint` checks:

| Check | Rule |
| --- | --- |
| `frontmatter` | frontmatter parses; `date` matches the folder; `status` is open, concluded or superseded |
| `links` | `continues` and `superseded_by` point at docs that exist; a superseded doc names its successor |
| `evidence` | `evidence:` is a list of IDs or aliases (not paths) that exist in the registry |
| `body_ids` | every ID written in the body exists in the registry |
| `images` | every local `![...](file)` exists next to the doc |
| `now` | each row of NOW.md's `## Open threads` table is at most 300 characters |

`prov journal index` rewrites `journal/INDEX.md` (date, title, status, evidence count; newest
first). Don't edit it by hand.

## Sites

`prov site build` turns the project journal (or any Markdown folder, such as `~/handbook`) into a
static site with Quartz, under `<sites_dir>/<name>/`. `prov site serve` serves every built site:

- `/` lists the sites;
- each site is at `/<name>/`;
- `/<name>/media/` serves the store's `media/` folder read-only, with seeking for video;
- sites whose source changed are rebuilt every `--rebuild-every` seconds.

`--host tailscale` binds to this machine's Tailscale address. Quartz and Node setup is in the README.

## Troubleshooting

Errors print as `prov: <message>` and exit with code 2. Add `-v` to see debug logging.

| Message | Cause |
| --- | --- |
| `no machine config at ...` | create `~/.config/prov/config.toml` (README), or set `PROV_CONFIG` |
| `no prov.toml in ... or its parents` | `prov run`, `prov journal` and `prov site build` without a folder need a project; `cd` into it or `prov init` |
| `not an alias: ...` | the reference isn't `kind:name/version` or `kind:name@label`, or the kind isn't one of the alias kinds |
| `... already exists; versions never change` | pick the next version number, or move a label instead |
| `... is already inside the store` | it's published already; `prov load` / `prov show` it |
| `not registered episodes: [...]` | the query or file names IDs that aren't episodes; check the query's first column |
| `warning: only N GB free on the store disk` | under 50 GB free; publishing continues, but clean up |
| ``summary outside `prov run`; not recorded`` | `prov.summary` was called from a plain script or notebook |
| `W&B use_artifact failed ...` | W&B is offline or unreachable; the run continues and the registry still has the record |

Store files are read-only on purpose. To change an artifact, publish a new one. The catalog can
always be deleted and rebuilt (`prov catalog rebuild`). The registry is the record: if a command
fails halfway, `git -C ~/registry status` shows what was written.
