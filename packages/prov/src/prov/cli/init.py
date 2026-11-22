"""prov init.

    prov init <project>
        Make the current repo a prov project: write prov.toml. Never overwrites.
"""

from pathlib import Path

from prov.core.context import init_project


def cmd_init(args, get_ctx) -> int:
    made = init_project(Path.cwd(), args.project)
    print("\n".join(made) if made else "nothing to do: already set up")
    return 0


def register(sub, ext) -> None:
    init = sub.add_parser("init", help="make this repo a prov project")
    init.add_argument("project")
    init.set_defaults(func=cmd_init)
