"""Canonical foundry-agt capability detector.

Source of truth for the prose example in `../../SKILL.md § Using the canonical capability detector`.

Implements the public API for issue #248 — a 9-key dict capability snapshot
that threadlight v0.5.1 calls when dispatching AGT-V4-001..007 findings as
`kind: sibling-skill`.

The detection regexes (V4_DIST_REGEX, V4_POLICY_REGEX, V4_DYNAMIC_REGEX)
and the _v4_scoped_files / _v4_signal_present helper shapes are lifted
verbatim from threadlight `production_ready.py::_check_agt_static_v4`.
The 9-key dict OUTPUT shape is the public contract from issue #248 — it
differs from threadlight's internal Finding-list output, which is correct:
this helper reshapes the v4-detection logic into a stable consumer-facing
snapshot.

Public API:
    from capability_detector import detect
    caps = detect(repo_root=".")

The return dict ALWAYS contains every key, even on an empty repo. Never raises.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Lifted from threadlight production_ready.py (microsoft/agent-governance-toolkit v4.1.0).
# These regexes detect AGT v4 surfaces in dependency declarations, policy YAML,
# and dynamic-condition source/policy bodies.

V4_DIST_REGEX = re.compile(
    r"agent-governance-toolkit(?:-(?:core|runtime|sre|cli)|\[full\])",
    re.IGNORECASE,
)
V4_POLICY_REGEX = re.compile(
    r"^\s*agent_control_specification_version\s*:|^\s*intervention_points\s*:",
    re.MULTILINE,
)
V4_DYNAMIC_REGEX = re.compile(
    r"\btime_window\s*:|\bcost_per_window\s*:|\btoken_count_per_window\s*:|\bday_of_week\s*:|agent_os\.policies\.dynamic_context",
)
# ---------------------------------------------------------------------------
# Internal file-system helpers

def _glob_repo(root: Path, *patterns: str) -> list[Path]:
    """Glob a list of patterns under root; return concrete Path objects (sorted, dedup'd)."""
    seen: set[Path] = set()
    for pat in patterns:
        try:
            for p in root.glob(pat):
                if p.is_file():
                    seen.add(p)
        except Exception:  # noqa: BLE001
            pass
    return sorted(seen)


def _read_text(path: Path) -> str:
    """Best-effort read; return empty string on any error (never raises)."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _v4_scoped_files(root: Path) -> dict[str, list[Path]]:
    """Return v4-detection-scoped file groups.

    Critical: this MUST NOT include docs/**, README.md, *.md, or specs/SPEC.md —
    docs prose mentioning v4 must not flip auto-detection to v4_preview.
    """
    deps = _glob_repo(root, "requirements*.txt", "pyproject.toml", "package.json")
    deps += _glob_repo(root, "src/**/requirements*.txt", "src/**/pyproject.toml", "src/**/package.json")
    policies = _glob_repo(root, "**/policy*.y*ml", "**/policies/**/*.y*ml", "**/agt-policy*.y*ml")
    workflows = _glob_repo(root, ".github/workflows/*.yml", ".github/workflows/*.yaml")
    verifier_json = _glob_repo(root, "tests/**/verifier*.json", "tests/**/agt-verifier*.json",
                               "docs/**/agt-verifier*.json", "verifiers/**/*.json")
    return {
        "deps": [p for p in deps if "node_modules" not in p.parts],
        "policies": policies,
        "workflows": workflows,
        "verifier_json": verifier_json,
    }


# Regex to extract a version string from a package specifier like:
# foundry-agt==4.0.0  or  foundry-agt>=4.0.0  or  foundry-agt~=4.0.0
_VERSION_EXTRACT_RE = re.compile(
    r"(?:==|~=|>=|>|<=|<|!=|@)\s*([A-Za-z0-9._+-]+)"
)

# Regex to find AGT package name + version in a single requirement line
_AGT_LINE_RE = re.compile(
    r"(agent-governance-toolkit(?:-(?:core|runtime|sre|cli)|\[full\])"
    r"|foundry[-_]agt)",
    re.IGNORECASE,
)

# Regex to detect SHA-pinned CI action reference
_CI_ACTION_RE = re.compile(r"uses:\s*foundry-agt/verify@(\S+)")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Regex for deny key in policy YAML
_DENY_RE = re.compile(r"^\s*deny\s*:", re.MULTILINE)


def _extract_package_pins_from_line(line: str) -> tuple[str, str] | None:
    """Extract (package_name, version) from a single requirement/dependency line."""
    m = _AGT_LINE_RE.search(line)
    if not m:
        return None
    pkg_name = m.group(1).lower().replace("_", "-")
    vm = _VERSION_EXTRACT_RE.search(line[m.end():])
    if not vm:
        return None
    return (pkg_name, vm.group(1))


def _scan_pyproject_toml(text: str) -> dict[str, str]:
    """Extract AGT pins from pyproject.toml dependencies array (no toml lib needed)."""
    pins: dict[str, str] = {}
    # Match the dependencies array in [project] section: dependencies = [ ... ]
    # We look for lines inside it that match AGT package names.
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"dependencies\s*=\s*\[", stripped):
            in_deps = True
        if in_deps:
            result = _extract_package_pins_from_line(stripped)
            if result:
                pins[result[0]] = result[1]
            if stripped.endswith("]"):
                in_deps = False
    return pins


