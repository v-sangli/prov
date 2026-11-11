"""Layer 9: the `prov` command line. One module per command group, each with `register`.

main       argument parser root, -v / -q, error handling, the list of groups
common     shared argument helpers
run        prov run, prov rerun
artifacts  prov publish, show, alias
episodes   prov ingest, annotate
datasets   prov dataset freeze
query      prov catalog rebuild, q, trace, uses
journal    prov init, journal new | lint | index
site       prov site build | serve
"""

from prov.cli.main import main

__all__ = ["main"]
