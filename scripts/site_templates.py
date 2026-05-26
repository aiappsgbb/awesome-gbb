"""site_templates.py — HTML/CSS render helpers for the awesome-gbb static catalog site.

Pure stdlib. No Jinja, no f-string-only templates — uses str.format() and .replace()
so the templates stay readable when copy-pasted. All user-controlled text is run
through html.escape() at the render boundary (defense in depth — frontmatter is
trusted authored prose but we treat it as untrusted at the rendering layer).

Exports:
  - render_layout(...)            base HTML skeleton + nav
  - render_home(...)              landing page
  - render_skills_index(...)      flat list + client-side filter
  - render_skill_detail(...)      per-skill page
  - render_plugins_index(...)     plugin overview
  - render_plugin_detail(...)     per-plugin page
  - render_llms_txt(...)          llmstxt.org markdown
  - STYLES_CSS                    single CSS string, reusing threadlight-experience palette
"""

from __future__ import annotations

import html
from typing import Any

GITHUB_BASE = 'https://github.com/aiappsgbb/awesome-gbb'

# Site lives at https://aiappsgbb.github.io/awesome-gbb/ — a GitHub Pages
# project URL with a subpath. Every root-relative href/src MUST start with
# this prefix or the browser resolves them against the user-domain root
# (aiappsgbb.github.io/) and 404s. If/when a CNAME is added that puts the
# site at a domain root, set this to '' (empty string).
SITE_BASE = '/awesome-gbb'


# ---------------------------------------------------------------------------
# Stylesheet — palette + variable names taken verbatim from
# threadlight-experience.html so the two surfaces share a visual language.
# ---------------------------------------------------------------------------

