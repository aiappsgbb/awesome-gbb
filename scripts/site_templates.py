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
<link rel="stylesheet" href="/_styles.css">
</head>
<body>
<nav class="nav">
  <div class="nav-inner">
    <a href="/" class="brand"><span class="brand-mark"></span><span>awesome-gbb</span></a>
    <div class="links">
      <a href="/"{a_home}>Home</a>
      <a href="/skills/"{a_skills}>Skills</a>
      <a href="/plugins/"{a_plugins}>Plugins</a>
      <a href="/threadlight/"{a_threadlight}>Threadlight</a>
      <a href="https://github.com/aiappsgbb/awesome-gbb">GitHub</a>
    </div>
  </div>
</nav>
<main>
{body}
</main>
<footer>
  <div class="stats">{stats}</div>
  <div>Built from <code>{sha}</code> on {date} · <a href="https://github.com/aiappsgbb/awesome-gbb">aiappsgbb/awesome-gbb</a> · MIT</div>
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

def render_home(
    categories: dict[str, list[str]],
    skills: list[dict[str, Any]],
    plugins: list[dict[str, Any]],
) -> str:
    """Render the landing page body."""
    skills_by_name = {s['name']: s for s in skills}

    plugin_cards = ['<div class="grid">']
    for p in plugins:
        plugin_cards.append(
            '<div class="card">'
            f'<h3><a href="/plugins/{_esc(p["name"])}/">{_esc(p["name"])}</a></h3>'
            f'<p>{_esc(_first_sentence(p.get("description", ""), max_chars=220))}</p>'
            f'<pre><code>copilot plugin install {_esc(p["name"])}@awesome-gbb</code></pre>'
            f'<div class="meta"><span class="badge">{len(p.get("skills", []))} skills</span>'
            f' <span class="badge ver">v{_esc(p.get("version", "1.0.0"))}</span></div>'
            '</div>'
        )
    plugin_cards.append('</div>')

    cat_sections: list[str] = []
    for cat_name, members in categories.items():
        cat_sections.append(
            f'<div class="section-head"><h2>{_esc(cat_name)}</h2>'
            f'<span class="count">{len(members)} skill{"s" if len(members) != 1 else ""}</span></div>'
        )
        cat_sections.append('<div class="grid">')
        for skill_name in members:
            s = skills_by_name.get(skill_name)
            if not s:
                continue
            blurb = _first_sentence(s.get('description', ''))
            cat_sections.append(
                '<div class="card">'
                f'<h3><a href="/skills/{_esc(skill_name)}/">{_esc(skill_name)}</a></h3>'
                f'<p>{_esc(blurb)}</p>'
                f'<div class="meta"><span class="badge ver">v{_esc(s.get("version", ""))}</span></div>'
                '</div>'
            )
        cat_sections.append('</div>')

    threadlight_tile = (
        '<div class="section-head"><h2>🧵 Threadlight experience</h2></div>'
        '<div class="card" style="max-width:760px;">'
        '<h3><a href="/threadlight/">Threadlight — one paragraph to a deployed agent</a></h3>'
        '<p>Cinematic single-page narrative for the end-to-end Threadlight pipeline. '
        'Eight skills compress eight weeks of pilot into a single working session.</p>'
        '<p><a href="/threadlight/">Open the experience →</a></p>'
        '</div>'
    )

    body = (
        '<section class="hero">'
        '<p class="eyebrow"><span class="dot"></span>Microsoft GBB · Copilot skill catalog</p>'
        '<h1><strong>awesome-gbb</strong></h1>'
        '<p class="lede">Microsoft GBB Copilot skills + plugins for Azure AI, '
        'Microsoft Foundry, and governance. 33 production-tested skills bundled into '
        '3 one-command plugins.</p>'
        '</section>'
        '<div class="section-head"><h2>Plugins</h2>'
        f'<span class="count">{len(plugins)} bundles</span></div>'
        + ''.join(plugin_cards)
        + ''.join(cat_sections)
        + threadlight_tile
    )
    return body


# ---------------------------------------------------------------------------
# Skills index
# ---------------------------------------------------------------------------

_SKILLS_FILTER_JS = '''<script>
(function () {
  var input = document.getElementById('filter');
  var items = Array.prototype.slice.call(document.querySelectorAll('.skill-list li'));
  var count = document.getElementById('skill-count');
  function apply() {
    var q = (input.value || '').trim().toLowerCase();
    var shown = 0;
    items.forEach(function (li) {
      var hay = li.getAttribute('data-search') || '';
      var match = !q || hay.indexOf(q) !== -1;
      li.hidden = !match;
      if (match) shown += 1;
    });
    if (count) count.textContent = shown + ' / ' + items.length;
  }
  input.addEventListener('input', apply);
  apply();
})();
</script>'''


def render_skills_index(
    skills: list[dict[str, Any]],
    categories: dict[str, list[str]],
) -> str:
    """Render the flat searchable skill list."""
    items = []
    for s in sorted(skills, key=lambda x: x['name']):
        name = s['name']
        cats = _skill_categories(name, categories)
        cat = cats[0] if cats else 'Uncategorized'
        blurb = _first_sentence(s.get('description', ''))
        search_blob = f'{name} {cat} {blurb}'.lower()
        cat_badge = f'<span class="badge cat">{_esc(cat)}</span>' if cats else ''
        items.append(
            f'<li data-search="{_esc(search_blob)}">'
            f'<div class="title"><a href="/skills/{_esc(name)}/">{_esc(name)}</a></div>'
            f'<div class="meta">{cat_badge} <span class="badge ver">v{_esc(s.get("version", ""))}</span></div>'
            f'<div class="desc">{_esc(blurb)}</div>'
            '</li>'
        )
    body = (
        '<h1>Skills</h1>'
        f'<p>{len(skills)} production-tested Microsoft GBB Copilot skills. '
        'Type to filter by name, category, or description.</p>'
        '<div class="filter-bar">'
        '<input id="filter" type="search" placeholder="Filter skills…" autocomplete="off" autofocus>'
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
            f'<li><a href="/plugins/{_esc(p)}/">{_esc(p)}</a></li>'
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
            f'<h3><a href="/plugins/{_esc(p["name"])}/">{_esc(p["name"])}</a></h3>'
            f'<p>{_esc(_first_sentence(p.get("description", ""), max_chars=240))}</p>'
            f'<pre><code>copilot plugin install {_esc(p["name"])}@awesome-gbb</code></pre>'
            f'<div class="meta"><span class="badge">{len(p.get("skills", []))} skills</span>'
            f' <span class="badge ver">v{_esc(p.get("version", "1.0.0"))}</span></div>'
            '</div>'
        )
    cards.append('</div>')
    body = (
        '<h1>Plugins</h1>'
        '<p>Three Copilot CLI plugin bundles that install whole engagement '
        'domains in one command. Skills also remain installable individually '
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
                f'<h3><a href="/skills/{_esc(skill_name)}/">{_esc(skill_name)}</a></h3>'
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
