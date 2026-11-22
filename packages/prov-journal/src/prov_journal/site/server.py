"""Serving built sites: `/<site>/...` from `<sites_dir>/<site>/`, `/<site>/media/...` read-only from
`<store>/media/` with HTTP range requests (video seeking), `/` a list of sites. Paths that would
escape their root are refused. Optionally rebuilds sites whose source changed.
"""

import html
import mimetypes
import os
import shutil
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from prov.core import layout, log
from prov.core.errors import SiteError
from prov_journal.site.build import built_sites, rebuild_changed

mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("text/markdown", ".md")

_log = log.get("site")


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
                names = [p.name for p in built_sites(sites_dir)]
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


def make_server(ctx, host: str, port: int) -> ThreadingHTTPServer:
    sites_dir = ctx.sites_dir.resolve() if ctx.sites_dir.exists() else ctx.sites_dir
    media_root = ctx.store_root / layout.MEDIA_DIR
    media_root = media_root.resolve() if media_root.exists() else media_root
    bind = tailscale_ip() if host == "tailscale" else host
    return ThreadingHTTPServer((bind, port), make_handler(sites_dir, media_root))


def serve(ctx, host: str = "127.0.0.1", port: int = 8090, rebuild_every: int = 300) -> None:
    server = make_server(ctx, host, port)

    def rebuild_loop():
        while True:
            time.sleep(rebuild_every)
            for name in rebuild_changed(ctx):
                _log.info("site: rebuilt %s", name)

    if rebuild_every > 0:
        threading.Thread(target=rebuild_loop, daemon=True).start()
    _log.info("site: serving %s and store media on http://%s:%s/", ctx.sites_dir, server.server_address[0], port)
    server.serve_forever()
