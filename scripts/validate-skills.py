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

# --- 2026-Q2 testing rethink note ---
#
# The AST lints in this file (sync-credential check, MID-I/MID-G detectors,
# reference-vs-SKILL.md drift check) SURVIVE the testing rebuild per spec
# 2026-05-30-deep-audit-and-testing-rethink-design.md §5.4. They function as
# fast pre-flight filters: they catch bugs that don't require a live deploy
# to detect, and they catch them in seconds rather than minutes. The
# copilot-cli-matrix job (skill-test.yml) is the live-Azure layer; this
# file is the static layer. Both are required.
#
# DO NOT remove a lint from this file without an explicit replacement
# documented in AGENTS.md §9.8.
# --- end note ---

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

# PEP 440 pre-release suffixes — used by pip cap policy (AGENTS.md § 9.5)
_PRERELEASE_RE = re.compile(r"\d+\.\d+\.\d+(?:a|b|rc|dev)\d*")
# Matches pip specifier patterns inside quoted strings in pip install lines
_PIP_SPEC_RE = re.compile(
    r'"([A-Za-z0-9_][A-Za-z0-9_.~\[\]-]*?)'   # package name (possibly with extras)
    r'(~=|==|>=|<=|!=|>|<)'                     # operator
    r'([^"]*)"'                                 # version
)

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PoC name `kyc-poc`", re.compile(r"\bkyc-poc\b", re.I)),
    ("PoC name `card-dispute-investigation`", re.compile(r"\bcard-dispute-investigation\b", re.I)),
    ("PoC name `threadlight-v[123]`", re.compile(r"\bthreadlight-v[123]\b", re.I)),
    ("personal repo name `ricchi`", re.compile(r"\bricchi/[A-Za-z0-9_.-]+\b")),
]

# Deprecated API patterns — checked only inside fenced code blocks.
# These catch stale code samples that reference APIs removed from upstream SDKs.
# Prose mentions (deprecation notices, troubleshooting tables) are fine and excluded.
DEPRECATED_API_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("MAF removed API `client.get_toolbox()` (removed 1.3.0)",
     re.compile(r"client\.get_toolbox\s*\(")),
    ("MAF removed API `select_toolbox_tools` (removed 1.3.0)",
     re.compile(r"\bselect_toolbox_tools\s*\(")),
    ("MAF removed API `fetch_toolbox` (removed 1.3.0)",
     re.compile(r"\bfetch_toolbox\s*\(")),
    ("MAF removed constructor `SkillsProvider(skill_paths=...)` (removed 1.4.0)",
     re.compile(r"SkillsProvider\s*\(\s*skill_paths\s*=")),
    ("MAF removed `AzureOpenAIChatClient` from `agent_framework.azure` (removed 1.4.0)",
     re.compile(r"from\s+agent_framework\.azure\s+import\s+AzureOpenAIChatClient")),
    ("MAF removed `agent_framework.hosted` module — use `agent_framework_foundry_hosting` (removed 1.4.0)",
     re.compile(r"from\s+agent_framework\.hosted\s+import")),
]

# Regex to extract fenced code blocks from markdown
_CODE_BLOCK_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


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

    # Check for deprecated APIs inside fenced code blocks only.
    # Prose mentions (deprecation notices, troubleshooting) are fine.
    # Skip code blocks that contain '# OLD' or 'REMOVED' comments —
    # these are migration guides showing what NOT to do.
    code_blocks_raw = _CODE_BLOCK_RE.findall(body)
    active_blocks = [
        cb for cb in code_blocks_raw
        if not re.search(r"#\s*OLD|REMOVED|deprecated", cb, re.IGNORECASE)
    ]
    active_code = "\n".join(active_blocks)
    if active_code:
        for label, pattern in DEPRECATED_API_PATTERNS:
            for match in pattern.finditer(active_code):
                errors.append(
                    f"{path}: deprecated API in code block ({label}): "
                    f"`{match.group(0).strip()}`"
                )

    return errors


