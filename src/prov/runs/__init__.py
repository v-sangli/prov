"""Layer 2: runs, the processes that read and make artifacts. Imports core, storage.

schema    RunRecord, CodeState, ExcludedFile, Env
records   read / write run records in the registry
snapshot  the whole working tree as a commit under refs/prov/<run_id>
machine   host facts recorded per run (Python, platform, GPUs)
wrapper   the `prov run` lifecycle
rerun     re-run a recorded run on its exact code
tables    catalog tables: runs, run_code, run_inputs, run_outputs, run_tags, run_summary
"""