def _scan_package_json(text: str) -> dict[str, str]:
    """Extract AGT pins from package.json dependencies/devDependencies."""
    pins: dict[str, str] = {}
    try:
        data = json.loads(text)
        for section in ("dependencies", "devDependencies"):
            for pkg, ver in (data.get(section) or {}).items():
                if _AGT_LINE_RE.search(pkg):
                    pkg_name = pkg.lower().replace("_", "-")
                    vm = _VERSION_EXTRACT_RE.search(ver or "")
                    version = vm.group(1) if vm else (ver or "")
                    pins[pkg_name] = version
    except Exception:  # noqa: BLE001
        pass
    return pins


# ---------------------------------------------------------------------------
# Public API

_EVIDENCE_GLOBS_SCANNED: list[str] = [
    "pyproject.toml", "requirements*.txt", "package.json",
    "**/policy*.y*ml", ".github/workflows/*.yml",
    "tests/**/verifier*.json", "verifiers/**/*.json",
]


def detect(repo_root: str = ".") -> dict:
    """Detect AGT capability posture of a repository.

    Args:
        repo_root: Path to the root of the target repository (str, not Path).

    Returns:
        A dict with exactly 9 keys. Never raises; returns defaults on any error.
    """
    _defaults: dict = {
        "version_detected": None,
        "detection_confidence": 0.0,
        "package_pins": {},
        "intervention_points_present": False,
        "policy_yaml_path": None,
        "deny_path_present": False,
        "audit_fields_in_verifier_json": [],
        "ci_action_pinned": False,
        "evidence_globs_scanned": _EVIDENCE_GLOBS_SCANNED,
    }

    try:
        root = Path(repo_root).resolve()
        files = _v4_scoped_files(root)

        package_pins: dict[str, str] = {}
        version_detected: str | None = None

        # Pass 1: Package pins
        for dep_file in files["deps"]:
            try:
                text = _read_text(dep_file)
                if dep_file.name == "pyproject.toml":
                    pins = _scan_pyproject_toml(text)
                elif dep_file.name == "package.json":
                    pins = _scan_package_json(text)
                else:
                    # requirements*.txt — line by line
                    pins = {}
                    for line in text.splitlines():
                        result = _extract_package_pins_from_line(line)
                        if result:
                            pins[result[0]] = result[1]
                package_pins.update(pins)
            except Exception:  # noqa: BLE001
                pass

        if package_pins:
            # Prefer v4 dist names over v3.7 names for version_detected
            for name in package_pins:
                if V4_DIST_REGEX.search(name):
                    version_detected = package_pins[name]
                    break
            if version_detected is None:
                version_detected = next(iter(package_pins.values()), None)

        # Pass 2: Intervention points + policy YAML path + deny path
        intervention_points_present = False
        policy_yaml_path: str | None = None
        deny_path_present = False

        for policy_file in files["policies"]:
            try:
                text = _read_text(policy_file)
                if V4_POLICY_REGEX.search(text):
                    intervention_points_present = True
                    if policy_yaml_path is None:
                        try:
                            policy_yaml_path = policy_file.relative_to(root).as_posix()
                        except ValueError:
                            policy_yaml_path = policy_file.as_posix()
                if _DENY_RE.search(text):
                    deny_path_present = True
            except Exception:  # noqa: BLE001
                pass

        # Pass 3: Audit fields in verifier JSON
        audit_fields_set: set[str] = set()
        for vf in files["verifier_json"]:
            try:
                text = _read_text(vf)
                data = json.loads(text)
                if isinstance(data, dict):
                    fields = data.get("audit_fields")
                    if isinstance(fields, list):
                        for f in fields:
                            if isinstance(f, str):
                                audit_fields_set.add(f)
            except Exception:  # noqa: BLE001
                pass

        audit_fields_in_verifier_json = sorted(audit_fields_set)

        # Pass 4: CI action pinned
        ci_action_refs: list[str] = []
        for wf in files["workflows"]:
            try:
                text = _read_text(wf)
                for m in _CI_ACTION_RE.finditer(text):
                    ci_action_refs.append(m.group(1))
            except Exception:  # noqa: BLE001
                pass

        ci_action_pinned = bool(ci_action_refs) and all(
            _SHA_RE.match(ref) for ref in ci_action_refs
        )

        # Pass 5: Confidence score (5 × 0.2 = 1.0)
        score = sum([
            0.2 if version_detected is not None else 0.0,
            0.2 if intervention_points_present else 0.0,
            0.2 if policy_yaml_path is not None else 0.0,
            0.2 if audit_fields_in_verifier_json else 0.0,
            0.2 if ci_action_pinned else 0.0,
        ])
        detection_confidence = min(round(score, 10), 1.0)

        return {
            "version_detected": version_detected,
            "detection_confidence": detection_confidence,
            "package_pins": package_pins,
            "intervention_points_present": intervention_points_present,
            "policy_yaml_path": policy_yaml_path,
            "deny_path_present": deny_path_present,
            "audit_fields_in_verifier_json": audit_fields_in_verifier_json,
            "ci_action_pinned": ci_action_pinned,
            "evidence_globs_scanned": _EVIDENCE_GLOBS_SCANNED,
        }

    except Exception:  # noqa: BLE001
        return _defaults
