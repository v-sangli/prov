"""Journal and handbook sites: Quartz builds the text, `prov site serve` serves it with the store's media.

    prov site build [<vault dir>] [--name N]   default: this project's journal/, named after the project
    prov site serve [--host H] [--port P]      H = 127.0.0.1 (default), an address, or `tailscale`

Quartz never sees `media/` (ignored in its config), so videos are not copied into the site. Its
embeds still point at `<site>/media/...`, and the server answers those from `<store>/media/`,
read-only, with HTTP range requests so video seeking works. Sites live in `<sites_dir>/<name>/`;
each records its source so the server can rebuild it when the source changes.

Quartz v4.5.2 (pinned; v5 fetches its plugins from separate repos at build time). Its config is
prov's `templates/quartz.config.ts`, written into the checkout before each build: no analytics,
local fonts, `media/` ignored.

Machine config keys (optional): quartz = "<Quartz checkout>", node = "<dir with node/npx>",
sites_dir = "~/.cache/prov/sites".
"""

import html
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from prov import config

SOURCE_FILE = ".prov-source"
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("text/markdown", ".md")


class SiteError(Exception):
    pass


def _settings() -> dict[str, Path]:
    path = Path(os.environ.get("PROV_CONFIG", "~/.config/prov/config.toml")).expanduser()
    data = tomllib.loads(path.read_text()) if path.is_file() else {}
    out = {"sites_dir": Path(data.get("sites_dir", "~/.cache/prov/sites")).expanduser()}
    for key in ("quartz", "node"):
        if key in data:
            out[key] = Path(data[key]).expanduser()
    return out


def _latest_mtime(root: Path) -> float:
    latest = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("media", ".obsidian", ".git")]
        for f in filenames:
            latest = max(latest, os.stat(os.path.join(dirpath, f)).st_mtime)
    return latest


