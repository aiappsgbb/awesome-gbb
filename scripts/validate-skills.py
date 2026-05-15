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
import pathlib
import re
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

MAX_DESCRIPTION_CHARS = 1024
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PoC name `kyc-poc`", re.compile(r"\bkyc-poc\b", re.I)),
    ("PoC name `card-dispute-investigation`", re.compile(r"\bcard-dispute-investigation\b", re.I)),
    ("PoC name `threadlight-v[123]`", re.compile(r"\bthreadlight-v[123]\b", re.I)),
    ("personal repo name `ricchi`", re.compile(r"\bricchi/[A-Za-z0-9_.-]+\b")),
]


class ValidationError(Exception):
    pass


def parse_frontmatter(path: pathlib.Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValidationError(f"{path}: file does not start with YAML front-matter (---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValidationError(f"{path}: front-matter not properly terminated by `---`")
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        raise ValidationError(f"{path}: YAML parse error: {e}") from e
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: front-matter is not a mapping")
    return data


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

    print(
        f"Validated {skill_md_count} SKILL.md files + {pin_count} pin files",
        file=sys.stderr,
    )

    if all_errors:
        print(f"\n❌ {len(all_errors)} validation error(s):\n", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("✅ All checks passed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
