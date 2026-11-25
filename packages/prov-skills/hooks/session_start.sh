#!/usr/bin/env bash
# prov-skills SessionStart hook (ADR 0021): inside a prov project (a prov.toml at the session's
# cwd or above), tell the agent so; anywhere else, print nothing.
dir="$PWD"
while [ ! -f "$dir/prov.toml" ]; do
  [ "$dir" = "/" ] && exit 0
  dir="${dir%/*}"
  [ -z "$dir" ] && dir="/"
done
echo "PROV PROJECT: prov.toml at $dir. Every run, artifact, dataset and doc here has a prov ID."
echo "- Resolve any ID or alias (run_..., ds_..., doc_..., model:name/3) with prov show / trace / uses"
echo "  before guessing; cite IDs, never paths. Skills: prov-skills:prov, prov-skills:journal, prov-skills:plot."
if [ -f "$dir/journal/NOW.md" ]; then
  echo "- Read $dir/journal/NOW.md before starting work."
fi