STYLES_CSS = '''/* awesome-gbb static catalog stylesheet.
   Palette + variable names mirror threadlight-experience.html (single source
   of design truth). Dark-first; light fallback via prefers-color-scheme. */

:root {
  --bg-0:   #0a0d14;
  --bg-1:   #11151f;
  --bg-2:   #181c2a;
  --bg-3:   #232a3d;
  --line:   #2a3149;
  --line-2: #3a4366;

  --ink-0:  #f5f5f7;
  --ink-1:  #cfd2dc;
  --ink-2:  #8e95a8;
  --ink-3:  #5a6178;

  --accent:        #4f6dff;
  --accent-1:      #6e87ff;
  --accent-soft:   rgba(79,109,255,.18);
  --accent-glow:   rgba(79,109,255,.42);

  --lime:          #a8ff60;
  --lime-1:        #c8ff8a;
  --lime-soft:     rgba(168,255,96,.16);

  --warn:          #ffb84a;

  --serif:  "Source Serif 4", "Source Serif Pro", "Iowan Old Style", Georgia, serif;
  --sans:   "Inter", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --mono:   "Cascadia Mono", "JetBrains Mono", "SF Mono", ui-monospace, Menlo, monospace;

  --shadow-card:  0 18px 40px rgba(0,0,0,.40), 0 4px 12px rgba(0,0,0,.28);
  --shadow-pop:   0 28px 64px rgba(0,0,0,.55), 0 8px 18px rgba(0,0,0,.40);
}

@media (prefers-color-scheme: light) {
  :root {
    --bg-0:   #f6f7fb;
    --bg-1:   #ffffff;
    --bg-2:   #eef0f7;
    --bg-3:   #e2e6f1;
    --line:   #d6dbe8;
    --line-2: #b8bfd1;
    --ink-0:  #0a0d14;
    --ink-1:  #1c2236;
    --ink-2:  #4a5168;
    --ink-3:  #828aa4;
    --accent-soft: rgba(79,109,255,.12);
    --accent-glow: rgba(79,109,255,.20);
    --lime-soft:   rgba(168,255,96,.22);
    --shadow-card: 0 12px 28px rgba(20,28,52,.10), 0 2px 8px rgba(20,28,52,.06);
    --shadow-pop:  0 22px 50px rgba(20,28,52,.16), 0 6px 14px rgba(20,28,52,.10);
  }
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg-0);
  color: var(--ink-0);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

::selection { background: var(--accent); color: #fff; }

a {
  color: var(--accent-1);
  text-decoration: none;
  border-bottom: 1px dotted var(--accent-soft);
  transition: color .15s, border-color .15s;
}
a:hover { color: var(--lime-1); border-bottom-color: var(--lime); }

code, pre, .mono { font-family: var(--mono); }

h1, h2, h3, h4 {
  font-family: var(--serif);
  font-weight: 500;
  letter-spacing: -.015em;
  margin: 0 0 .6em;
  color: var(--ink-0);
}
h1 { font-size: clamp(32px, 4.4vw, 52px); line-height: 1.05; }
h2 { font-size: clamp(24px, 2.6vw, 32px); line-height: 1.15; margin-top: 2em; }
h3 { font-size: 20px; line-height: 1.25; margin-top: 1.4em; }
p { margin: 0 0 1em; color: var(--ink-1); }

/* ---------- nav ---------- */
.nav {
  position: sticky; top: 0; z-index: 10;
  background: rgba(10,13,20,.78);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
@media (prefers-color-scheme: light) { .nav { background: rgba(246,247,251,.82); } }
.nav-inner {
  max-width: 1100px; margin: 0 auto; padding: 14px 24px;
  display: flex; align-items: center; gap: 22px;
}
.nav .brand {
  display: flex; align-items: center; gap: 10px;
  font-weight: 700; font-size: 14px; letter-spacing: .01em;
  color: var(--ink-0); border-bottom: none;
}
.nav .brand-mark {
  width: 22px; height: 22px; border-radius: 5px;
  background: conic-gradient(from 220deg at 50% 50%, var(--accent) 0%, var(--lime) 40%, var(--accent-1) 70%, var(--accent) 100%);
  box-shadow: 0 0 14px var(--accent-glow), inset 0 0 0 1px rgba(255,255,255,.15);
  position: relative;
}
.nav .brand-mark::after {
  content: ""; position: absolute; inset: 5px;
  background: var(--bg-0); border-radius: 2px;
}
.nav .links {
  display: flex; gap: 18px; margin-left: auto;
  font-size: 13px; font-weight: 500; letter-spacing: .03em;
  text-transform: uppercase; color: var(--ink-2);
}
.nav .links a {
  color: var(--ink-2); border-bottom: none;
}
.nav .links a:hover, .nav .links a.active { color: var(--ink-0); }
.nav .links a.active { color: var(--accent-1); }

@media (max-width: 640px) {
  .nav-inner { padding: 12px 18px; gap: 14px; }
  .nav .links { gap: 12px; font-size: 12px; }
}

/* ---------- layout ---------- */
main { max-width: 1100px; margin: 0 auto; padding: 48px 24px 96px; }
@media (max-width: 640px) { main { padding: 28px 18px 60px; } }

footer {
  max-width: 1100px; margin: 0 auto; padding: 36px 24px 48px;
  border-top: 1px solid var(--line); color: var(--ink-3); font-size: 13px;
}
footer .stats { color: var(--ink-2); }

/* ---------- hero (home page) ---------- */
.hero { padding: 24px 0 40px; }
.hero .eyebrow {
  text-transform: uppercase; letter-spacing: .22em;
  font-size: 11.5px; font-weight: 600; color: var(--accent-1);
  margin: 0 0 14px;
}
.hero .eyebrow .dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent); margin-right: 10px; vertical-align: 1.5px;
  box-shadow: 0 0 12px var(--accent-glow);
}
.hero .lede {
  font-family: var(--serif); font-size: clamp(18px, 1.6vw, 22px);
  line-height: 1.55; color: var(--ink-1); max-width: 720px; margin: 0;
}

/* ---------- cards ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin: 20px 0 40px;
}
.card {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 18px 18px 16px;
  transition: transform .15s, box-shadow .15s, border-color .15s;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card);
  border-color: var(--line-2);
}
.card h3 {
  margin: 0 0 6px; font-size: 17px; font-family: var(--sans); font-weight: 600;
  letter-spacing: -.005em;
}
.card h3 a { color: var(--ink-0); border-bottom: none; }
.card h3 a:hover { color: var(--accent-1); }
.card p { font-size: 14px; color: var(--ink-2); margin: 0 0 10px; }
.card .meta { font-size: 12px; color: var(--ink-3); display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

/* ---------- badges ---------- */
.badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-2);
  color: var(--ink-2);
  border: 1px solid var(--line);
  letter-spacing: .02em;
}
.badge.cat { background: var(--accent-soft); color: var(--accent-1); border-color: var(--accent-soft); }
.badge.ver { background: var(--lime-soft); color: var(--lime); border-color: var(--lime-soft); }
.badge.fresh { background: var(--lime-soft); color: var(--lime); border-color: var(--lime-soft); }
.badge.stale { background: rgba(255,184,74,.15); color: var(--warn); border-color: rgba(255,184,74,.25); }

/* ---------- code ---------- */
pre, code {
  background: var(--bg-2);
  color: var(--ink-0);
}
code { padding: 1px 6px; border-radius: 4px; font-size: 13.5px; border: 1px solid var(--line); }
pre {
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid var(--line);
  overflow-x: auto;
  font-size: 13.5px;
  line-height: 1.55;
  background:
    linear-gradient(180deg, var(--lime-soft) 0%, transparent 100%),
    var(--bg-2);
}
pre code { background: transparent; border: 0; padding: 0; }

/* ---------- section header ---------- */
.section-head { display: flex; align-items: baseline; gap: 14px; margin-top: 2.4em; }
.section-head h2 { margin: 0; }
.section-head .count { color: var(--ink-3); font-size: 13px; font-family: var(--mono); }

/* ---------- skill list (index) ---------- */
.filter-bar {
  display: flex; align-items: center; gap: 12px; margin: 18px 0 22px;
}
.filter-bar input {
  flex: 1; background: var(--bg-1); color: var(--ink-0);
  border: 1px solid var(--line); border-radius: 8px;
  padding: 10px 14px; font: inherit; font-size: 14px;
  outline: none; transition: border-color .15s, box-shadow .15s;
}
.filter-bar input:focus {
  border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft);
}
.filter-bar .count { color: var(--ink-3); font-family: var(--mono); font-size: 12px; }

.skill-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.skill-list li {
  background: var(--bg-1); border: 1px solid var(--line); border-radius: 8px;
  padding: 14px 16px;
  display: grid; grid-template-columns: 1fr auto; gap: 8px 14px;
  align-items: baseline;
}
.skill-list li[hidden] { display: none; }
.skill-list li .title { font-weight: 600; color: var(--ink-0); font-size: 15px; }
.skill-list li .title a { color: var(--ink-0); border-bottom: none; }
.skill-list li .title a:hover { color: var(--accent-1); }
.skill-list li .desc { grid-column: 1 / -1; color: var(--ink-2); font-size: 13.5px; line-height: 1.5; }
.skill-list li .meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

/* ---------- detail pages ---------- */
.detail-head { margin-bottom: 28px; }
.detail-head h1 { margin-bottom: 12px; }
.detail-head .meta { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
.detail-body p { color: var(--ink-1); max-width: 760px; }
.detail-body .cta { display: inline-block; margin-right: 12px; }

.bundled-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.bundled-list li { padding: 4px 0; }

/* ---------- accessibility helper ---------- */
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}

/* ---------- home browse grid ---------- */
.browse-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
  margin: 32px 0 16px;
}
.browse-card {
  position: relative;
  display: flex; gap: 18px; align-items: flex-start;
  padding: 22px;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  border-radius: 12px;
  color: var(--ink-0);
  text-decoration: none;
  transition: transform .18s, box-shadow .18s, border-color .18s;
}
.browse-card:hover {
  transform: translateY(-3px);
  border-color: var(--accent);
  box-shadow: var(--shadow-pop);
  color: var(--ink-0);
}
.browse-icon {
  flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  width: 44px; height: 44px;
  border-radius: 10px;
  background: var(--accent-soft);
  color: var(--accent-1);
  transition: background .18s, color .18s;
}
.browse-icon svg { width: 26px; height: 26px; }
.browse-card:hover .browse-icon { background: var(--lime-soft); color: var(--lime); }
.browse-body { display: block; flex: 1; min-width: 0; }
.browse-body h3 {
  font-family: var(--sans); font-weight: 600; font-size: 18px;
  margin: 0 0 6px; color: var(--ink-0); letter-spacing: -.005em;
}
.browse-body p {
  font-size: 14px; color: var(--ink-2); margin: 0; line-height: 1.5;
}
.browse-count {
  position: absolute; top: 16px; right: 18px;
  font-family: var(--mono); font-size: 12px;
  color: var(--ink-3); letter-spacing: .02em;
}

/* ---------- chip bar (skills index) ---------- */
.chip-bar {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 22px 0 14px;
}
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px;
  font: inherit; font-size: 13px;
  background: var(--bg-1); color: var(--ink-1);
  border: 1px solid var(--line); border-radius: 999px;
  cursor: pointer;
  transition: border-color .15s, background .15s, color .15s;
}
.chip:hover { border-color: var(--accent); color: var(--ink-0); }
.chip.active {
  background: var(--accent-soft);
  color: var(--accent-1);
  border-color: var(--accent-soft);
}
.chip-count { font-family: var(--mono); font-size: 11px; color: var(--ink-3); }
.chip.active .chip-count { color: var(--accent-1); }

/* ---------- runtime pills (home hero) ---------- */
.runtimes-row {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 20px 0 6px;
  align-items: center;
}
.runtimes-row .runtimes-label {
  font-size: 11.5px; font-weight: 600; letter-spacing: .18em;
  text-transform: uppercase; color: var(--ink-3);
  margin-right: 4px;
}
.runtime-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px;
  font: inherit; font-size: 12px; font-family: var(--mono);
  background: var(--bg-2); color: var(--ink-1);
  border: 1px solid var(--line); border-radius: 999px;
  letter-spacing: .01em;
}
.runtime-pill .dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--lime); box-shadow: 0 0 6px var(--lime-soft);
}

/* ---------- install CTA (home) ---------- */
.install-cta {
  background:
    linear-gradient(160deg, var(--accent-soft) 0%, transparent 55%),
    var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 24px 26px 22px;
  margin: 36px 0 24px;
}
.install-cta h2 { margin: 0 0 4px; font-size: 22px; }
.install-cta p.lede {
  font-family: var(--serif); font-size: 16px;
  color: var(--ink-1); margin: 0 0 16px;
}
.install-cta pre {
  margin: 0 0 12px;
  background:
    linear-gradient(180deg, var(--lime-soft) 0%, transparent 100%),
    var(--bg-2);
}
.install-cta .install-alt {
  margin: 8px 0 0; font-size: 13.5px; color: var(--ink-2);
}
.install-cta .install-alt code {
  background: var(--bg-2); color: var(--ink-0);
  padding: 2px 8px; font-size: 12.5px;
}

/* ---------- stats stripe (home) ---------- */
.stats-stripe {
  display: flex; flex-wrap: wrap; gap: 0;
  margin: 28px 0 8px;
  padding: 14px 0;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.stats-stripe .stat {
  flex: 1 1 140px;
  min-width: 140px;
  padding: 0 18px;
  border-right: 1px solid var(--line);
}
.stats-stripe .stat:last-child { border-right: 0; }
.stats-stripe .stat-num {
  display: block;
  font-family: var(--serif); font-size: 26px; font-weight: 500;
  color: var(--ink-0); line-height: 1.1;
  letter-spacing: -.02em;
}
.stats-stripe .stat-label {
  display: block;
  font-size: 11.5px; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; color: var(--ink-3);
  margin-top: 6px;
}
.stats-stripe .stat-foot {
  display: block; font-size: 12px; color: var(--ink-2);
  margin-top: 2px;
}
@media (max-width: 640px) {
  .stats-stripe .stat { flex-basis: 50%; border-right: 0; padding: 10px 8px; }
  .install-cta { padding: 18px 18px 16px; }
}
</style>
</head>'''

