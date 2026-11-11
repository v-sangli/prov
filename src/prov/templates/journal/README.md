# Journal

The running record of this project: experiments, investigations, findings, decisions and
milestones, written by people and agents.

- **[NOW.md](NOW.md)** is the big picture: goal, current understanding, open threads, milestones.
  Read it first.
- **[INDEX.md](INDEX.md)** lists every doc by date and status (`prov journal index` rebuilds it).
- **Docs** live in `<year>/<month>/<YYYY-MM-DD>-<topic>/README.md`, one per topic per day, with
  their figures beside them. Start one with `prov journal new <topic>`.

## Rules

1. **One doc per topic per day.** Work that spills into another day gets a new doc whose
   `continues:` names the earlier one. A doc is always a folder.
2. **Past docs are frozen**, with one exception: when a later doc overturns or qualifies a
   finding, set the old doc's `status: superseded` and `superseded_by:` (or add a
   `Re-check: <link>` line), so nobody trusts it by accident.
3. **Mark every claim** *verified* (measured, with the numbers) or *inferred*.
4. **Evidence is IDs, not paths.** `evidence:` lists the run, artifact, episode or alias IDs the
   findings rest on (`run_01J...`, `model:cube/0.4`, `bench:cube-holdout/2`). Recordings and
   checkpoints are never copied in. `prov journal lint` fails on IDs that don't resolve.
5. **Figures come from `prov run`.** A figure in a doc is made by a committed script in
   `analysis/` (plotting skill) and copied in with `prov.plot.to_journal`, named `<fig_id>.png`,
   with the ID in its caption. Throwaway plots stay out.
6. **Keep files small.** PNG for plots, JPEG for photos, about 500 KB each. Videos are embedded
   from `media/` (a link into the store, not committed): `![[media/<run_id>/<file>.mp4]]`.
7. **Plans and decisions get docs too.** A plan is a doc with a table of items marked
   proposed / agreed / running / done; results land in their own docs and update the table.
   Accepted architecture decisions go to `docs/adr/`.
8. **Update [NOW.md](NOW.md)** when a doc changes the big picture. One line per open thread,
   with a link to its latest doc.
9. **Known problems and workarounds** live in `OPEN_ISSUES.md` and `PATCHES.md` at the repo root
   (workarounds tagged `PATCH(<id>)` in code). Docs link to them instead of copying them.
