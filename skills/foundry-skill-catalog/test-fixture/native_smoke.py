"""Canonical native Skills lifecycle and deterministic result writer."""

import io
import os
from pathlib import Path
import sys
import uuid
import zipfile

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import CreateSkillVersionFromFilesBody, SkillInlineContent
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "references"))
from skill_packages import download_catalog, skill_archive


def absent(read, *args):
    try:
        read(*args)
    except ResourceNotFoundError:
        return
    raise RuntimeError("Owned resource remains present")


def check_package(project, name, selected, expected, sentinel, asset=None):
    packages = download_catalog(project, {name: selected})
    if len(packages) != 1:
        raise ValueError("Expected one owned package")
    package = packages[0]
    if package.name != name or package.version != expected or package.content is None:
        raise ValueError("Package identity/content mismatch")
    body, files = skill_archive(package.content)
    if sentinel not in body:
        raise ValueError("Package sentinel mismatch")
    if asset is not None and files.get("assets/note.txt") != asset:
        raise ValueError("Package asset mismatch")


def smoke(project, name):
    skills = project.beta.skills
    absent(skills.get, name)
    created = False
    primary_error = None
    try:
        one = skills.create(
            name=name, default=True,
            inline_content=SkillInlineContent(description="Synthetic greeting", instructions="version-one"),
        )
        created = True
        print(f"SKILL_CREATED name={name} version={one.version}", flush=True)
        two = skills.create(
            name=name, default=False,
            inline_content=SkillInlineContent(description="Synthetic greeting", instructions="version-two"),
        )
        if skills.get(name).default_version != one.version:
            raise ValueError("Unpromoted version changed default")
        if not {one.version, two.version} <= {v.version for v in skills.list_versions(name)}:
            raise ValueError("Owned versions missing")
        check_package(project, name, one.version, one.version, "version-one")
        skills.update(name, default_version=two.version)
        if skills.get(name).default_version != two.version:
            raise ValueError("Promotion not observed")
        check_package(project, name, None, two.version, "version-two")
        check_package(project, name, one.version, one.version, "version-one")
        skills.update(name, default_version=one.version)
        check_package(project, name, None, one.version, "version-one")
        asset = b"synthetic asset\n"
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("SKILL.md", f"---\nname: {name}\ndescription: Synthetic greeting\n---\nversion-zip\n")
            package.writestr("assets/note.txt", asset)
        three = skills.create_from_files(
            name, content=CreateSkillVersionFromFilesBody(files=[("skill.zip", archive.getvalue())], default=False),
        )
        check_package(project, name, three.version, three.version, "version-zip", asset)
        if skills.get(name).default_version != one.version:
            raise ValueError("ZIP append changed default")
        deleted = skills.delete_version(name, two.version)
        if deleted.deleted is not True:
            raise RuntimeError("Version deletion not acknowledged")
        absent(skills.get_version, name, two.version)
        print("NATIVE_CONTENT_CHECKS_VERIFIED", flush=True)
    except Exception as error:
        primary_error = error
        raise
    finally:
        if created:
            try:
                deleted = skills.delete(name)
                if deleted.deleted is not True:
                    raise RuntimeError("Parent deletion not acknowledged")
                absent(skills.get, name)
                print(f"SKILL_PARENT_ABSENT_VERIFIED name={name}", flush=True)
            except Exception as cleanup_error:
                print(f"SKILL_CLEANUP_UNVERIFIED name={name} error_type={type(cleanup_error).__name__}", flush=True)
                if primary_error is None:
                    raise


def main():
    marker = Path("/tmp/foundry-skill-catalog-smoke-result")
    marker.write_text("SMOKE_RESULT=FAIL execution incomplete\n", encoding="utf-8")
    name = f"ci-smoke-skill-{uuid.uuid4().hex[:8]}"
    print(f"OWNED_SKILL_INTENT name={name}", flush=True)
    try:
        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                            credential=credential, allow_preview=True) as project,
        ):
            smoke(project, name)
    except Exception as error:
        marker.write_text(f"SMOKE_RESULT=FAIL native lifecycle {type(error).__name__}\n", encoding="utf-8")
        print(f"NATIVE_SKILL_FAILED error_type={type(error).__name__}", flush=True)
        return 1
    marker.write_text("SMOKE_RESULT=PASS\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
