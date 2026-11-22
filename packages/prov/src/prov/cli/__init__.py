"""Layer 9: the `prov` command line. One module per command group, each with `register`.

main       argument parser root, -v / -q, error handling, the list of groups
common     shared argument helpers
init       prov init
run        prov run, prov rerun
artifacts  prov publish, show, alias
episodes   prov ingest, annotate
datasets   prov dataset freeze
query      prov catalog rebuild, q, trace, uses
"""

from prov.cli.main import main

__all__ = ["main"]
