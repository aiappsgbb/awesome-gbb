"""Canonical lightweight skill package reader.

Source of truth for `../SKILL.md § Pattern A — Build-time bundle (the GHCP-SDK approach)`.

Uses only the standard library and an already-constructed, duck-typed project
client. Build-only consumers do not need Microsoft Agent Framework.
"""

from __future__ import annotations

import io
import re
import stat
import warnings
import zipfile
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import NamedTuple


class SkillPackage(NamedTuple):
    name: str
    description: str
    version: str | None
    content: bytes | None


def validate_selection(skill_versions: Mapping[str, str | None] | None) -> None:
    if skill_versions is None:
        return
    if not isinstance(skill_versions, Mapping):
        raise ValueError("skill_versions must map skill names to numeric version strings or None")
    for name, version in skill_versions.items():
        if not isinstance(name, str) or not name or "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError("Invalid skill name")
        if version is not None:
            _validate_version(version)


def _validate_version(version: str) -> None:
    if not isinstance(version, str) or not re.fullmatch(r"[1-9][0-9]*", version):
        raise ValueError("A native version must be a positive numeric string")


def skill_archive(content: bytes) -> tuple[str, dict[str, bytes]]:
    """Validate a package and return its SKILL.md and safe, root-relative files."""
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        files = {}
        for item in package.infolist():
            path = PurePosixPath(item.filename)
            if (
                path.is_absolute() or ".." in path.parts or "\\" in item.filename
                or ":" in item.filename or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise ValueError("Unsafe skill archive path")
            if item.is_dir():
                continue
            if str(path) in files:
                raise ValueError("Duplicate skill archive path")
            files[str(path)] = package.read(item)
    roots = [name for name in files if PurePosixPath(name).name == "SKILL.md"]
    if len(roots) != 1:
        raise ValueError("Skill archive must contain exactly one SKILL.md")
    root = PurePosixPath(roots[0]).parent
    if len(root.parts) > 1 or any(not PurePosixPath(name).is_relative_to(root) for name in files):
        raise ValueError("Skill archive files must share the SKILL.md root path")
    return files[roots[0]].decode("utf-8"), {
        str(PurePosixPath(name).relative_to(root)): data for name, data in files.items()
    }


def download_catalog(project, skill_versions: Mapping[str, str | None] | None = None) -> list[SkillPackage]:
    """Read selected snapshots; an empty mapping intentionally loads nothing."""
    validate_selection(skill_versions)
    operations = project.beta.skills
    summaries = (
        operations.list() if skill_versions is None
        else (operations.get(name) for name in skill_versions)
    )
    packages = []
    missing = object()
    for summary in summaries:
        requested = None if skill_versions is None else skill_versions[summary.name]
        default = getattr(summary, "default_version", missing)
        if default is not missing:
            version = requested if requested is not None else default
            if requested is None and not default:
                raise ValueError("Skill metadata has no default_version; select or promote a version")
            _validate_version(version)
            if not callable(getattr(operations, "download_version", None)):
                raise ValueError("Native skill metadata requires an SDK with download_version")
            metadata = operations.get_version(summary.name, version)
            if metadata.name != summary.name or metadata.version != version:
                raise ValueError("Skill version metadata does not match the requested snapshot")
            content = b"".join(operations.download_version(summary.name, version))
            description = metadata.description or ""
        elif isinstance(getattr(summary, "has_blob", None), bool):
            if requested is not None:
                raise ValueError("Cannot apply a native version pin to legacy skill metadata")
            version = None
            description = summary.description or ""
            if summary.has_blob:
                content = b"".join(operations.download(summary.name))
            else:
                warnings.warn(
                    f"legacy JSON skill {summary.name!r} has no readable package; returning a placeholder",
                    RuntimeWarning,
                    stacklevel=2,
                )
                content = None
        else:
            raise ValueError("Unrecognized skill metadata: expected default_version or legacy has_blob")
        if content is not None:
            skill_archive(content)
        packages.append(SkillPackage(summary.name, description, version, content))
    return packages
