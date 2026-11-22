# 0011. Docs are read remotely through Quartz sites served from this machine over Tailscale

Status: Accepted (2026-11-09)
Covers: `packages/prov-journal/src/prov_journal/site/`, `packages/prov-journal/src/prov_journal/cli.py`
PR: https://github.com/v-sangli/prov/pull/2

## Context
Journals (and the handbook) must be readable from a laptop or phone, with figures and rollout
videos, without copying videos anywhere or opening a public port. Quartz keeps Obsidian
wikilinks, embeds and frontmatter. Quartz v5 fetches its plugins from separate repos at build
time. Formerly design decision D11.

## Decision
- Quartz is pinned at v4.5.2 (Node 22.14). The machine config names the checkout (`quartz`),
  Node's bin dir (`node`, optional) and the output root (`sites_dir`, default
  `~/.cache/prov/sites`).
- `prov site build [<vault>] [--name N]` (default: this project's `journal/`, named after the
  project) writes `integrations/site/quartz.config.ts` into the Quartz checkout (analytics off,
  local fonts, no CDN caching, `media` / `.obsidian` / `private` / `templates` ignored), stages a
  text-only copy of the vault (skipping `media`, `.obsidian`, `.git`), builds it, and swaps the
  result into `<sites_dir>/<name>/`. The site records its source in `.prov-source`. Videos are
  never copied.
- `prov site serve [--host 127.0.0.1|<addr>|tailscale] [--port 8090] [--rebuild-every 300]`
  serves every built site at `/<site>/`, answers `/<site>/media/...` read-only from
  `<store>/media/` with HTTP range requests, lists sites at `/`, refuses paths that escape their
  root (404) and any method but GET/HEAD. `--host tailscale` binds the machine's Tailscale IPv4.
- Sites rebuild on a timer: every `--rebuild-every` seconds, a site whose source has a newer
  file mtime than its last build is rebuilt (0 disables).
- Only `store/media/` is served; `store/figures/` is not (journal figures are copied beside their
  doc, ADR 0007).

Not built: rebuild on journal commits; the public-cloud mirror (Cloudflare Pages + Access, clips
on R2), deferred until needed. Tailscale install and login on this machine are pending.

## Consequences
- Easier: full-size videos play in the browser from the store, with seeking.
- Easier: nothing is public; access is whoever is on the tailnet.
- Harder: when the machine is off, the sites are unreachable (the text is still on GitHub).
- Rules out copying media into sites and binding a public port by default.

## Enforced by
- `packages/prov-journal/tests/test_site.py::test_pages_and_pretty_urls`
- `packages/prov-journal/tests/test_site.py::test_media_from_store_with_ranges`
- `packages/prov-journal/tests/test_site.py::test_nothing_outside_the_roots`, `::test_writes_are_refused`
- `packages/prov-journal/tests/test_site.py::test_build_journal_with_quartz` (skips without `tools/quartz`, including in CI)
