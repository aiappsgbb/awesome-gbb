"""Canonical AGT capability detector for the foundry-agt skill.

Lifts threadlight's AGT_DIST_REGEX / V4_POLICY_REGEX / V4_DYNAMIC_REGEX
+ inline filesystem scans into a single reusable function. Replaces the
prose-and-snippet detection block in earlier versions of SKILL.md.

Public API:
    detect(repo_root: str = ".") -> dict
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

AGT_DIST_REGEX = re.compile(
    r'(?:^|[\s,"\'])agt(?:-v4-dynamic)?\s*[~^=><]+\s*(\d+\.\d+(?:\.\d+)?)'
)
V4_POLICY_FILE_NAMES = ("agt.policy.yaml", "agt.policy.yml")
V4_INTERVENTION_REGEX = re.compile(
    r'\bfrom\s+agt\.intervention\b|\bagt\.intervention\.enforce\b'
)
V4_DENY_PATH_REGEX = re.compile(r'\bdeny_path\s*:')
V4_DYNAMIC_PKG_REGEX = re.compile(r'\bagt-v4-dynamic\b')
CI_ACTION_REGEX = re.compile(r'uses:\s*microsoft/agt-action@v\d+\.\d+\.\d+')

EVIDENCE_GLOBS = (
    "pyproject.toml",
    "requirements*.txt",
    "agt.policy.yaml",
    "agt.policy.yml",
    "verifier.json",
    "**/*.py",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)


def _read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""


def _detect_version(repo: Path) -> str | None:
    versions: set[str] = set()
    seen_dynamic = False
    for pyproject in [*repo.glob("pyproject.toml"),
                      *repo.glob("requirements*.txt")]:
        text = _read(pyproject)
        for m in AGT_DIST_REGEX.finditer(text):
            v = m.group(1)
            # Bucket major version for the dict-value shape callers expect
            major_minor = ".".join(v.split(".")[:2])
            versions.add(major_minor)
        if V4_DYNAMIC_PKG_REGEX.search(text):
            seen_dynamic = True
            versions.add("4.x")
    if not versions:
        return None
    if len(versions) == 1:
        only = versions.pop()
        # Normalise "4.x" alongside an explicit "4.1" → "4.1"
        return only
    # Multiple major-minor versions => "mixed"
    majors = {v.split(".")[0] for v in versions}
    if len(majors) > 1:
        return "mixed"
    return sorted(versions)[-1]


def _find_policy_yaml(repo: Path) -> Path | None:
    for name in V4_POLICY_FILE_NAMES:
        candidates = list(repo.rglob(name))
        if candidates:
            return candidates[0]
    return None


def _intervention_points_present(repo: Path) -> bool:
    for py in repo.rglob("*.py"):
        if V4_INTERVENTION_REGEX.search(_read(py)):
            return True
    return False


def _deny_path_present(policy_path: Path | None) -> bool:
    if policy_path is None:
        return False
    return bool(V4_DENY_PATH_REGEX.search(_read(policy_path)))


def _audit_fields_in_verifier(repo: Path) -> bool:
    verifier = repo / "verifier.json"
    if not verifier.exists():
        return False
    try:
        payload = json.loads(verifier.read_text())
    except json.JSONDecodeError:
        return False
    return bool(payload.get("audit_fields"))


def _ci_action_pinned(repo: Path) -> bool:
    for wf in [*(repo / ".github/workflows").rglob("*.yml"),
               *(repo / ".github/workflows").rglob("*.yaml")]:
        if CI_ACTION_REGEX.search(_read(wf)):
            return True
    return False


def detect(repo_root: str = ".") -> dict[str, Any]:
    """Scan repo for AGT signals; return canonical capability dict."""
    repo = Path(repo_root)
    policy_path = _find_policy_yaml(repo)
    return {
        "version_detected": _detect_version(repo),
        "intervention_points_present": _intervention_points_present(repo),
        "policy_yaml_path": str(policy_path) if policy_path else None,
        "deny_path_present": _deny_path_present(policy_path),
        "audit_fields_in_verifier_json": _audit_fields_in_verifier(repo),
        "ci_action_pinned": _ci_action_pinned(repo),
        "evidence_globs_scanned": list(EVIDENCE_GLOBS),
    }
