import http.client
import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from prov.integrations.site import build as site
from prov.integrations.site.server import make_handler
from prov.journal.docs import new_doc
from prov.journal.project import init_project
from prov.wiring import context

QUARTZ = Path(__file__).resolve().parents[2] / "tools" / "quartz"
NODE = Path(__file__).resolve().parents[2] / "tools" / "node" / "bin"


@pytest.fixture
def server(tmp_path):
    sites, media = tmp_path / "sites", tmp_path / "store" / "media"
    (sites / "demo" / "2026").mkdir(parents=True)
    (sites / "demo" / site.SOURCE_FILE).write_text(str(tmp_path))
    (sites / "demo" / "index.html").write_text("<h1>home</h1>")
    (sites / "demo" / "2026" / "doc.html").write_text("<p>doc</p>")
    (media / "run_A").mkdir(parents=True)
    (media / "run_A" / "clip.mp4").write_bytes(bytes(range(256)) * 4)      # 1024 bytes
    (tmp_path / "secret.txt").write_text("no")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sites, media))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def _get(port, path, headers=None, method="GET"):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path, headers=headers or {})
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read()


def test_pages_and_pretty_urls(server):
    assert _get(server, "/demo/")[2] == b"<h1>home</h1>"
    assert _get(server, "/demo/2026/doc")[2] == b"<p>doc</p>"
    status, headers, _ = _get(server, "/demo")
    assert status == 301 and headers["Location"] == "/demo/"
    assert b'href="/demo/"' in _get(server, "/")[2]


def test_media_from_store_with_ranges(server):
    status, headers, body = _get(server, "/demo/media/run_A/clip.mp4")
    assert status == 200 and len(body) == 1024 and headers["Content-Type"] == "video/mp4"
    assert headers["Accept-Ranges"] == "bytes"
    status, headers, body = _get(server, "/demo/media/run_A/clip.mp4", {"Range": "bytes=100-199"})
    assert status == 206 and headers["Content-Range"] == "bytes 100-199/1024" and body == bytes(range(100, 200))
    status, _, body = _get(server, "/demo/media/run_A/clip.mp4", {"Range": "bytes=-24"})
    assert status == 206 and len(body) == 24
    status, headers, _ = _get(server, "/demo/media/run_A/clip.mp4", {"Range": "bytes=5000-"})
    assert status == 416 and headers["Content-Range"] == "bytes */1024"
    status, headers, body = _get(server, "/demo/media/run_A/clip.mp4", method="HEAD")
    assert status == 200 and headers["Content-Length"] == "1024" and body == b""


@pytest.mark.parametrize("path", ["/demo/../secret.txt", "/demo/media/../../secret.txt",
                                  "/demo/%2e%2e/secret.txt", "/demo/media/%2e%2e/%2e%2e/secret.txt",
                                  "/nope/", "/demo/missing"])
def test_nothing_outside_the_roots(server, path):
    assert _get(server, path)[0] == 404


def test_writes_are_refused(server):
    assert _get(server, "/demo/", method="POST")[0] == 501


@pytest.mark.skipif(not (QUARTZ / "node_modules").is_dir(), reason="Quartz not installed in tools/")
def test_build_journal_with_quartz(registry, tmp_path, monkeypatch):
    cfg = Path(os.environ["PROV_CONFIG"])
    cfg.write_text(cfg.read_text() + f'quartz = "{QUARTZ}"\nnode = "{NODE}"\nsites_dir = "{tmp_path / "sites"}"\n')
    ctx = context()
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.chdir(root)
    init_project(ctx, root, "proj")
    (tmp_path / "store" / "media" / "run_A").mkdir(parents=True)
    (tmp_path / "store" / "media" / "run_A" / "clip.mp4").write_bytes(b"0" * 5_000_000)
    doc = new_doc("first-look")
    doc.write_text(doc.read_text() + "\n![[media/run_A/clip.mp4]]\n")

    out = site.build(ctx, root / "journal", "proj")
    assert out == tmp_path / "sites" / "proj" and (out / "index.html").is_file()
    assert Path((out / site.SOURCE_FILE).read_text()) == (root / "journal").resolve()
    assert not list(out.rglob("*.mp4"))                                   # videos never copied
    page = next(p for p in out.rglob("README.html") if "first-look" in str(p))
    assert 'media/run_A/clip.mp4' in page.read_text()
    assert site.rebuild_changed(ctx) == []                 # nothing changed since
