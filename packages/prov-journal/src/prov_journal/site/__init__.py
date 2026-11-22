"""Journal and handbook sites: Quartz builds the text, the server adds the store's media.

build    `prov-journal site build`: a Markdown vault -> `<sites_dir>/<name>/` with Quartz
server   `prov-journal site serve`: every built site, `/<site>/media/` answered from `<store>/media/`

Quartz v4.5.2 (pinned; v5 fetches its plugins from separate repos at build time). Its config is
`quartz.config.ts` here, written into the checkout before each build: no analytics, local fonts,
`media/` ignored, so videos are never copied into a site. Machine config keys: quartz, node,
sites_dir (see core.context).
"""
