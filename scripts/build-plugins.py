#!/usr/bin/env python3
"""
build-plugins.py — validate plugin manifest + marketplace consistency.

Since v2.0.0 the repo ships a SINGLE plugin (`plugin.json` at repo root)
with `"skills": "skills/"`.  There are no per-plugin skill copies to sync.
This script validates that:

  1. The root `plugin.json` exists and parses.
  2. Every skill directory under `skills/` contains a valid SKILL.md.
  3. `marketplace.json` references the root plugin correctly.

Modes:
  --check    Validate structure (CI gate). Exit 1 on errors.
  --write    No-op (kept for backward compat with contributor muscle-memory).
  --dry-run  Same as --check.

Run from anywhere; locates the repo root via the location of this script.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
PLUGIN_JSON = REPO_ROOT / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".github" / "plugin" / "marketplace.json"


def cmd_check() -> int:
    """Validate plugin structure. Exit 1 on errors."""
    errors = 0

    # 1. Root plugin.json
    if not PLUGIN_JSON.exists():
        print(f"❌ Missing {PLUGIN_JSON.relative_to(REPO_ROOT)}")
        return 1

    try:
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ plugin.json parse error: {e}")
        return 1

    plugin_name = plugin.get("name", "")
    if not plugin_name:
        print("❌ plugin.json missing 'name' field")
        errors += 1

    skills_field = plugin.get("skills")
    if skills_field != "skills/":
        print(f"⚠️  plugin.json 'skills' field is {skills_field!r} (expected 'skills/')")

    # 2. Every skill dir has SKILL.md
    skill_dirs = sorted(d for d in SKILLS_ROOT.iterdir() if d.is_dir())
    for sd in skill_dirs:
        if not (sd / "SKILL.md").exists():
            print(f"❌ skills/{sd.name}/ has no SKILL.md")
            errors += 1

    # 3. Marketplace.json consistency
    if not MARKETPLACE_JSON.exists():
        print(f"❌ Missing {MARKETPLACE_JSON.relative_to(REPO_ROOT)}")
        errors += 1
    else:
        try:
            mp = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ marketplace.json parse error: {e}")
            errors += 1
            mp = None

        if mp:
            plugins_list = mp.get("plugins", [])
            if len(plugins_list) != 1:
                print(f"⚠️  marketplace.json has {len(plugins_list)} plugin entries (expected 1)")
            for entry in plugins_list:
                if entry.get("name") != plugin_name:
                    print(f"❌ marketplace plugin name {entry.get('name')!r} ≠ plugin.json name {plugin_name!r}")
                    errors += 1
                mp_ver = entry.get("version", "")
                pj_ver = plugin.get("version", "")
                if mp_ver and pj_ver and mp_ver != pj_ver:
                    print(f"❌ marketplace version {mp_ver} ≠ plugin.json version {pj_ver}")
                    errors += 1

    if errors:
        print(f"\n❌ {errors} error(s) found.")
        return 1

    print(f"✅ Single-plugin structure valid — {len(skill_dirs)} skills, plugin '{plugin_name}' v{plugin.get('version', '?')}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate plugin structure (CI gate)")
    mode.add_argument("--write", action="store_true", help="no-op (kept for backward compat)")
    mode.add_argument("--dry-run", action="store_true", help="same as --check")
    args = parser.parse_args(argv)

    if args.write:
        print("ℹ️  --write is a no-op in the single-plugin model. Running --check instead.")
        return cmd_check()

    return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
