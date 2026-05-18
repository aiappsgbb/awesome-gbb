#!/usr/bin/env python3
"""
build-plugins.py — copy skills/<name>/ into plugins/<plugin>/skills/<name>/

Source of truth for every skill is `skills/<name>/`. Each plugin manifest
at `plugins/<plugin>/plugin.json` lists which skills it bundles via its
`skills` array (entries are local paths relative to the plugin root, e.g.
`skills/foundry-iq`).

This script keeps the per-plugin `skills/` subtree in lock-step with the
source `skills/` tree at the repo root, using SHA-based comparison and
rsync-style delete for files removed at source.

Modes:
  --check    Compare plugin copies to source. Exit 1 on any drift; print
             a per-file diff summary. CI gate uses this mode.
  --write    Sync plugin copies from source. Creates/updates/removes files
             to match. Contributors run this after editing a skill.
  --dry-run  Like --write but reports what would change without writing.

Run from anywhere; locates the repo root via the location of this script.

Exits 0 on success (no drift in --check, sync complete in --write),
1 on drift in --check or any I/O error.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import shutil
import sys
from typing import Iterable

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
PLUGINS_ROOT = REPO_ROOT / "plugins"

EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo"}


def _iter_relative_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    """Yield every file path under root, relative to root, excluding caches."""
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIR_NAMES for part in p.relative_to(root).parts):
            continue
        if p.suffix in EXCLUDE_FILE_SUFFIXES:
            continue
        yield p.relative_to(root)


def _sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_plugin_manifests() -> list[tuple[pathlib.Path, dict]]:
    """Return [(plugin_dir, parsed plugin.json), ...] for every plugin."""
    out: list[tuple[pathlib.Path, dict]] = []
    if not PLUGINS_ROOT.exists():
        return out
    for plugin_dir in sorted(PLUGINS_ROOT.iterdir()):
        if not plugin_dir.is_dir():
            continue
        manifest = plugin_dir / "plugin.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ {manifest.relative_to(REPO_ROOT)} parse error: {e}")
            sys.exit(1)
        out.append((plugin_dir, data))
    return out


def _plugin_skill_specs(plugin_data: dict) -> list[str]:
    """Return the list of skill subpaths declared by plugin.json."""
    skills_field = plugin_data.get("skills")
    if skills_field is None:
        return []
    if isinstance(skills_field, str):
        return [skills_field]
    if isinstance(skills_field, list):
        return [str(s) for s in skills_field]
    raise ValueError(f"plugin.json `skills` must be string or list, got {type(skills_field).__name__}")


def _resolve_skill_name(spec: str) -> str:
    """Turn a plugin.json skill spec like `skills/foundry-iq` into `foundry-iq`."""
    p = pathlib.PurePosixPath(spec)
    parts = p.parts
    if len(parts) >= 2 and parts[0] == "skills":
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    raise ValueError(f"Cannot derive skill name from plugin.json entry: {spec!r}")


def _compare_trees(src: pathlib.Path, dst: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path], list[pathlib.Path]]:
    """Return (missing_in_dst, drifted, extra_in_dst) relative paths."""
    src_files = set(_iter_relative_files(src))
    dst_files = set(_iter_relative_files(dst))

    missing = sorted(src_files - dst_files)
    extra = sorted(dst_files - src_files)
    drifted: list[pathlib.Path] = []

    for rel in sorted(src_files & dst_files):
        sp, dp = src / rel, dst / rel
        if sp.stat().st_size != dp.stat().st_size or _sha256_of(sp) != _sha256_of(dp):
            drifted.append(rel)

    return missing, drifted, extra


def _sync_tree(src: pathlib.Path, dst: pathlib.Path, dry_run: bool) -> int:
    """Rsync-style copy src -> dst. Returns number of changes."""
    changes = 0
    missing, drifted, extra = _compare_trees(src, dst)

    for rel in missing + drifted:
        sp, dp = src / rel, dst / rel
        if dry_run:
            verb = "WOULD CREATE" if rel in missing else "WOULD UPDATE"
            print(f"  {verb}: {dp.relative_to(REPO_ROOT)}")
        else:
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dp)
        changes += 1

    for rel in extra:
        dp = dst / rel
        if dry_run:
            print(f"  WOULD REMOVE: {dp.relative_to(REPO_ROOT)}")
        else:
            dp.unlink()
            parent = dp.parent
            while parent != dst and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        changes += 1

    return changes


def cmd_check() -> int:
    """Compare every plugin's skills/ tree against source. Exit 1 on drift."""
    manifests = _load_plugin_manifests()
    if not manifests:
        print("⚠️  No plugins found under plugins/ — nothing to check.")
        return 0

    total_drift = 0
    for plugin_dir, data in manifests:
        plugin_name = data.get("name", plugin_dir.name)
        specs = _plugin_skill_specs(data)
        for spec in specs:
            skill_name = _resolve_skill_name(spec)
            src = SKILLS_ROOT / skill_name
            dst = plugin_dir / "skills" / skill_name

            if not src.exists():
                print(f"❌ {plugin_name}: source skill not found: skills/{skill_name}/")
                total_drift += 1
                continue

            missing, drifted, extra = _compare_trees(src, dst)
            for rel in missing:
                print(f"❌ {plugin_name}/{skill_name}: missing in plugin copy: {rel}")
                total_drift += 1
            for rel in drifted:
                print(f"❌ {plugin_name}/{skill_name}: drifted: {rel}")
                total_drift += 1
            for rel in extra:
                print(f"❌ {plugin_name}/{skill_name}: extra in plugin copy (deleted at source?): {rel}")
                total_drift += 1

    if total_drift:
        print(f"\n❌ {total_drift} file(s) out of sync. Run `python scripts/build-plugins.py --write` and commit.")
        return 1

    print(f"✅ All plugin copies in sync with skills/ source ({len(manifests)} plugin(s)).")
    return 0


def cmd_write(dry_run: bool) -> int:
    """Sync plugin copies from source. --dry-run shows what would change."""
    manifests = _load_plugin_manifests()
    if not manifests:
        print("⚠️  No plugins found under plugins/ — nothing to write.")
        return 0

    total = 0
    for plugin_dir, data in manifests:
        plugin_name = data.get("name", plugin_dir.name)
        specs = _plugin_skill_specs(data)
        plugin_changes = 0
        for spec in specs:
            skill_name = _resolve_skill_name(spec)
            src = SKILLS_ROOT / skill_name
            dst = plugin_dir / "skills" / skill_name

            if not src.exists():
                print(f"❌ {plugin_name}: source skill not found: skills/{skill_name}/")
                return 1

            plugin_changes += _sync_tree(src, dst, dry_run)

        if plugin_changes:
            verb = "would change" if dry_run else "synced"
            print(f"  {plugin_name}: {plugin_changes} file(s) {verb}")
        total += plugin_changes

    if total == 0:
        print(f"✅ Nothing to do — all plugin copies already in sync ({len(manifests)} plugin(s)).")
    else:
        verb = "would be written" if dry_run else "written"
        print(f"\n✅ {total} file(s) {verb} across {len(manifests)} plugin(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 if any plugin copy drifts from source")
    mode.add_argument("--write", action="store_true", help="sync plugin copies from source")
    mode.add_argument("--dry-run", action="store_true", help="report what --write would do without writing")
    args = parser.parse_args(argv)

    if args.check:
        return cmd_check()
    if args.write:
        return cmd_write(dry_run=False)
    if args.dry_run:
        return cmd_write(dry_run=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