# Strip the trailing </style></head> — we only want the CSS body for the .css file
STYLES_CSS = STYLES_CSS.split('</style>')[0]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_LAYOUT = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="Microsoft GBB Copilot skills + plugins for Azure AI, Foundry, and governance.">
<meta name="theme-color" content="#4f6dff">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="{base}/_styles.css">
</head>
<body>
<nav class="nav">
  <div class="nav-inner">
    <a href="{base}/" class="brand"><span class="brand-mark"></span><span>awesome-gbb</span></a>
    <div class="links">
      <a href="{base}/"{a_home}>Home</a>
      <a href="{base}/skills/"{a_skills}>Skills</a>
      <a href="{base}/plugins/"{a_plugins}>Plugins</a>
      <a href="{base}/threadlight/"{a_threadlight}>Threadlight</a>
      <a href="https://github.com/aiappsgbb/awesome-gbb">GitHub</a>
    </div>
  </div>
</nav>
<main>
{body}
</main>
<footer>
  <div class="stats">{stats}</div>
  <div>Built from <code>{sha}</code> on {date} · <a href="https://github.com/aiappsgbb/awesome-gbb">aiappsgbb/awesome-gbb</a> · <a href="https://github.com/aiappsgbb/awesome-gbb/blob/main/AGENTS.md">Contributing</a> · MIT</div>
