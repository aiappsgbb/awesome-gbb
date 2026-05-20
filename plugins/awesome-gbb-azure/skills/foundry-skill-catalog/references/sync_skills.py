"""sync_skills.py — azd predeploy hook that bundles Foundry skills into the
agent image at build time (Pattern A from foundry-skill-catalog).

Run this from azure.yaml:

    hooks:
      predeploy:
        windows:
          shell: pwsh
          run: uv run python scripts/sync_skills.py
        posix:
          shell: sh
          run: uv run python scripts/sync_skills.py

Skips JSON-mode skills (their body is not retrievable from the API — see
the foundry-skill-catalog skill for the documented write-only trap).

Required env:
- FOUNDRY_PROJECT_ENDPOINT (e.g. https://<account>.services.ai.azure.com/api/projects/<project>)
- AZURE_CONFIG_DIR set per-tenant (see azure-tenant-isolation)
"""

from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient


def main() -> int:
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    target = Path(__file__).resolve().parent.parent / "src" / "skills"
    target.mkdir(parents=True, exist_ok=True)

    with (
        DefaultAzureCredential() as cred,
        AIProjectClient(endpoint=endpoint, credential=cred, allow_preview=True) as project,
    ):
        skills = list(project.beta.skills.list())
        if not skills:
            print(f"[sync_skills] no skills published in {endpoint}; nothing to bundle.")
            return 0

        zipped = 0
        skipped_json = 0
        for s in skills:
            if not s.has_blob:
                print(
                    f"[sync_skills] skip JSON-mode skill {s.name!r} "
                    f"(body unretrievable; re-import as ZIP)"
                )
                skipped_json += 1
                continue
            zip_bytes = b"".join(project.beta.skills.download(s.name))
            skill_dir = target / s.name
            skill_dir.mkdir(parents=True, exist_ok=True)
            # Wipe any prior contents so deletions in Foundry are reflected
            for p in skill_dir.rglob("*"):
                if p.is_file():
                    p.unlink()
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                z.extractall(skill_dir)
            print(f"[sync_skills] unpacked {s.name!r} → {skill_dir}")
            zipped += 1

        print(
            f"[sync_skills] done: {zipped} bundled, {skipped_json} skipped, "
            f"target={target}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