def validate_pin_pip_caps(path: pathlib.Path, fm: dict[str, Any]) -> list[str]:
    """Enforce AGENTS.md § 9.5 pin/cap policy on validation.script pip installs.

    Allowed:
      ~=X.Y.Z  (compatible release — default for stable)
      ==X.Y.ZaN / ==X.Y.ZbN / ==X.Y.ZrcN / ==X.Y.ZdevN  (pre-release exact pin)
      ~=X.Y    (broad compat — only with author justification, accepted here)

    Forbidden:
      ==X.Y.Z  for stable releases (no cap math)
      >=X.Y.Z  (unbounded — next major can break)
      Bare package name without specifier (unpinned)
    """
    errors: list[str] = []
    validation = fm.get("validation") or {}
    script = validation.get("script")
    if not isinstance(script, str):
        return errors

    for line in script.split("\n"):
        stripped = line.strip()
        # Skip comments and non-pip lines
        if stripped.startswith("#") or "pip install" not in stripped:
            continue
        # Skip lines that are just `pip install --upgrade pip`
        if re.search(r"pip install\s+--\S*\s*pip\s*$", stripped):
            continue

        for match in _PIP_SPEC_RE.finditer(stripped):
            pkg_name, operator, version_str = match.groups()
            # Resolve shell variable defaults like ${PINNED_VERSION:-3.7.0}
            resolved = re.sub(r"\$\{[^:}]+:-([^}]+)\}", r"\1", version_str)
            # Skip if still contains unresolvable shell vars
            if "$" in resolved:
                continue

            if operator == "~=":
                # Always allowed
                continue
            elif operator == "==":
                # Allowed only for pre-releases
                if _PRERELEASE_RE.search(resolved):
                    continue
                errors.append(
                    f"{path}: pip cap policy violation — `{pkg_name}{operator}{version_str}` "
                    f"uses bare `==` for a stable release. Use `~=` instead (AGENTS.md § 9.5)"
                )
            elif operator == ">=":
                errors.append(
                    f"{path}: pip cap policy violation — `{pkg_name}{operator}{version_str}` "
                    f"is unbounded (`>=`). Use `~=` to cap at the next minor (AGENTS.md § 9.5)"
                )
            # <=, !=, <, > are unusual but not explicitly forbidden — skip

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
            # auto + creds is allowed when runnable=false: the coding agent
            # does the pin edit, CI validates with OIDC Azure creds.
            # Only block auto + creds + runnable=true (agent can't run it).
            if needs_creds and automation_tier == "auto" and runnable:
                errors.append(
                    f"{path}: automation_tier=auto + runnable=true but "
                    f"validation.requires includes creds ({requires!r}); "
                    f"set runnable=false (CI validates via --include-azure)"
                )
            if needs_creds and runnable and automation_tier != "auto":
                errors.append(
                    f"{path}: validation.runnable=true but requires creds "
                    f"({requires!r}); must be false"
                )

    last_validated = fm.get("last_validated")
    if not last_validated:
        errors.append(f"{path}: missing `last_validated`")

    # Enforce pip cap/pin policy (AGENTS.md § 9.5)
    errors.extend(validate_pin_pip_caps(path, fm))

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
    """Error when MAJOR/MINOR skill bumps or new skills leave root plugin version unchanged."""
    errors: list[str] = []
    merge_base = _merge_base_main()
    if not merge_base or not PLUGIN_JSON.exists():
        return errors

    try:
        plugin_data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    except Exception:
        return errors
    if not isinstance(plugin_data, dict):
        return errors
    plugin_version = plugin_data.get("version")
    if not isinstance(plugin_version, str):
        return errors

    old_plugin_text = _git_stdout("show", f"{merge_base}:plugin.json")
    if old_plugin_text is None:
        return errors
    try:
        old_plugin_data = json.loads(old_plugin_text)
    except Exception:
        return errors
    old_plugin_version = old_plugin_data.get("version")
    if not isinstance(old_plugin_version, str):
        return errors

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
        skill_name = skill_md.parent.name

        if old_text is None:
            # New skill — requires at least MINOR plugin bump
            if old_plugin_version == plugin_version:
                errors.append(
                    f"New skill '{skill_name}' added but plugin.json version "
                    f"unchanged at {plugin_version} — bump MINOR per AGENTS.md § 5.1"
                )
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

        if old_plugin_version == plugin_version:
            errors.append(
                f"Skill '{skill_name}' bumped {old_version}→{current_version} "
                f"({bump_kind}), but plugin.json version unchanged at {plugin_version} "
                f"— bump per AGENTS.md § 5.1"
            )

    return errors


# ────────────────────────────────────────────────────────────────────────
# Reference-files validation (AGENTS.md § 7 — references/ as SSOT)
# ────────────────────────────────────────────────────────────────────────

# Skipped on syntax-check: data fixtures, prose, format-less files
_SKIP_SYNTAX_SUFFIXES = {
    ".csv",
    ".md",
    ".kql",
    ".env",
    ".bicepparam",  # cannot `az bicep build` standalone — needs the .bicep it params
    ".toml",  # parsed implicitly by `python3 -m py_compile` when imported; pyproject.toml is data
}

