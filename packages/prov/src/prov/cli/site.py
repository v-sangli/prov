"""prov site build | serve.

    prov site build [<vault dir>] [--name N]
        Build a Markdown vault (default: this project's journal) into a static site with Quartz.
    prov site serve [--host 127.0.0.1|<addr>|tailscale] [--port 8090] [--rebuild-every 300]
        Serve every built site, with /<site>/media/ answered read-only from the store.
"""

from pathlib import Path

from prov.core.context import load_project
from prov.integrations.site import build, server


def cmd_site(args, get_ctx) -> int:
    ctx = get_ctx()
    if args.action == "serve":
        server.serve(ctx, args.host, args.port, args.rebuild_every)
        return 0
    if args.source:
        source, name = Path(args.source), args.name or Path(args.source).resolve().name
    else:
        project = load_project(Path.cwd())
        source, name = project.root / "journal", args.name or project.project
    print(build.build(ctx, source, name))
    return 0


def register(sub, ext) -> None:
    st = sub.add_parser("site", help="build and serve journal / handbook sites")
    st.add_argument("action", choices=["build", "serve"])
    st.add_argument("source", nargs="?", help="vault folder to build (default: this project's journal)")
    st.add_argument("--name", help="site name (default: project name or folder name)")
    st.add_argument("--host", default="127.0.0.1", help="address to bind, or `tailscale`")
    st.add_argument("--port", type=int, default=8090)
    st.add_argument("--rebuild-every", type=int, default=300, help="seconds; 0 disables")
    st.set_defaults(func=cmd_site)
