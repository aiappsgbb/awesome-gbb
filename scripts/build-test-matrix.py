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
  with two refinements:

  - Force-full-matrix paths (any one of them touched → emit the full set):
        plugin.json
        .github/plugin/marketplace.json
        scripts/build-test-matrix.py
        .github/workflows/skill-test.yml
        .github/quarantine.yml
        .github/skill-deps.yml
    These files change the matrix shape, the gating logic itself, or the
    cross-skill dependency map — so any change to them MUST re-validate
    every fixtured skill.

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
import json
import subprocess
from pathlib import Path

import yaml

# Paths whose modification forces a full-matrix run. These files change
# the matrix shape itself (plugin manifest, quarantine list), the gating
# logic (this script, the workflow), or the cross-skill dep map.
FORCE_FULL_MATRIX_PATHS: frozenset[str] = frozenset({
    "plugin.json",
    ".github/plugin/marketplace.json",
    "scripts/build-test-matrix.py",
    ".github/workflows/skill-test.yml",
    ".github/quarantine.yml",
    ".github/skill-deps.yml",
})


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
    """Extract `<name>` from any path matching `skills/<name>/...`."""
    out: set[str] = set()
    for path in changed_files:
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


def main() -> int:
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
    args = parser.parse_args()
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
