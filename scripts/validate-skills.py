#!/usr/bin/env python3
"""
validate-skills.py — CI gate that productionizes AGENTS.md § 8 pre-push checks.

Checks every `skills/<name>/SKILL.md`:
  1. YAML front-matter parses
  2. `name` and `description` keys present
  3. `description` length <= 1024 chars (AGENTS.md § 2.3)
  4. `metadata.version` present and is valid SemVer
  5. No forbidden strings (PoC names, customer names, personal repos)
  6. Pin files under `references/upstream-pin.md` parse and conform to
     schema_version 2 if present

Exits 0 on clean catalog, non-zero on any failure.

This script is run by `.github/workflows/skill-validation.yml` as a PR
gate, and by every contributor before push per AGENTS.md § 8.
"""

from __future__ import annotations

import io
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

# Force UTF-8 stdout/stderr so the ✅/❌ markers in pass/fail messages
# work on Windows consoles that default to cp1252. The GitHub Actions
# runner is already UTF-8, but local contributors would otherwise crash
# with `UnicodeEncodeError` on the very first reject message.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed — pip install pyyaml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
PLUGIN_JSON = REPO_ROOT / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".github" / "plugin" / "marketplace.json"

MAX_DESCRIPTION_CHARS = 1024
KEBAB_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PoC name `kyc-poc`", re.compile(r"\bkyc-poc\b", re.I)),
    ("PoC name `card-dispute-investigation`", re.compile(r"\bcard-dispute-investigation\b", re.I)),
    ("PoC name `threadlight-v[123]`", re.compile(r"\bthreadlight-v[123]\b", re.I)),
    ("personal repo name `ricchi`", re.compile(r"\bricchi/[A-Za-z0-9_.-]+\b")),
]


class ValidationError(Exception):
    pass


