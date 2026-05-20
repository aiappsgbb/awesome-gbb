#!/usr/bin/env python3
"""build-site.py — Generate the static awesome-gbb catalog site under docs/.

Pure stdlib + PyYAML. Reads source from `skills/*/SKILL.md` and
`plugins/*/plugin.json`, applies a hard-coded category map (matches
README.md § "Skills Catalog"), and writes HTML + llms.txt + CSS into the
output directory.

Idempotent: re-running produces byte-identical output (no wall-clock
timestamps — footer SHA + date come from `git log`).

Usage:
  python3 scripts/build-site.py [--out docs/] [--validate]
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

# UTF-8 stdout — see scripts/validate-skills.py for the rationale.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

try:
    import yaml
except ImportError:
    print('ERROR: PyYAML is required. Install with `pip install pyyaml`.', file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import site_templates as tpl  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Source of truth for category → skill mapping. MUST match README.md
# § "Skills Catalog". A skill present in skills/ but absent here is a build
# failure (drift detector for new skills).
CATEGORIES: dict[str, list[str]] = {
    '🏗️ Foundry Building Blocks': [
        'foundry-hosted-agents', 'foundry-teams-bot', 'ghcp-hosted-agents',
        'foundry-mcp-aca', 'foundry-evals', 'foundry-iq',
        'foundry-doc-vision-speech', 'foundry-observability',
        'foundry-cross-resource', 'foundry-vnet-deploy',
        'foundry-toolbox', 'foundry-skill-catalog',
    ],
    '🧵 Threadlight Pipeline': [
        'threadlight-design', 'threadlight-local-test', 'threadlight-deploy',
        'threadlight-safe-check', 'threadlight-event-triggers',
        'threadlight-hitl-patterns', 'threadlight-workspace-ui',
        'threadlight-demo-data-factory',
    ],
    '🛠️ Cross-Cutting Helpers': [
        'azd-patterns', 'azure-tenant-isolation', 'gbb-humanizer',
        'ghcp-cli-config', 'paygo-ptu-cost-analyzer',
    ],
    '🛡️ Governance': [
        'citadel-hub-deploy', 'citadel-spoke-onboarding', 'foundry-agt',
    ],
    '📊 Content Generation': [
        'gbb-pptx', 'auto-demo-producer',
    ],
    '🧬 Org Composition': [
        'research-company', 'compose-org',
    ],
    '🔍 Discovery': [
        'ip-catalog',
    ],
}


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    """Extract the leading YAML frontmatter block of a markdown file."""
    if not text.startswith('---'):
        return None
    parts = text.split('---', 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
        return data if isinstance(data, dict) else None
    except yaml.YAMLError:
        return None


def load_skills(repo_root: pathlib.Path) -> list[dict[str, Any]]:
    """Walk skills/*/SKILL.md and return a list of skill dicts."""
    skills: list[dict[str, Any]] = []
    for skill_md in sorted(repo_root.glob('skills/*/SKILL.md')):
        fm = _parse_frontmatter(skill_md.read_text(encoding='utf-8'))
        if not fm:
            print(f'WARN: could not parse frontmatter for {skill_md}', file=sys.stderr)
            continue
        name = fm.get('name') or skill_md.parent.name
        description = (fm.get('description') or '').strip()
        version = str((fm.get('metadata') or {}).get('version') or '')

        last_validated: str | None = None
        pin = skill_md.parent / 'references' / 'upstream-pin.md'
        if pin.exists():
            pin_fm = _parse_frontmatter(pin.read_text(encoding='utf-8'))
            if pin_fm and pin_fm.get('last_validated'):
                lv = pin_fm['last_validated']
                last_validated = lv.isoformat() if hasattr(lv, 'isoformat') else str(lv)

        skills.append({
            'name': name,
            'description': description,
            'version': version,
            'last_validated': last_validated,
        })
    return skills


def load_plugins(repo_root: pathlib.Path) -> list[dict[str, Any]]:
    """Walk plugins/*/plugin.json and return a list of plugin dicts."""
    plugins: list[dict[str, Any]] = []
    for manifest in sorted(repo_root.glob('plugins/*/plugin.json')):
        data = json.loads(manifest.read_text(encoding='utf-8'))
        skill_names = [
            entry.split('/')[-1] if isinstance(entry, str) else entry.get('source', '').split('/')[-1]
            for entry in data.get('skills', [])
        ]
        plugins.append({
            'name': data['name'],
            'description': data.get('description', ''),
            'version': str(data.get('version', '1.0.0')),
            'skills': [s for s in skill_names if s],
        })
    return plugins


