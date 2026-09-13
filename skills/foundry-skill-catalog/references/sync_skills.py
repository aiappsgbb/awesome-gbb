"""Canonical version-aware azd predeploy skill bundler.

Source of truth for `../SKILL.md § Pattern A — Build-time bundle (the GHCP-SDK approach)`.

Run this from azure.yaml:

    hooks:
      predeploy:
        windows:
          shell: pwsh
          run: uv run python scripts/sync_skills.py
        posix:
          shell: sh
          run: uv run python scripts/sync_skills.py

Copy skill_packages.py alongside this file; MAF is not required. Native inline and ZIP
versions both have downloadable content. Only explicitly legacy has_blob=False
skills are skipped, with a warning. Errors never become successful fallbacks.

Required env:
- FOUNDRY_PROJECT_ENDPOINT (e.g. https://<account>.services.ai.azure.com/api/projects/<project>)
- AZURE_CONFIG_DIR set per-tenant (see azure-tenant-isolation)

Optional env:
- FOUNDRY_SKILL_VERSIONS: JSON object mapping selected names to numeric version
  strings or null (follow default). Omitted loads all; {} requires an empty
  skill target. Explicit selection rejects unselected directories before writes.
- FOUNDRY_SKILLS_TARGET: dedicated output directory; defaults to src/skills.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from skill_packages import download_catalog, skill_archive, validate_selection


def selection_from_env(raw: str | None):
    if raw is None:
        return None
    selection = json.loads(raw)
    if not isinstance(selection, dict):
        raise ValueError("FOUNDRY_SKILL_VERSIONS must be a JSON object")
    validate_selection(selection)
    return selection


def bundle_skills(project, target: Path, skill_versions=None) -> dict[str, int]:
    validate_selection(skill_versions)
    if skill_versions is not None and target.exists():
        unexpected = [
            entry.name for entry in target.iterdir()
            if entry.name == "SKILL.md"
            or ((entry.is_dir() or entry.is_symlink()) and entry.name not in skill_versions)
        ]
        if unexpected:
            raise ValueError("Explicit selection has unselected entries; use a clean target directory")
    packages = download_catalog(project, skill_versions)
    prepared = []
    skipped = 0
    for package in packages:
        validate_selection({package.name: None})
        if package.content is None:
            if (target / package.name).exists():
                raise ValueError("Legacy skip would retain stale instructions; use a clean target directory")
            skipped += 1
            continue
        _, files = skill_archive(package.content)
        destination = target / package.name
        if destination.is_symlink():
            raise ValueError("Refusing to replace a symlinked skill directory")
        prepared.append((destination, files))
    for destination, files in prepared:
        if destination.exists():
            shutil.rmtree(destination)
        for relative, content in files.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return {"bundled": len(prepared), "skipped_legacy": skipped}


def main() -> int:
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient

    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    default_target = Path(__file__).resolve().parent.parent / "src" / "skills"
    target = Path(os.environ.get("FOUNDRY_SKILLS_TARGET", default_target))
    selection = selection_from_env(os.environ.get("FOUNDRY_SKILL_VERSIONS"))
    with (
        DefaultAzureCredential() as cred,
        AIProjectClient(endpoint=endpoint, credential=cred, allow_preview=True) as project,
    ):
        result = bundle_skills(project, target, selection)
    print(f"[sync_skills] bundled={result['bundled']} skipped_legacy={result['skipped_legacy']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