def parse_frontmatter_text(text: str, label: str) -> dict[str, Any]:
    if not text.startswith("---"):
        raise ValidationError(f"{label}: file does not start with YAML front-matter (---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValidationError(f"{label}: front-matter not properly terminated by `---`")
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        raise ValidationError(f"{label}: YAML parse error: {e}") from e
    if not isinstance(data, dict):
        raise ValidationError(f"{label}: front-matter is not a mapping")
    return data


def parse_frontmatter(path: pathlib.Path) -> dict[str, Any]:
    return parse_frontmatter_text(path.read_text(encoding="utf-8"), str(path))


def validate_skill_md(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    try:
        fm = parse_frontmatter(path)
    except ValidationError as e:
        return [str(e)]

    name = fm.get("name")
    if not name:
        errors.append(f"{path}: missing `name` in front-matter")
    elif name != path.parent.name:
        errors.append(
            f"{path}: `name: {name}` does not match directory name "
            f"`{path.parent.name}` (AGENTS.md § 2.4)"
        )

    desc = fm.get("description")
    if not desc:
        errors.append(f"{path}: missing `description` in front-matter")
    elif not isinstance(desc, str):
        errors.append(f"{path}: `description` must be a string")
    elif len(desc) > MAX_DESCRIPTION_CHARS:
        errors.append(
            f"{path}: description is {len(desc)} chars, max is {MAX_DESCRIPTION_CHARS} "
            f"(AGENTS.md § 2.3)"
        )

    metadata = fm.get("metadata") or {}
    if not isinstance(metadata, dict):
        errors.append(f"{path}: `metadata` must be a mapping")
        version = None
    else:
        version = metadata.get("version")
    if not version:
        errors.append(f"{path}: missing `metadata.version` (AGENTS.md § 5)")
    elif not isinstance(version, str):
        errors.append(f"{path}: `metadata.version` must be a string")
    elif not SEMVER_RE.match(version):
        errors.append(
            f"{path}: `metadata.version: {version}` is not valid SemVer "
            f"(AGENTS.md § 5)"
        )

    body = path.read_text(encoding="utf-8")
    for label, pattern in FORBIDDEN_PATTERNS:
        for match in pattern.finditer(body):
            errors.append(
                f"{path}: forbidden string detected ({label}): "
                f"`{match.group(0)}` at offset {match.start()}"
            )

    return errors


def validate_pin_file(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    try:
        fm = parse_frontmatter(path)
    except ValidationError as e:
        return [str(e)]

    schema_version = fm.get("schema_version")
    if schema_version != 2:
        errors.append(
            f"{path}: schema_version must be 2 (got {schema_version!r}). "
            f"See scripts/templates/upstream-pin.template.md"
        )
        return errors

    freshness_tier = fm.get("freshness_tier")
    if freshness_tier not in ("A", "B", "C"):
        errors.append(f"{path}: freshness_tier must be A | B | C (got {freshness_tier!r})")

    automation_tier = fm.get("automation_tier")
    if automation_tier not in ("auto", "issue_only"):
        errors.append(
            f"{path}: automation_tier must be `auto` or `issue_only` "
            f"(got {automation_tier!r})"
        )

    validation = fm.get("validation") or {}
    if not isinstance(validation, dict):
        errors.append(f"{path}: `validation` must be a mapping")
    else:
        requires = validation.get("requires") or []
        runnable = validation.get("runnable")
        if not isinstance(requires, list):
            errors.append(f"{path}: validation.requires must be a list")
        if not isinstance(runnable, bool):
            errors.append(f"{path}: validation.runnable must be a bool")
        else:
            needs_creds = bool(
                {"azure_subscription", "foundry_project"} & set(requires or [])
            )
            if needs_creds and automation_tier == "auto":
                errors.append(
                    f"{path}: automation_tier=auto but validation.requires includes "
                    f"creds we don't ship to GHCP ({requires!r}); must be issue_only"
                )
            if needs_creds and runnable:
                errors.append(
                    f"{path}: validation.runnable=true but requires creds "
                    f"({requires!r}); must be false"
                )

    last_validated = fm.get("last_validated")
    if not last_validated:
        errors.append(f"{path}: missing `last_validated`")

    return errors


def validate_plugin_json(path: pathlib.Path) -> list[str]:
    """Validate root plugin.json manifest (single-plugin model)."""
    errors: list[str] = []
    try:
        import json as _json
        data = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path}: JSON parse error: {e}"]
    if not isinstance(data, dict):
        return [f"{path}: not a JSON object"]

    name = data.get("name")
    if not name:
        errors.append(f"{path}: missing `name`")
    elif not KEBAB_NAME_RE.match(name):
        errors.append(f"{path}: `name: {name}` must be kebab-case ([a-z][a-z0-9-]*)")
    elif len(name) > 64:
        errors.append(f"{path}: `name` exceeds 64 chars ({len(name)})")

    desc = data.get("description")
    if not desc:
        errors.append(f"{path}: missing `description`")
    elif len(desc) > MAX_DESCRIPTION_CHARS:
        errors.append(f"{path}: description {len(desc)} chars (max {MAX_DESCRIPTION_CHARS})")

    version = data.get("version")
    if not version:
        errors.append(f"{path}: missing `version`")
    elif not SEMVER_RE.match(str(version)):
        errors.append(f"{path}: `version: {version}` is not valid SemVer")

    skills = data.get("skills")
    if skills == "skills/":
        skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
        for sd in skill_dirs:
            if not (sd / "SKILL.md").exists():
                errors.append(f"{path}: skills/{sd.name}/ has no SKILL.md")
    elif skills is not None:
        errors.append(f"{path}: `skills` should be 'skills/' in single-plugin model (got {skills!r})")

    return errors


def validate_marketplace(path: pathlib.Path) -> list[str]:
    """Validate .github/plugin/marketplace.json (single-plugin model)."""
    errors: list[str] = []
    try:
        import json as _json
        data = _json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path}: JSON parse error: {e}"]
    if not isinstance(data, dict):
        return [f"{path}: not a JSON object"]

    if not data.get("name"):
        errors.append(f"{path}: missing `name`")
    if not data.get("owner") or not isinstance(data.get("owner"), dict):
        errors.append(f"{path}: missing or non-object `owner` (must be {{name, url}})")

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(f"{path}: `plugins` must be a non-empty list")
        return errors

    for p in plugins:
        if not isinstance(p, dict):
            errors.append(f"{path}: plugin entry not an object")
            continue
        pname = p.get("name")
        if not pname:
            errors.append(f"{path}: plugin entry missing `name`")
            continue
        if not p.get("version"):
            errors.append(f"{path}: plugin `{pname}` missing `version`")
        elif not SEMVER_RE.match(str(p["version"])):
            errors.append(f"{path}: plugin `{pname}` version not valid SemVer")
        if not p.get("description"):
            errors.append(f"{path}: plugin `{pname}` missing `description`")
        elif len(p["description"]) > MAX_DESCRIPTION_CHARS:
            errors.append(f"{path}: plugin `{pname}` description too long ({len(p['description'])} chars)")
        source = p.get("source")
        if not source:
            errors.append(f"{path}: plugin `{pname}` missing `source`")
        elif source == ".":
            if not PLUGIN_JSON.exists():
                errors.append(f"{path}: plugin `{pname}` source is '.' but no plugin.json at repo root")
        elif source.startswith("./"):
            target = (REPO_ROOT / source[2:] / "plugin.json")
            if not target.exists():
                errors.append(f"{path}: plugin `{pname}` source path `{source}` has no plugin.json")

        # Version consistency: marketplace version must match plugin.json version
        if PLUGIN_JSON.exists():
            try:
                root_plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
                mp_ver = p.get("version", "")
                pj_ver = root_plugin.get("version", "")
                if mp_ver and pj_ver and mp_ver != pj_ver:
                    errors.append(f"{path}: plugin `{pname}` version {mp_ver} ≠ plugin.json version {pj_ver}")
            except Exception:
                pass

    return errors


def _body_after_frontmatter(text: str) -> str:
    parts = text.split("---", 2)
    if text.startswith("---") and len(parts) >= 3:
        return parts[2]
    return text


def _plugin_skill_specs(data: dict[str, Any]) -> list[str]:
    skills = data.get("skills") or []
    if isinstance(skills, str):
        skills = [skills]
    if not isinstance(skills, list):
        return []

    specs: list[str] = []
    for entry in skills:
        if isinstance(entry, str):
            specs.append(entry)
        elif isinstance(entry, dict):
            source = entry.get("source")
            if isinstance(source, str):
                specs.append(source)
    return specs


def _plugin_skill_name(spec: str) -> str | None:
    normalized = spec[2:] if spec.startswith("./") else spec
    parts = pathlib.PurePosixPath(normalized).parts
    if len(parts) >= 2 and parts[0] == "skills":
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    return None


def _semver_core(version: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _version_bump_kind(old_version: str, new_version: str) -> str:
    old_parts = _semver_core(old_version)
    new_parts = _semver_core(new_version)
    if not old_parts or not new_parts:
        return "NONE"
    if old_parts[0] != new_parts[0]:
        return "MAJOR"
    if old_parts[1] != new_parts[1]:
        return "MINOR"
    if old_parts[2] != new_parts[2]:
        return "PATCH"
    return "NONE"


def _git_stdout(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _merge_base_main() -> str | None:
    for ref in ("origin/main", "main"):
        stdout = _git_stdout("merge-base", "HEAD", ref)
        if stdout and stdout.strip():
            return stdout.strip()
    return None


def validate_skill_plugin_version_consistency() -> list[str]:
    """Warn when MAJOR/MINOR skill bumps leave root plugin version unchanged."""
    warnings: list[str] = []
    merge_base = _merge_base_main()
    if not merge_base or not PLUGIN_JSON.exists():
        return warnings

    try:
        plugin_data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    except Exception:
        return warnings
    if not isinstance(plugin_data, dict):
        return warnings
    plugin_version = plugin_data.get("version")
    if not isinstance(plugin_version, str):
        return warnings

    old_plugin_text = _git_stdout("show", f"{merge_base}:plugin.json")
    if old_plugin_text is None:
        return warnings
    try:
        old_plugin_data = json.loads(old_plugin_text)
    except Exception:
        return warnings
    old_plugin_version = old_plugin_data.get("version")
    if not isinstance(old_plugin_version, str):
        return warnings

    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        try:
            current_fm = parse_frontmatter(skill_md)
        except ValidationError:
            continue

        current_metadata = current_fm.get("metadata") or {}
        current_version = current_metadata.get("version") if isinstance(current_metadata, dict) else None
        if not isinstance(current_version, str):
            continue

        rel = skill_md.relative_to(REPO_ROOT).as_posix()
        old_text = _git_stdout("show", f"{merge_base}:{rel}")
        if old_text is None:
            continue
        try:
            old_fm = parse_frontmatter_text(old_text, f"{merge_base}:{rel}")
        except ValidationError:
            continue

        old_metadata = old_fm.get("metadata") or {}
        old_version = old_metadata.get("version") if isinstance(old_metadata, dict) else None
        if not isinstance(old_version, str):
            continue

        bump_kind = _version_bump_kind(old_version, current_version)
        if bump_kind not in ("MAJOR", "MINOR"):
            continue

        skill_name = skill_md.parent.name
        if old_plugin_version == plugin_version:
            warnings.append(
                f"WARN: skill '{skill_name}' bumped {old_version}→{current_version} "
                f"({bump_kind}), but plugin version unchanged at {plugin_version}"
            )

    return warnings


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"ERROR: {SKILLS_DIR} does not exist", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    skill_md_count = 0
    pin_count = 0

    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill_md_count += 1
        errs = validate_skill_md(skill_md)
        all_errors.extend(errs)

    for pin_file in sorted(SKILLS_DIR.glob("*/references/upstream-pin.md")):
        pin_count += 1
        errs = validate_pin_file(pin_file)
        all_errors.extend(errs)

    if PLUGIN_JSON.exists():
        all_errors.extend(validate_plugin_json(PLUGIN_JSON))

    if MARKETPLACE_PATH.exists():
        all_errors.extend(validate_marketplace(MARKETPLACE_PATH))

    warnings = validate_skill_plugin_version_consistency()

    print(
        f"Validated {skill_md_count} SKILL.md files + {pin_count} pin files"
        + (f" + plugin.json" if PLUGIN_JSON.exists() else "")
        + (f" + marketplace.json" if MARKETPLACE_PATH.exists() else ""),
        file=sys.stderr,
    )
    for w in warnings:
        print(f"⚠️  {w}", file=sys.stderr)

    if all_errors:
        print(f"\n❌ {len(all_errors)} validation error(s):\n", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("✅ All checks passed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