</footer>
</body>
</html>
'''


def render_layout(
    title: str,
    body: str,
    active_nav: str,
    canonical_url: str,
    *,
    sha: str = '',
    date: str = '',
    stats: str = '',
) -> str:
    """Render the full HTML document with nav, body, and footer."""
    active = {'home': '', 'skills': '', 'plugins': '', 'threadlight': ''}
    if active_nav in active:
        active[active_nav] = ' class="active"'
    return _LAYOUT.format(
        title=html.escape(title),
        canonical=html.escape(canonical_url),
        body=body,
        base=SITE_BASE,
        a_home=active['home'],
        a_skills=active['skills'],
        a_plugins=active['plugins'],
        a_threadlight=active['threadlight'],
        sha=html.escape(sha or 'dev'),
        date=html.escape(date or ''),
        stats=html.escape(stats or ''),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_sentence(text: str, *, max_chars: int = 180) -> str:
    """Return the first sentence of `text`, trimmed to `max_chars`."""
    if not text:
        return ''
    s = ' '.join(text.split())
    for terminator in ('. ', '! ', '? '):
        idx = s.find(terminator)
        if 0 < idx < max_chars + 40:
            return s[: idx + 1].strip()
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars].rsplit(' ', 1)[0]
    return cut + '…'


def _esc(text: str) -> str:
    return html.escape(text or '', quote=True)


def _skill_categories(skill_name: str, categories: dict[str, list[str]]) -> list[str]:
    return [cat for cat, members in categories.items() if skill_name in members]


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

_ICON_SKILLS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 3 2 8l10 5 10-5-10-5Z"/>'
    '<path d="m2 16 10 5 10-5"/>'
    '<path d="m2 12 10 5 10-5"/>'
    '</svg>'
)
_ICON_PLUGINS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="7" height="7" rx="1.5"/>'
    '<rect x="14" y="3" width="7" height="7" rx="1.5"/>'
    '<rect x="3" y="14" width="7" height="7" rx="1.5"/>'
    '<rect x="14" y="14" width="7" height="7" rx="1.5"/>'
    '</svg>'
)
_ICON_THREAD = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M3 12c4-6 14-6 18 0-4 6-14 6-18 0Z"/>'
    '<circle cx="12" cy="12" r="2.5"/>'
    '</svg>'
)
_ICON_DOCS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4 4h10l4 4v12H4z"/>'
    '<path d="M14 4v4h4"/>'
    '<path d="M8 13h8M8 17h6"/>'
    '</svg>'
)


def _browse_card(
    href: str, icon: str, title: str, desc: str, *,
    count: str | int | None = None, external: bool = False,
) -> str:
    ext_attr = ' target="_blank" rel="noopener"' if external else ''
    count_html = (
        f'<span class="browse-count" aria-label="{_esc(title)} count">{_esc(str(count))}</span>'
        if count is not None else ''
    )
    return (
        f'<a class="browse-card" href="{_esc(href)}"{ext_attr}>'
        f'<span class="browse-icon" aria-hidden="true">{icon}</span>'
        '<span class="browse-body">'
        f'<h3>{_esc(title)}</h3>'
        f'<p>{_esc(desc)}</p>'
        '</span>'
        f'{count_html}'
        '</a>'
    )


def render_home(
    categories: dict[str, list[str]],
    skills: list[dict[str, Any]],
    plugins: list[dict[str, Any]],
) -> str:
    """Render the landing page body.

    Mirrors awesome-copilot.github.com: hero + small grid of resource-type
    browse cards. Skill-level browsing happens on /skills/ (with category
    chip filter). Categories are kept in the signature for forward-compat
    but no longer surface on the home page.
    """
    _ = categories  # unused on home — preserved for API stability

    cards = [
        _browse_card(
            f'{SITE_BASE}/skills/', _ICON_SKILLS, 'Skills',
            'Self-contained Copilot skills for Azure AI, Microsoft Foundry, '
            'threadlight, and agent governance.',
            count=len(skills),
        ),
        _browse_card(
            f'{SITE_BASE}/plugins/', _ICON_PLUGINS, 'Plugins',
            'One-command bundles of related skills. Work in Copilot CLI, '
            'Desktop, VS Code agent mode, and Claude Code.',
            count=len(plugins),
        ),
        _browse_card(
            f'{SITE_BASE}/threadlight/', _ICON_THREAD, 'Threadlight',
            'Cinematic walkthrough of the end-to-end agentic pipeline that '
            'bundles eight skills into a single working session. '
            'Live preview now online — preconfigured demos coming soon.',
            count='live preview',
        ),
    ]

    runtime_pills = ''.join(
        f'<span class="runtime-pill"><span class="dot" aria-hidden="true"></span>{_esc(r)}</span>'
        for r in ('Copilot CLI', 'Copilot Desktop', 'VS Code agent mode', 'Claude Code')
    )

    install_cta = (
        '<section class="install-cta" aria-labelledby="install-h">'
        '<h2 id="install-h">Get started in one command</h2>'
        '<p class="lede">Add the marketplace, install the plugin — '
        'all skills, zero auth gymnastics.</p>'
        '<pre><code>'
        'copilot plugin marketplace add aiappsgbb/awesome-gbb\n'
        'copilot plugin install awesome-gbb@awesome-gbb'
        '</code></pre>'
        '<p class="install-alt">Or pick one skill at a time: '
        '<code>gh skill install aiappsgbb/awesome-gbb foundry-iq</code></p>'
        '</section>'
    )

    # Stats stripe — derived live from catalog so numbers can't drift.
    industry_count = 5  # FSI · MFG · Retail · Telco · Airline (per research-company primers + threadlight-design data-realism)
    stats_stripe = (
        '<section class="stats-stripe" aria-label="Catalog at a glance">'
        f'<div class="stat"><span class="stat-num">{len(skills)}</span>'
        '<span class="stat-label">skills</span>'
        '<span class="stat-foot">production-tested</span></div>'
        f'<div class="stat"><span class="stat-num">{len(plugins)}</span>'
        '<span class="stat-label">plugin</span>'
        '<span class="stat-foot">one-command install</span></div>'
        f'<div class="stat"><span class="stat-num">{industry_count}</span>'
        '<span class="stat-label">industries</span>'
        '<span class="stat-foot">FSI · MFG · Retail · Telco · Airline</span></div>'
        '<div class="stat"><span class="stat-num">weekly</span>'
        '<span class="stat-label">freshness checks</span>'
        '<span class="stat-foot">CI-gated, auto-refresh</span></div>'
        '</section>'
    )

    body = (
        '<section class="hero">'
        '<p class="eyebrow"><span class="dot"></span>Microsoft GBB · Copilot skill catalog</p>'
        '<h1><strong>awesome-gbb</strong></h1>'
        '<p class="lede">Microsoft GBB Copilot skills + plugins for Azure AI, '
        'Microsoft Foundry, and governance. Production-tested. Versioned. '
        'Installable individually or as one-command plugin bundles.</p>'
        '<div class="runtimes-row" aria-label="Supported runtimes">'
        '<span class="runtimes-label">Runs in</span>'
        + runtime_pills +
        '</div>'
        '</section>'
        '<section aria-labelledby="browse-h">'
        '<h2 id="browse-h" class="sr-only">Browse</h2>'
        '<div class="browse-grid">'
        + ''.join(cards)
        + '</div>'
        '</section>'
        + install_cta
        + stats_stripe
    )
    return body


# ---------------------------------------------------------------------------
# Skills index
# ---------------------------------------------------------------------------

_SKILLS_FILTER_JS = '''<script>
(function () {
  var input = document.getElementById('filter');
  var items = Array.prototype.slice.call(document.querySelectorAll('.skill-list li'));
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip-bar .chip'));
  var count = document.getElementById('skill-count');
  var activeCat = '';
  function apply() {
    var q = (input.value || '').trim().toLowerCase();
    var shown = 0;
    items.forEach(function (li) {
      var hay = li.getAttribute('data-search') || '';
      var cat = li.getAttribute('data-category') || '';
      var matchQ = !q || hay.indexOf(q) !== -1;
      var matchCat = !activeCat || cat === activeCat;
      var match = matchQ && matchCat;
      li.hidden = !match;
      if (match) shown += 1;
    });
    if (count) count.textContent = shown + ' / ' + items.length;
  }
  input.addEventListener('input', apply);
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      chips.forEach(function (c) { c.classList.remove('active'); });
      chip.classList.add('active');
      activeCat = chip.getAttribute('data-cat') || '';
      apply();
    });
  });
  apply();
})();
</script>'''


def render_skills_index(
    skills: list[dict[str, Any]],
    categories: dict[str, list[str]],
) -> str:
    """Render the flat searchable skill list with category chip filter."""
    chips = [
        f'<button type="button" class="chip active" data-cat="">All '
        f'<span class="chip-count">{len(skills)}</span></button>'
    ]
    for cat_name, members in categories.items():
        chips.append(
            f'<button type="button" class="chip" data-cat="{_esc(cat_name)}">'
            f'{_esc(cat_name)} <span class="chip-count">{len(members)}</span>'
            '</button>'
        )

    items = []
    for s in sorted(skills, key=lambda x: x['name']):
        name = s['name']
        cats = _skill_categories(name, categories)
        cat = cats[0] if cats else 'Uncategorized'
        blurb = _first_sentence(s.get('description', ''))
        search_blob = f'{name} {cat} {blurb}'.lower()
        cat_badge = f'<span class="badge cat">{_esc(cat)}</span>' if cats else ''
        items.append(
            f'<li data-search="{_esc(search_blob)}" data-category="{_esc(cat)}">'
            f'<div class="title"><a href="{SITE_BASE}/skills/{_esc(name)}/">{_esc(name)}</a></div>'
            f'<div class="meta">{cat_badge} <span class="badge ver">v{_esc(s.get("version", ""))}</span></div>'
            f'<div class="desc">{_esc(blurb)}</div>'
            '</li>'
        )
    body = (
        '<h1>Skills</h1>'
        f'<p>{len(skills)} production-tested Microsoft GBB Copilot skills. '
        'Click a category to filter, or type to search by name or description.</p>'
        '<div class="chip-bar" role="tablist" aria-label="Filter by category">'
        + ''.join(chips)
        + '</div>'
        '<div class="filter-bar">'
        '<input id="filter" type="search" placeholder="Filter skills…" autocomplete="off">'
        f'<span class="count" id="skill-count">{len(skills)} / {len(skills)}</span>'
        '</div>'
        '<ul class="skill-list">'
        + ''.join(items)
        + '</ul>'
        + _SKILLS_FILTER_JS
    )
    return body


# ---------------------------------------------------------------------------
# Skill detail
# ---------------------------------------------------------------------------

def render_skill_detail(
    skill: dict[str, Any],
    categories: dict[str, list[str]],
    plugins_containing: list[str],
) -> str:
    """Render a single skill's detail page."""
    name = skill['name']
    cats = _skill_categories(name, categories)
    cat_badges = ' '.join(f'<span class="badge cat">{_esc(c)}</span>' for c in cats)

    freshness_html = ''
    last_validated = skill.get('last_validated')
    if last_validated:
        from datetime import date, datetime
        try:
            if isinstance(last_validated, str):
                dt = datetime.strptime(last_validated, '%Y-%m-%d').date()
            else:
                dt = last_validated
            delta = (date.today() - dt).days
            badge_class = 'fresh' if delta <= 180 else 'stale'
            freshness_html = (
                '<h2>Freshness</h2>'
                f'<p><span class="badge {badge_class}">last validated {dt.isoformat()} '
                f'({delta} day{"s" if delta != 1 else ""} ago)</span></p>'
            )
        except (ValueError, TypeError):
            pass

    bundled_html = ''
    if plugins_containing:
        items = ''.join(
            f'<li><a href="{SITE_BASE}/plugins/{_esc(p)}/">{_esc(p)}</a></li>'
            for p in plugins_containing
        )
        bundled_html = (
            '<h2>Bundled in</h2>'
            f'<ul class="bundled-list">{items}</ul>'
        )

    description = skill.get('description', '').strip()

    body = (
        '<div class="detail-head">'
        f'<h1>{_esc(name)}</h1>'
        '<div class="meta">'
        f'<span class="badge ver">v{_esc(skill.get("version", ""))}</span>'
        f' {cat_badges}'
        '</div>'
        '</div>'
        '<div class="detail-body">'
        f'<p>{_esc(description)}</p>'
        '<h2>Install</h2>'
        f'<pre><code>gh skill install aiappsgbb/awesome-gbb {_esc(name)}</code></pre>'
        '<p>'
        f'<a class="cta" href="{GITHUB_BASE}/blob/main/skills/{_esc(name)}/SKILL.md">'
        'Open SKILL.md on GitHub →</a>'
        '</p>'
        + bundled_html
        + freshness_html
        + '</div>'
    )
    return body


# ---------------------------------------------------------------------------
# Plugins index
# ---------------------------------------------------------------------------

def render_plugins_index(plugins: list[dict[str, Any]]) -> str:
    """Render the 3-card plugins overview."""
    cards = ['<div class="grid">']
    for p in plugins:
        cards.append(
            '<div class="card">'
            f'<h3><a href="{SITE_BASE}/plugins/{_esc(p["name"])}/">{_esc(p["name"])}</a></h3>'
            f'<p>{_esc(_first_sentence(p.get("description", ""), max_chars=240))}</p>'
            f'<pre><code>copilot plugin install {_esc(p["name"])}@awesome-gbb</code></pre>'
            f'<div class="meta"><span class="badge">{len(p.get("skills", []))} skills</span>'
            f' <span class="badge ver">v{_esc(p.get("version", "1.0.0"))}</span></div>'
            '</div>'
        )
    cards.append('</div>')
    body = (
        '<h1>Plugins</h1>'
        '<p>One Copilot CLI plugin that installs the entire catalog '
        'in one command. Skills also remain installable individually '
        'via <code>gh skill install</code>.</p>'
        '<h2>Register the marketplace</h2>'
        '<pre><code>copilot plugin marketplace add aiappsgbb/awesome-gbb</code></pre>'
        + ''.join(cards)
    )
    return body


# ---------------------------------------------------------------------------
# Plugin detail
# ---------------------------------------------------------------------------

def render_plugin_detail(
    plugin: dict[str, Any],
    contained_skills: list[dict[str, Any]],
    categories: dict[str, list[str]],
) -> str:
    """Render a single plugin's detail page, grouped by category."""
    name = plugin['name']
    contained_names = {s['name'] for s in contained_skills}
    skills_by_name = {s['name']: s for s in contained_skills}

    groups: list[str] = []
    for cat_name, members in categories.items():
        present = [m for m in members if m in contained_names]
        if not present:
            continue
        groups.append(
            f'<div class="section-head"><h2>{_esc(cat_name)}</h2>'
            f'<span class="count">{len(present)} skill{"s" if len(present) != 1 else ""}</span></div>'
        )
        cards = ['<div class="grid">']
        for skill_name in present:
            s = skills_by_name[skill_name]
            blurb = _first_sentence(s.get('description', ''))
            cards.append(
                '<div class="card">'
                f'<h3><a href="{SITE_BASE}/skills/{_esc(skill_name)}/">{_esc(skill_name)}</a></h3>'
                f'<p>{_esc(blurb)}</p>'
                f'<div class="meta"><span class="badge ver">v{_esc(s.get("version", ""))}</span></div>'
                '</div>'
            )
        cards.append('</div>')
        groups.extend(cards)

    description = plugin.get('description', '').strip()

    body = (
        '<div class="detail-head">'
        f'<h1>{_esc(name)}</h1>'
        '<div class="meta">'
        f'<span class="badge ver">v{_esc(plugin.get("version", "1.0.0"))}</span>'
        f' <span class="badge">{len(contained_skills)} skills</span>'
        '</div>'
        '</div>'
        '<div class="detail-body">'
        f'<p>{_esc(description)}</p>'
        '<h2>Install</h2>'
        '<pre><code>copilot plugin marketplace add aiappsgbb/awesome-gbb\n'
        f'copilot plugin install {_esc(name)}@awesome-gbb</code></pre>'
        '<p>'
        f'<a class="cta" href="{GITHUB_BASE}/blob/main/plugins/{_esc(name)}/plugin.json">'
        'Open plugin.json on GitHub →</a>'
        '</p>'
        '</div>'
        + ''.join(groups)
    )
    return body


# ---------------------------------------------------------------------------
# llms.txt
# ---------------------------------------------------------------------------

def render_llms_txt(
    categories: dict[str, list[str]],
    skills: list[dict[str, Any]],
    plugins: list[dict[str, Any]],
) -> str:
    """Render an llmstxt.org-style markdown index."""
    skills_by_name = {s['name']: s for s in skills}

    lines: list[str] = []
    lines.append('# awesome-gbb')
    lines.append('')
    lines.append('> Microsoft GBB Copilot skills + plugins for Azure AI, Microsoft Foundry, and governance.')
    lines.append('')
    lines.append('## Skills')
    lines.append('')
    for cat_name, members in categories.items():
        lines.append(f'### {cat_name}')
        lines.append('')
        for member in members:
            s = skills_by_name.get(member)
            if not s:
                continue
            blurb = _first_sentence(s.get('description', ''))
            url = f'{GITHUB_BASE}/blob/main/skills/{member}/SKILL.md'
            lines.append(f'- [{member}]({url}): {blurb}')
        lines.append('')
    lines.append('## Plugins')
    lines.append('')
    for p in plugins:
        url = f'{GITHUB_BASE}/blob/main/plugins/{p["name"]}/plugin.json'
        blurb = _first_sentence(p.get('description', ''), max_chars=240)
        lines.append(f'- [{p["name"]}]({url}): {blurb}')
    lines.append('')
    return '\n'.join(lines)
