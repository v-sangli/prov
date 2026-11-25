---
name: prov
description: Use when an ID like run_…, ds_…, ckpt_…, res_…, fig_…, doc_… or an alias like model:name/3 or ds:name@best appears, when asked what something was made from or what uses it, and before running, publishing or citing anything in a project that uses prov (a prov.toml in the repo or above). Covers prov show / trace / uses / q, prov run, prov.load / publish / refs, and citing by ID.
---

# prov: the reference for every ID

prov records every run, artifact, dataset and doc on this machine in one registry. Any ID or
alias resolves to what it is, what it was made from, and what was built on it. Look it up
before guessing; cite it instead of a path.

## Reading an ID or alias

IDs are `<prefix>_<ULID>`: `run_` run, `ses_` session, `ep_` episode, `ds_` dataset version,
`ckpt_` checkpoint, `bench_` benchmark, `res_` result, `fig_` figure, `vid_` video, `raw_` raw
recording, `calib_` calibration, `doc_` doc. Aliases: `<kind>:<name>/<version>` (fixed) and
`<kind>:<name>@<label>` (moves). Every command below takes either.

| Question | Command |
| --- | --- |
| What is it? | `prov show <ref>` |
| What was it made from? (inputs, sessions, code commits) | `prov trace <ref>` |
| What runs, datasets, artifacts and docs use it? | `prov uses <ref>` |
| Which versions does an alias have? | `prov alias show <ref>` |
| Anything else (find the latest eval, list runs by tag) | `prov q "<SQL>"` over the catalog tables (`prov q "SHOW TABLES"`) |

An ID found in another tool (a W&B run's config `prov_run`, a checkpoint's metadata) is
resolved the same way.

## Recording

1. Run work that makes or reads artifacts through `prov run --kind <collect|export|train|eval|analysis|other> -- <command>`,
   inside the project. It snapshots the code and records the run's inputs and outputs.
2. In the script, load inputs by reference and publish outputs:
   `rec = prov.load("ds:<name>/<v>")`, `prov.path(rec)` for the bytes,
   `prov.publish(path, kind, alias="<kind>:<name>/<v>")`. Pass alias versions in as arguments,
   never hard-coded: `prov rerun` publishes again.
3. Other tools get the run's IDs, not the other way round: `wandb.init(config={**cfg, **prov.refs()})`.
   prov calls no other tool.
4. Move a label only on the user's word (a release): `prov alias label <kind:name@label> <kind:name/version>`.

## Citing

- A finding, doc, figure caption or PR description cites IDs or aliases, never store paths or
  local file names.
- Docs: journal docs follow the `journal` skill; `prov-journal register` at the end of the
  session. Any other Markdown doc in a git repo: `prov doc register <path>`. A loose note in no
  repo is folded into a journal doc first.
- Figures: the `plot` skill.

## Don'ts

- Don't write into the registry or the store by hand; only `prov` commands change them.
- Don't invent an ID or alias: a cited one that is not in the registry fails registration.