def build(source: Path, name: str) -> Path:
    """Build `source` (a Markdown vault) into `<sites_dir>/<name>/` with Quartz."""
    settings = _settings()
    if "quartz" not in settings:
        raise SiteError("set `quartz = \"<Quartz checkout>\"` in the machine config")
    source = Path(source).resolve()
    if not source.is_dir():
        raise SiteError(f"{source} is not a folder")
    out = settings["sites_dir"] / name
    shutil.copyfile(Path(__file__).parent / "templates" / "quartz.config.ts", settings["quartz"] / "quartz.config.ts")
    env = dict(os.environ)
    if "node" in settings:
        env["PATH"] = f"{settings['node']}{os.pathsep}{env['PATH']}"
    with tempfile.TemporaryDirectory() as tmp:
        content = Path(tmp) / "content"               # staged copy: text only, plus a home page
        shutil.copytree(source, content, symlinks=True,
                        ignore=shutil.ignore_patterns("media", ".obsidian", ".git"))
        if not (content / "index.md").exists():
            home = content / "README.md"
            (content / "index.md").write_text(home.read_text() if home.exists() else f"# {name}\n")
        staged_out = Path(tmp) / "public"
        p = subprocess.run(["npx", "quartz", "build", "-d", str(content), "-o", str(staged_out)],
                           cwd=settings["quartz"], env=env, capture_output=True, text=True)
        if p.returncode != 0:
            raise SiteError(f"quartz build failed:\n{p.stdout[-2000:]}{p.stderr[-2000:]}")
        (staged_out / SOURCE_FILE).write_text(str(source))
        out.parent.mkdir(parents=True, exist_ok=True)
        old = out.with_name(out.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if out.exists():
            out.rename(old)
        shutil.move(str(staged_out), out)
        shutil.rmtree(old, ignore_errors=True)
    return out


def rebuild_changed(sites_dir: Path) -> list[str]:
    rebuilt = []
    for site in sorted(p for p in sites_dir.iterdir() if (p / SOURCE_FILE).is_file()):
        source = Path((site / SOURCE_FILE).read_text())
        if source.is_dir() and _latest_mtime(source) > (site / SOURCE_FILE).stat().st_mtime:
            try:
                build(source, site.name)
                rebuilt.append(site.name)
            except SiteError as exc:
                print(f"prov site: rebuild of {site.name} failed: {exc}", file=sys.stderr)
    return rebuilt


def _inside(root: Path, rel: str) -> Path | None:
    """`root/rel` if it stays inside root (no '..' escapes); symlinks inside are followed."""
    candidate = os.path.normpath(os.path.join(root, rel))
    return Path(candidate) if candidate == str(root) or candidate.startswith(str(root) + os.sep) else None


def make_handler(sites_dir: Path, media_root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "prov-site"

        def log_message(self, fmt, *args):            # quiet
            pass

        def do_HEAD(self):
            self._serve(head=True)

        def do_GET(self):
            self._serve(head=False)

        def _resolve(self) -> Path | None:
            path = unquote(urlsplit(self.path).path)
            parts = [p for p in path.split("/") if p]
            if not parts:
                return None
            name, rest = parts[0], "/".join(parts[1:])
            if rest == "media" or rest.startswith("media/"):
                return _inside(media_root, rest[len("media"):].lstrip("/"))
            base = _inside(sites_dir, name)
            if base is None or not base.is_dir():
                return None
            target = _inside(base, rest)
            if target is None:
                return None
            for c in (target, Path(str(target) + ".html"), target / "index.html"):
                if c.is_file():
                    return c
            return None

        def _serve(self, head: bool) -> None:
            if urlsplit(self.path).path in ("", "/"):
                names = sorted(p.name for p in sites_dir.iterdir() if (p / SOURCE_FILE).is_file()) \
                    if sites_dir.is_dir() else []
                body = ("<!doctype html><meta charset=utf-8><title>Sites</title><h1>Sites</h1><ul>"
                        + "".join(f'<li><a href="/{html.escape(n)}/">{html.escape(n)}</a></li>' for n in names)
                        + "</ul>").encode()
                return self._send(HTTPStatus.OK, "text/html; charset=utf-8", body, head)
            url_path = urlsplit(self.path).path
            if url_path.count("/") == 1 and (sites_dir / unquote(url_path[1:])).is_dir():
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                self.send_header("Location", url_path + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            path = self._resolve()
            if path is None or not path.is_file():
                return self._send(HTTPStatus.NOT_FOUND, "text/plain", b"not found\n", head)
            size = path.stat().st_size
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            start, end = 0, size - 1
            rng = self.headers.get("Range")
            status = HTTPStatus.OK
            if rng and rng.startswith("bytes="):
                first, _, last = rng[6:].split(",")[0].partition("-")
                try:
                    if first:
                        start, end = int(first), int(last) if last else size - 1
                    else:
                        start, end = max(0, size - int(last)), size - 1
                except ValueError:
                    start, end = -1, -1
                if not (0 <= start <= end < size):
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                status = HTTPStatus.PARTIAL_CONTENT
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if head:
                return
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    remaining -= len(chunk)

        def _send(self, status, ctype, body: bytes, head: bool) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)

    return Handler


def tailscale_ip() -> str:
    if not shutil.which("tailscale"):
        raise SiteError("tailscale is not installed")
    p = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        raise SiteError(f"tailscale ip failed: {p.stderr.strip() or 'not logged in?'}")
    return p.stdout.split()[0]


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    settings = _settings()
    machine = config.load_machine()
    sites_dir = settings["sites_dir"].resolve() if settings["sites_dir"].exists() else settings["sites_dir"]
    media_root = (machine.store_root / "media")
    media_root = media_root.resolve() if media_root.exists() else media_root
    bind = tailscale_ip() if host == "tailscale" else host
    return ThreadingHTTPServer((bind, port), make_handler(sites_dir, media_root))


def serve(host: str = "127.0.0.1", port: int = 8090, rebuild_every: int = 300) -> None:
    server = make_server(host, port)
    sites_dir = _settings()["sites_dir"]

    def rebuild_loop():
        while True:
            time.sleep(rebuild_every)
            if sites_dir.is_dir():
                for name in rebuild_changed(sites_dir):
                    print(f"prov site: rebuilt {name}", file=sys.stderr)

    if rebuild_every > 0:
        threading.Thread(target=rebuild_loop, daemon=True).start()
    print(f"prov site: serving {sites_dir} and store media on http://{server.server_address[0]}:{port}/",
          file=sys.stderr)
    server.serve_forever()