def assert_categorization(skills: list[dict[str, Any]]) -> None:
    """Fail loudly if any discovered skill is missing from the CATEGORIES map."""
    all_categorized: set[str] = set()
    for members in CATEGORIES.values():
        all_categorized.update(members)
    discovered = {s['name'] for s in skills}
    missing = sorted(discovered - all_categorized)
    extra = sorted(all_categorized - discovered)
    errs: list[str] = []
    if missing:
        errs.append(
            'The following skills exist under skills/ but are NOT mapped to '
            'any category in build-site.py CATEGORIES:\n  - '
            + '\n  - '.join(missing)
            + '\nAdd them to the appropriate category in scripts/build-site.py.'
        )
    if extra:
        errs.append(
            'The following skills are in CATEGORIES but do NOT exist under '
            'skills/:\n  - '
            + '\n  - '.join(extra)
            + '\nRemove them from scripts/build-site.py or restore the skills.'
        )
    # Skill-in-multiple-categories check
    multi: list[str] = []
    for name in discovered:
        cats = [c for c, m in CATEGORIES.items() if name in m]
        if len(cats) > 1:
            multi.append(f'{name} → {cats}')
    if multi:
        errs.append('Skills appear in multiple categories:\n  - ' + '\n  - '.join(multi))
    if errs:
        for e in errs:
            print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)


def git_head_info(repo_root: pathlib.Path) -> tuple[str, str]:
    """Return (short_sha, commit_date_YYYY-MM-DD) for HEAD; fall back to ('dev', '')."""
    try:
        sha = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_root, text=True,
        ).strip()
        date = subprocess.check_output(
            ['git', 'log', '-1', '--format=%ad', '--date=short'],
            cwd=repo_root, text=True,
        ).strip()
        return sha, date
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 'dev', ''


