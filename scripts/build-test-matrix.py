#!/usr/bin/env python3
# scripts/build-test-matrix.py
"""Emit the GHA matrix `skills` list for copilot-cli-matrix.

Output: a single-line JSON object `{"skill": [...]}` consumable by
`fromJSON(steps.build.outputs.matrix)` in skill-test.yml.

A skill is included iff:
  1. `skills/<name>/test-fixture/consumer_prompt.md` exists.
  2. `<name>` is NOT in `.github/quarantine.yml::skills[].name`.

Sorted alphabetically for deterministic GHA matrix expansion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def build(repo_root: Path) -> dict[str, list[str]]:
    quarantine_file = repo_root / ".github" / "quarantine.yml"
    quarantined: set[str] = set()
    if quarantine_file.exists():
        data = yaml.safe_load(quarantine_file.read_text()) or {}
        for entry in data.get("skills") or []:
            quarantined.add(entry["name"])

    skills_dir = repo_root / "skills"
    matrix_skills: list[str] = []
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            if (child / "test-fixture" / "consumer_prompt.md").exists():
                if child.name not in quarantined:
                    matrix_skills.append(child.name)

    return {"skill": matrix_skills}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root.resolve())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
