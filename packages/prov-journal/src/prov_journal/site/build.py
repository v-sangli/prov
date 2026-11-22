"""Building a Markdown vault into a static site with Quartz.

Each site lives in `<sites_dir>/<name>/` and records its source folder in `.prov-source`, so the
server can rebuild it when the source changes.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from prov.core import log
from prov.core.errors import SiteError

SOURCE_FILE = ".prov-source"
QUARTZ_CONFIG = Path(__file__).parent / "quartz.config.ts"
SKIP = ("media", ".obsidian", ".git")

_log = log.get("site")


def _latest_mtime(root: Path) -> float:
    latest = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for f in filenames:
            latest = max(latest, os.stat(os.path.join(dirpath, f)).st_mtime)
    return latest


def build(ctx, source: Path, name: str) -> Path:
    """Build `source` (a Markdown vault) into `<sites_dir>/<name>/` with Quartz."""
    if ctx.quartz is None:
        raise SiteError("set `quartz = \"<Quartz checkout>\"` in the machine config")
    source = Path(source).resolve()
    if not source.is_dir():
        raise SiteError(f"{source} is not a folder")
    out = ctx.sites_dir / name
    shutil.copyfile(QUARTZ_CONFIG, ctx.quartz / "quartz.config.ts")
    env = dict(os.environ)
    if ctx.node is not None:
        env["PATH"] = f"{ctx.node}{os.pathsep}{env['PATH']}"
    with tempfile.TemporaryDirectory() as tmp:
        content = Path(tmp) / "content"               # staged copy: text only, plus a home page
        shutil.copytree(source, content, symlinks=True, ignore=shutil.ignore_patterns(*SKIP))
        if not (content / "index.md").exists():
            home = content / "README.md"
            (content / "index.md").write_text(home.read_text() if home.exists() else f"# {name}\n")
        staged_out = Path(tmp) / "public"
        p = subprocess.run(["npx", "quartz", "build", "-d", str(content), "-o", str(staged_out)],
                           cwd=ctx.quartz, env=env, capture_output=True, text=True)
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


def built_sites(sites_dir: Path) -> list[Path]:
    return sorted(p for p in sites_dir.iterdir() if (p / SOURCE_FILE).is_file()) if sites_dir.is_dir() else []


def rebuild_changed(ctx) -> list[str]:
    rebuilt = []
    for site in built_sites(ctx.sites_dir):
        source = Path((site / SOURCE_FILE).read_text())
        if source.is_dir() and _latest_mtime(source) > (site / SOURCE_FILE).stat().st_mtime:
            try:
                build(ctx, source, site.name)
                rebuilt.append(site.name)
            except SiteError as exc:
                _log.warning("site: rebuild of %s failed: %s", site.name, exc)
    return rebuilt