def _write(path: pathlib.Path, content: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode('utf-8')
    path.write_bytes(data)
    return len(data)


def _validate_links(out_dir: pathlib.Path) -> int:
    """Walk every .html under out_dir, parse href="...", and verify root-relative paths exist."""
    href_re = re.compile(r'href="([^"]+)"')
    broken: list[tuple[pathlib.Path, str]] = []
    html_files = sorted(out_dir.rglob('*.html'))
    for html_file in html_files:
        text = html_file.read_text(encoding='utf-8')
        for url in href_re.findall(text):
            if not url.startswith('/'):
                continue
            # strip fragments / query
            path_only = url.split('#', 1)[0].split('?', 1)[0]
            if not path_only or path_only == '/':
                target = out_dir / 'index.html'
            elif path_only.endswith('/'):
                target = out_dir / path_only.lstrip('/') / 'index.html'
            else:
                target = out_dir / path_only.lstrip('/')
            if not target.exists():
                broken.append((html_file.relative_to(out_dir), url))
    if broken:
        print(f'BROKEN LINKS ({len(broken)}):', file=sys.stderr)
        for src, url in broken:
            print(f'  {src} → {url}', file=sys.stderr)
        return 1
    print(f'OK: {len(html_files)} HTML files, 0 broken root-relative links.')
    return 0


def build(out_dir: pathlib.Path, *, validate: bool) -> int:
    skills = load_skills(REPO_ROOT)
    plugins = load_plugins(REPO_ROOT)
    assert_categorization(skills)

    # Reverse index: skill_name → [plugin names that bundle it]
    skill_to_plugins: dict[str, list[str]] = {s['name']: [] for s in skills}
    for p in plugins:
        for skill_name in p['skills']:
            if skill_name in skill_to_plugins:
                skill_to_plugins[skill_name].append(p['name'])

    sha, date = git_head_info(REPO_ROOT)
    stats = f'{len(skills)} skills · {len(plugins)} plugins · MIT license'

    # Clean output directory (preserving dotfiles like .gitkeep / .nojekyll)
    if out_dir.exists():
        for entry in out_dir.iterdir():
            if entry.name.startswith('.'):
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / '.gitkeep').touch()
    # .nojekyll disables GitHub Pages' Jekyll layer entirely. WITHOUT this,
    # Pages silently drops every file whose name starts with `_` (Jekyll's
    # default include filter) — so `_styles.css` 404s and the live site
    # renders unstyled. .nojekyll fixes that and is the canonical "I am
    # serving a static site, leave my files alone" signal for Pages.
    (out_dir / '.nojekyll').touch()

    total_bytes = 0
    html_count = 0

    def render(active: str, title: str, body: str, canonical_path: str) -> str:
        canonical = f'https://aiappsgbb.github.io/awesome-gbb{canonical_path}'
        return tpl.render_layout(
            title=title, body=body, active_nav=active,
            canonical_url=canonical, sha=sha, date=date, stats=stats,
        )

    # Stylesheet
    total_bytes += _write(out_dir / '_styles.css', tpl.STYLES_CSS)

    # Home
    home_body = tpl.render_home(CATEGORIES, skills, plugins)
    total_bytes += _write(
        out_dir / 'index.html',
        render('home', 'awesome-gbb — Microsoft GBB Copilot skills + plugins', home_body, '/'),
    )
    html_count += 1

    # Skills index
    skills_body = tpl.render_skills_index(skills, CATEGORIES)
    total_bytes += _write(
        out_dir / 'skills' / 'index.html',
        render('skills', 'Skills — awesome-gbb', skills_body, '/skills/'),
    )
    html_count += 1

    # Skill detail pages
    for s in skills:
        detail = tpl.render_skill_detail(s, CATEGORIES, sorted(skill_to_plugins.get(s['name'], [])))
        total_bytes += _write(
            out_dir / 'skills' / s['name'] / 'index.html',
            render('skills', f'{s["name"]} — awesome-gbb', detail, f'/skills/{s["name"]}/'),
        )
        html_count += 1

    # Plugins index
    plugins_body = tpl.render_plugins_index(plugins)
    total_bytes += _write(
        out_dir / 'plugins' / 'index.html',
        render('plugins', 'Plugins — awesome-gbb', plugins_body, '/plugins/'),
    )
    html_count += 1

    # Plugin detail pages
    skills_by_name = {s['name']: s for s in skills}
    for p in plugins:
        contained = [skills_by_name[n] for n in p['skills'] if n in skills_by_name]
        detail = tpl.render_plugin_detail(p, contained, CATEGORIES)
        total_bytes += _write(
            out_dir / 'plugins' / p['name'] / 'index.html',
            render('plugins', f'{p["name"]} — awesome-gbb', detail, f'/plugins/{p["name"]}/'),
        )
        html_count += 1

    # llms.txt
    total_bytes += _write(out_dir / 'llms.txt', tpl.render_llms_txt(CATEGORIES, skills, plugins))

    # Threadlight experience — verbatim copy
    threadlight_src = REPO_ROOT / 'threadlight-experience.html'
    if threadlight_src.exists():
        threadlight_dst = out_dir / 'threadlight' / 'index.html'
        threadlight_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(threadlight_src, threadlight_dst)
        total_bytes += threadlight_dst.stat().st_size
        html_count += 1
    else:
        print(f'WARN: {threadlight_src} not found — skipping /threadlight/', file=sys.stderr)

    # Backward-compat for the legacy /threadlight-experience.html URL.
    # Pre-flip, Pages served the file at the repo root with the WHOLE site
    # being TL. Post-flip, the home is the catalog hub and TL lives under
    # /threadlight/. We deliberately serve a CHOOSER page here instead of a
    # silent auto-redirect: when a browser has cached the old root
    # `<meta refresh>` (which sends /  →  /threadlight-experience.html),
    # a silent redirect to /threadlight/ would never surface the new hub.
    # The chooser breaks the cached redirect chain visibly and lets the
    # user pick either destination.
    chooser_html = (
        '<!doctype html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>awesome-gbb — this URL has moved</title>\n'
        '<link rel="stylesheet" href="/_styles.css">\n'
        '</head>\n'
        '<body>\n'
        '<main>\n'
        '<section class="hero" style="text-align:center;">\n'
        '<p class="eyebrow"><span class="dot"></span>This URL has moved</p>\n'
        '<h1>awesome-gbb</h1>\n'
        '<p class="lede" style="margin:0 auto 28px;">'
        'The catalog now has a proper landing page. '
        '<code>/threadlight-experience.html</code> is no longer the whole site '
        '— Threadlight is one of four resources in the hub.'
        '</p>\n'
        '<div class="browse-grid" style="max-width:680px;margin:0 auto;">\n'
        '<a class="browse-card" href="/">'
        '<span class="browse-icon" aria-hidden="true">→</span>'
        '<span class="browse-body"><h3>awesome-gbb hub</h3>'
        '<p>Skills · Plugins · Threadlight · Contributing</p></span>'
        '</a>\n'
        '<a class="browse-card" href="/threadlight/">'
        '<span class="browse-icon" aria-hidden="true">🧵</span>'
        '<span class="browse-body"><h3>Threadlight experience</h3>'
        '<p>Cinematic walkthrough (the page you used to land on).</p></span>'
        '</a>\n'
        '</div>\n'
        '</section>\n'
        '</main>\n'
        '</body>\n'
        '</html>\n'
    )
    total_bytes += _write(out_dir / 'threadlight-experience.html', chooser_html)
    html_count += 1

    print(
        f'Built {len(skills)} skills, {len(plugins)} plugins → {out_dir}/ '
        f'({html_count} HTML files, {total_bytes:,} total bytes)'
    )

    if validate:
        return _validate_links(out_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build the awesome-gbb static catalog site.')
    parser.add_argument(
        '--out', default='docs',
        help='Output directory (default: docs/, relative to repo root if not absolute)',
    )
    parser.add_argument(
        '--validate', action='store_true',
        help='After build, parse every .html and assert root-relative links resolve.',
    )
    args = parser.parse_args(argv)

    out_path = pathlib.Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    return build(out_path, validate=args.validate)


if __name__ == '__main__':
    sys.exit(main())
