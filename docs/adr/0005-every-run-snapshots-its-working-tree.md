# 0005. Uncommitted code is allowed; every run snapshots each repo's working tree under `refs/prov/<run_id>`

Status: Accepted (2026-11-09)
Covers: `packages/prov/src/prov/runs/snapshot.py`, `packages/prov/src/prov/runs/wrapper.py`, `packages/prov/src/prov/runs/rerun.py`, `packages/prov/src/prov/core/context.py` (`prov.toml` `repos`)
PR: https://github.com/v-sangli/prov/pull/2

## Context
In the last project the recorded commit was often "uncommitted": research code is edited
between runs and patched upstreams (e.g. GR00T) are edited in place. Forbidding dirty runs would
be ignored; recording only HEAD loses the code that ran. Formerly design decision D5.

## Decision
- Every run kind may run on a dirty tree. `prov run` snapshots each repo listed in the project's
  `prov.toml` `repos` (default `["."]`, paths relative to `prov.toml`; patched upstreams are
  listed there too) before starting the command.
- Snapshot (`runs/snapshot.py`), built without touching the branch, the index or any file:
  a temporary index gets `read-tree HEAD`, `add -A`, then `write-tree`; when the tree differs
  from HEAD's, `commit-tree -p HEAD` makes the snapshot commit, otherwise the snapshot is HEAD
  itself. The commit is stored at `refs/prov/<run_id>` and authored `prov <prov@localhost>`.
- Contents: modified, staged and new untracked files. Gitignored files are neither stored nor
  listed. Untracked files over 5 MB are left out and listed (`excluded`: path, bytes).
- A repo with no commits is refused. A subdirectory resolves to its repo's top level.
- When the repo has a remote named `origin`, the ref is pushed to it at run start. A failed or
  impossible push is not an error; it is recorded as `pushed: false` and logged.
- Each repo becomes a `code` entry in the run record: `repo`, `path`, `base` (HEAD), `snapshot`,
  `ref`, `dirty`, `pushed`, `excluded`. `git diff <base> <snapshot>` shows what was uncommitted.
- `prov rerun <run_id>` checks each snapshot out as a detached worktree under a temp root, laid
  out as the repos were relative to each other, remaps the cwd and command arguments that point
  into a recorded repo, and runs the same command as a new `prov run` of the same kind with
  `rerun_of=<run_id>` plus the original tags. Worktrees are removed after. Not restored:
  gitignored files, excluded untracked files, the Python environment.

## Consequences
- Easier: the exact code of any run, and its diff from the last commit, is always recoverable;
  local-only commits survive rebases and resets once pushed.
- Harder: `refs/prov/*` accumulate in every snapshotted repo and its remote.
- Harder: a run that reads gitignored files by path is not reproducible; it should load them by
  ID instead.
- Rules out refusing dirty runs.

## Enforced by
- `packages/prov/tests/test_gitsnap.py::test_clean_repo`
- `packages/prov/tests/test_gitsnap.py::test_dirty_repo_diff_is_exactly_the_changes`
- `packages/prov/tests/test_gitsnap.py::test_ref_reaches_remote`, `::test_no_remote_still_snapshots`
- `packages/prov/tests/test_gitsnap.py::test_big_untracked_file_is_listed_not_stored`
- `packages/prov/tests/test_gitsnap.py::test_snapshot_from_subdirectory`, `::test_repo_without_commits`
- `packages/prov/tests/test_run.py::test_dirty_run_records_snapshot`, `::test_multiple_repos`
- `packages/prov/tests/test_rerun.py::test_rerun_uses_snapshot_not_current_code`
- `packages/prov/tests/test_rerun.py::test_rerun_reproduces_file_byte_for_byte`
