#!/usr/bin/env python3
# scripts/build-test-matrix.py
"""Emit the GHA matrix `skills` list for copilot-cli-matrix.

Output: a single-line JSON object `{"skill": [...]}` consumable by
`fromJSON(steps.build.outputs.matrix)` in skill-test.yml.

A skill is included in the FULL matrix iff:
  1. `skills/<name>/test-fixture/consumer_prompt.md` exists.
  2. `<name>` is NOT in `.github/quarantine.yml::skills[].name`.

Sorted alphabetically for deterministic GHA matrix expansion.

--changed-only --base-ref <sha>
  Restricts the matrix to skills affected by `git diff $base_ref..HEAD`,
  with these refinements:

  - Force-full-matrix paths (any one of them touched → emit the full set):
        .github/workflows/skill-test.yml
        .github/quarantine.yml
        .github/ci-shared-preamble.md
        scripts/resolve-foundry-project.py
    These files change the per-leg input contract (workflow timeouts,
    env vars, retry logic, runner image; shared preamble prepended to
    every fixture; quarantine list; Foundry project selection) — any
    change to them MUST re-validate every fixtured skill against real
    Azure resources.

    `plugin.json`, `.github/plugin/marketplace.json`,
    `scripts/build-test-matrix.py`, and `.github/skill-deps.yml` are
    deliberately NOT in this list:

      - The two manifests are metadata: a new skill adds its own
        `skills/<name>/` paths to the diff (caught by natural skill-
        change detection), and a pure version bump has zero test
        impact.
      - The matrix script itself only decides WHICH legs run, not
        what they do. Regressions are covered by
        `scripts/tests/test_build_test_matrix.py` (10 unit tests).
      - `skill-deps.yml` is read live by `_load_dep_map` to apply
        forward fanout, so a NEW dep entry (the common case when
        adding a new skill) doesn't change existing fanout — it just
        adds new edges that fire only when their roots change. A
        REMOVED or RENAMED entry could cause silent regressions; that
        rare case is covered by `validate-skills.py` (cycle + unknown-
        ref checks) and by the unconditional `push: main` / weekly
        full-matrix canary.

    The push-to-main + weekly schedule paths still run the full
    matrix as a catalogue canary, so any plugin-structural change
    (categories, keywords, name), matrix-logic drift, or dep-graph
    rename is re-validated within ≤7 days even when the PR fan-out
    skipped it.

  - AgentOps-only CI helpers map to `foundry-agentops`, not the full
    matrix. Normal dependency expansion and fixture/quarantine filtering
    still apply.

  - Transitive forward fanout via `.github/skill-deps.yml`: if skill A
    changed and skill B declares `depends_on: [A]`, B is also emitted.
    Single-hop only (cycles are ruled out by validate-skills.py).

  Empty changed-set → `{"skill": []}`. The downstream matrix job's
  `if: fromJSON(...).skill[0] != null` guard handles the no-op case.

  PR events MUST pass `--changed-only --base-ref <base.sha>`. `push: main`,
  `schedule:`, and `workflow_dispatch` MUST omit `--changed-only` so the
  full matrix runs as a catalogue health canary.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Paths whose modification forces a full-matrix run. These files change
# the per-leg input contract (workflow timeouts, env vars, retry logic,
# runner image; shared preamble prepended to every fixture; quarantine
# list; Foundry project selection) — any change to them requires
# real-Azure re-validation across the catalog.
# plugin.json/marketplace.json, this script, and
# skill-deps.yml are NOT here: the manifests are metadata, this script
# is covered by its own unit tests, and skill-deps.yml is read live by
# _load_dep_map (a new entry is additive and doesn't change existing
# fanout). All non-listed structural drift is caught by the
# unconditional push:main full-matrix canary within ≤7 days.
# See module docstring for full rationale.
FORCE_FULL_MATRIX_PATHS: frozenset[str] = frozenset({
    ".github/workflows/skill-test.yml",
    ".github/quarantine.yml",
    # SHARED CI HARDENING preamble (post-2026-06-09 incident): every
    # fixture run prepends this file's content, so editing it changes
    # the input contract for every leg — re-validate the whole catalog.
    ".github/ci-shared-preamble.md",
    # Every Azure fixture consumes the project context selected here.
    "scripts/resolve-foundry-project.py",
})

SKILL_HELPER_PATHS: dict[str, str] = {
    "scripts/agentops-ci-preflight.py": "foundry-agentops",
    "scripts/agentops-ci-report.py": "foundry-agentops",
    "scripts/agentops-ci-diagnostic.py": "foundry-agentops",
    "scripts/setup-agentops-age.sh": "foundry-agentops",
}
DIAGNOSTIC_LABEL = "agentops-diagnostic"


def _full_fixtured_skills(repo_root: Path) -> list[str]:
    """Return alphabetically-sorted list of skills with a fixture and
    not quarantined."""
    quarantine_file = repo_root / ".github" / "quarantine.yml"
    quarantined: set[str] = set()
    if quarantine_file.exists():
        data = yaml.safe_load(quarantine_file.read_text()) or {}
        for entry in data.get("skills") or []:
            quarantined.add(entry["name"])

    skills_dir = repo_root / "skills"
    out: list[str] = []
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            if (child / "test-fixture" / "consumer_prompt.md").exists():
                if child.name not in quarantined:
                    out.append(child.name)
    return out


def _diff_filenames(repo_root: Path, base_ref: str) -> list[str]:
    """`git diff --name-only base_ref..HEAD` as a list of repo-relative paths."""
    out = subprocess.check_output(
        ["git", "-C", str(repo_root), "diff", "--name-only", f"{base_ref}..HEAD"],
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def _changed_skills_from_diff(changed_files: list[str]) -> set[str]:
    """Map skill-folder changes and exact skill-owned helper paths to skills."""
    out: set[str] = set()
    for path in changed_files:
        if path in SKILL_HELPER_PATHS:
            out.add(SKILL_HELPER_PATHS[path])
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "skills":
            out.add(parts[1])
    return out


def _load_dep_map(repo_root: Path) -> dict[str, list[str]]:
    """Parse `.github/skill-deps.yml` into `{skill: [upstreams]}`.

    Best-effort and schema-tolerant — the authoritative schema validator
    is `scripts/validate-skills.py::validate_skill_deps`. Here we just
    want to drive transitive expansion without crashing the matrix build
    on a malformed entry (the validator already failed-fast on CI by
    that point if it was malformed)."""
    deps_file = repo_root / ".github" / "skill-deps.yml"
    if not deps_file.exists():
        return {}
    data = yaml.safe_load(deps_file.read_text()) or {}
    skills = data.get("skills") or {}
    out: dict[str, list[str]] = {}
    if isinstance(skills, dict):
        for name, entry in skills.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                continue
            deps = entry.get("depends_on") or []
            if isinstance(deps, list):
                out[name] = [d for d in deps if isinstance(d, str)]
    return out


def _expand_transitively(changed: set[str], deps_map: dict[str, list[str]]) -> set[str]:
    """Forward fanout: if A is in `changed` and B.depends_on contains A,
    add B. Single-hop only."""
    expanded = set(changed)
    for skill, deps in deps_map.items():
        if any(dep in changed for dep in deps):
            expanded.add(skill)
    return expanded


def build(
    repo_root: Path,
    changed_only: bool = False,
    base_ref: str | None = None,
) -> dict[str, list[str]]:
    all_fixtured = _full_fixtured_skills(repo_root)

    if not changed_only:
        return {"skill": all_fixtured}

    assert base_ref is not None, "--changed-only requires --base-ref"
    changed_files = _diff_filenames(repo_root, base_ref)

    # Force full matrix on any infra/gating-file change.
    if any(f in FORCE_FULL_MATRIX_PATHS for f in changed_files):
        return {"skill": all_fixtured}

    changed_skills = _changed_skills_from_diff(changed_files)
    deps_map = _load_dep_map(repo_root)
    expanded = _expand_transitively(changed_skills, deps_map)

    # Intersect with the fixtured+non-quarantined set so we never emit
    # a name the downstream job can't actually execute.
    final = sorted(s for s in expanded if s in all_fixtured)
    return {"skill": final}


def _load_agentops_preflight():
    """Load the sibling preflight by its fixed repository path."""
    path = Path(__file__).resolve().with_name("agentops-ci-preflight.py")
    spec = importlib.util.spec_from_file_location("agentops_ci_preflight", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("preflight import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _diagnostic_mode(environ: dict[str, str]) -> int:
    gate = None
    try:
        gate = _load_agentops_preflight()
        approval_json = environ.get("AGENTOPS_CI_TELEMETRY_APPROVAL_JSON", "").strip()
        if approval_json:
            gate.require(
                "\n" not in approval_json and "\r" not in approval_json,
                "INVALID_JSON",
            )
        if environ.get("GITHUB_EVENT_NAME") != "pull_request":
            print("false")
            return 0
        event_path = gate.absolute_path(gate.required_env(environ, "GITHUB_EVENT_PATH"))
        event = gate.parse_json(gate.read_file(event_path))
        labels = gate.field(event, "pull_request", "labels")
        gate.require(isinstance(labels, list) and all(
            isinstance(label, dict) and isinstance(label.get("name"), str)
            for label in labels
        ), "CI_CONTEXT")
        if not any(label["name"] == DIAGNOSTIC_LABEL for label in labels):
            print("false")
            return 0
        approval_json = gate.required_env(
            environ, "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"
        ).strip()
        record = gate.parse_json(approval_json)
        gate.validate_record(record, datetime.now(timezone.utc))
        gate.exact(record["schema_version"], 2, "SCHEMA")
        gate.validate_github_context(record, environ)
    except Exception as exc:
        code = "INTERNAL_ERROR"
        if gate is not None and isinstance(exc, gate.PreflightError):
            candidate = exc.args[0] if len(exc.args) == 1 else None
            if isinstance(candidate, str) and candidate in gate.ERROR_CODES:
                code = candidate
        print(code, file=sys.stderr)
        return 1
    print("true")
    return 0


def main(argv: list[str] | None = None, *, environ: dict[str, str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else argv
    if "--agentops-diagnostic-mode" in raw_args:
        if raw_args != ["--agentops-diagnostic-mode"]:
            print("ARGUMENTS", file=sys.stderr)
            return 1
        return _diagnostic_mode(dict(os.environ if environ is None else environ))
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Restrict matrix to skills affected by git diff $base_ref..HEAD",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Required when --changed-only is set. The git ref to diff against HEAD.",
    )
    args = parser.parse_args(raw_args)
    if args.changed_only and not args.base_ref:
        parser.error("--changed-only requires --base-ref")
    print(
        json.dumps(
            build(
                args.repo_root.resolve(),
                changed_only=args.changed_only,
                base_ref=args.base_ref,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