# § <Section Title> in a reference-file header — anchor convention from AGENTS.md § 7.
# The most common shape wraps the whole anchor in backticks:
#     `../../SKILL.md § Some Title`
# We match through to the closing backtick (DOTALL — handles wrap), and as a
# fallback also match unquoted occurrences ending at a period or end of line.
# Post-capture, _clean_anchor_capture collapses comment-line continuations.
_REF_ANCHOR_RE_QUOTED = re.compile(
    r"\.\./\.\./SKILL\.md\s*§\s*([^`]+?)`",
    re.DOTALL,
)
_REF_ANCHOR_RE_UNQUOTED = re.compile(
    r"\.\./\.\./SKILL\.md\s*§\s*(.+?)(?:\.\s|\.$|$)",
    re.MULTILINE,
)
# `##`, `###`, `####` section header in SKILL.md
_SKILL_SECTION_RE = re.compile(r"^#{2,4}\s+(.+?)\s*$", re.MULTILINE)


def _clean_anchor_capture(raw: str) -> str:
    """Collapse comment-line continuations and surrounding whitespace.

    `Custom\n# grader recipe: URL-citation quality`
        → `Custom grader recipe: URL-citation quality`

    Handles bash `#`, py `#`, yaml `#`, c-style `//` and `*`, and bare
    indentation continuations (Python docstrings).
    """
    # Replace any newline + optional comment marker + optional space with one space
    collapsed = re.sub(r"\s*\n[ \t]*(?:#|//|\*)?[ \t]?", " ", raw)
    return collapsed.strip().rstrip(".,;:`")


def _normalize_anchor(s: str) -> str:
    """Lowercase, collapse whitespace, drop emoji/punct decoration for fuzzy match."""
    s = s.lower().strip()
    # Strip leading/trailing emoji + symbols frequently used as section decoration
    s = re.sub(r"[`*_~\"']", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def validate_reference_files() -> list[str]:
    """Per-file syntax lint on every `skills/<name>/references/**`.

    Catches the silent failure mode where SKILL.md prose says "copy verbatim
    from references/..." but the canonical file has a typo, import error, or
    invalid YAML. Without this gate, the CI signal regresses to "the inline
    code was right at commit time" — exactly the duplication this skill
    catalog was supposed to eliminate.

    Coverage:
      - `.py`      → `python3 -m py_compile`
      - `.sh`      → `bash -n`
      - `.yaml`    → `yaml.safe_load`
      - `.json`    → `json.loads`
      - `.bicep`   → `az bicep build` (skipped if `az` not on PATH)
      - `.jsonl`   → line-by-line `json.loads`
      - others     → see `_SKIP_SYNTAX_SUFFIXES`
    """
    errors: list[str] = []
    az_available = _which("az") is not None
    az_warned = False

    for ref_path in sorted(SKILLS_DIR.glob("*/references/**/*")):
        if not ref_path.is_file():
            continue
        # Ignore generated artefacts that may exist locally but shouldn't be linted
        if "__pycache__" in ref_path.parts or ref_path.suffix == ".pyc":
            continue

        suffix = ref_path.suffix.lower()
        if suffix in _SKIP_SYNTAX_SUFFIXES:
            continue

        rel = ref_path.relative_to(REPO_ROOT)

        try:
            if suffix == ".py":
                _lint_python(ref_path, rel, errors)
            elif suffix == ".sh":
                _lint_bash(ref_path, rel, errors)
            elif suffix in (".yaml", ".yml"):
                _lint_yaml(ref_path, rel, errors)
            elif suffix == ".json":
                _lint_json(ref_path, rel, errors)
            elif suffix == ".jsonl":
                _lint_jsonl(ref_path, rel, errors)
            elif suffix == ".bicep":
                if az_available:
                    _lint_bicep(ref_path, rel, errors)
                elif not az_warned:
                    print(
                        f"  (skipping .bicep lint — `az` not on PATH; install azure-cli to enable)",
                        file=sys.stderr,
                    )
                    az_warned = True
        except Exception as exc:  # noqa: BLE001 — never let a linter crash the gate
            errors.append(f"{rel}: linter crashed unexpectedly: {exc}")

    return errors


def _which(cmd: str) -> str | None:
    import shutil
    return shutil.which(cmd)


def _lint_python(path: pathlib.Path, rel: pathlib.Path, errors: list[str]) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append(f"{rel}: py_compile failed:\n{(proc.stderr or proc.stdout).strip()}")


def _lint_bash(path: pathlib.Path, rel: pathlib.Path, errors: list[str]) -> None:
    bash = _which("bash") or "/bin/bash"
    proc = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
    if proc.returncode != 0:
        errors.append(f"{rel}: bash -n failed:\n{(proc.stderr or proc.stdout).strip()}")


def _lint_yaml(path: pathlib.Path, rel: pathlib.Path, errors: list[str]) -> None:
    try:
        # safe_load_all so multi-doc YAMLs (--- separated) don't false-fail
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        if not docs:
            errors.append(f"{rel}: YAML file is empty")
    except yaml.YAMLError as exc:
        errors.append(f"{rel}: invalid YAML: {exc}")


def _lint_json(path: pathlib.Path, rel: pathlib.Path, errors: list[str]) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: invalid JSON: {exc}")


def _lint_jsonl(path: pathlib.Path, rel: pathlib.Path, errors: list[str]) -> None:
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}:{lineno}: invalid JSONL: {exc}")
            return  # one error per file is enough — don't drown the report


def _lint_bicep(path: pathlib.Path, rel: pathlib.Path, errors: list[str]) -> None:
    # `az bicep build --stdout` writes ARM JSON on success, errors to stderr.
    # Use a real temp file because some bicep features rejoin via relative paths.
    proc = subprocess.run(
        ["az", "bicep", "build", "--file", str(path), "--stdout"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append(f"{rel}: az bicep build failed:\n{(proc.stderr or proc.stdout).strip()}")


def validate_reference_section_anchors() -> list[str]:
    """Section-anchor sanity: every `../../SKILL.md § <title>` reference in a
    `references/**/*` file header MUST resolve to a real `##` or `###`
    section in that skill's SKILL.md.

    Stops the "rename SKILL.md section but forget to update the canonical
    file header" silent drift. Fuzzy match: case-insensitive + whitespace
    normalized + emoji/punct decoration stripped.
    """
    errors: list[str] = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        refs_dir = skill_dir / "references"
        skill_md = skill_dir / "SKILL.md"
        if not refs_dir.exists() or not skill_md.exists():
            continue

        sections = {
            _normalize_anchor(m.group(1))
            for m in _SKILL_SECTION_RE.finditer(skill_md.read_text(encoding="utf-8"))
        }

        for ref_path in sorted(refs_dir.rglob("*")):
            if not ref_path.is_file() or "__pycache__" in ref_path.parts:
                continue
            if ref_path.suffix.lower() == ".pyc":
                continue
            # Header lives in the first ~80 lines for every convention we use
            try:
                head = "\n".join(ref_path.read_text(encoding="utf-8").splitlines()[:80])
            except (UnicodeDecodeError, OSError):
                continue

            rel = ref_path.relative_to(REPO_ROOT)
            seen: set[str] = set()
            # Prefer backtick-quoted anchors when present; fall back to bare
            # `../../SKILL.md § ...` references for older headers.
            matches = list(_REF_ANCHOR_RE_QUOTED.finditer(head))
            if not matches:
                matches = list(_REF_ANCHOR_RE_UNQUOTED.finditer(head))

            for match in matches:
                anchor = _clean_anchor_capture(match.group(1))
                if not anchor or anchor in seen:
                    continue
                seen.add(anchor)
                # Nested anchor like "Critical Rules § agent.yaml" — accept if
                # ANY segment matches a real section (the deepest level usually
                # does, but skill authors occasionally cite a parent header).
                pieces = [p.strip() for p in anchor.split("§") if p.strip()]
                if any(_anchor_resolves(p, sections) for p in pieces):
                    continue
                errors.append(
                    f"{rel}: header references SKILL.md § \"{anchor}\" "
                    f"but no matching ## or ### section in {skill_md.relative_to(REPO_ROOT)}"
                )

    return errors


def _anchor_resolves(anchor: str, sections: set[str]) -> bool:
    norm = _normalize_anchor(anchor)
    if not norm:
        return False
    if norm in sections:
        return True
    # Allow substring match for verbose titles, but only when the anchor is
    # long enough that the match is meaningful (avoid "the" matching anything).
    if len(norm) >= 8:
        return any(norm in s or s in norm for s in sections)
    return False


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

    plugin_version_errors = validate_skill_plugin_version_consistency()
    all_errors.extend(plugin_version_errors)

    reference_errors = validate_reference_files()
    all_errors.extend(reference_errors)

    anchor_errors = validate_reference_section_anchors()
    all_errors.extend(anchor_errors)

    reference_file_count = sum(
        1
        for p in SKILLS_DIR.glob("*/references/**/*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix.lower() != ".pyc"
    )

    print(
        f"Validated {skill_md_count} SKILL.md files + {pin_count} pin files "
        f"+ {reference_file_count} reference files"
        + (f" + plugin.json" if PLUGIN_JSON.exists() else "")
        + (f" + marketplace.json" if MARKETPLACE_PATH.exists() else ""),
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
