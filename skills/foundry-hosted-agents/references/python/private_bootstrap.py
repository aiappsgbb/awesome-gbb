"""Canonical offline staging and artifact inventory for a private BASIC consumer.

Source of truth for `../../SKILL.md § Private BASIC consumer`.
No logins, build commands, subprocesses or Azure calls. See ../private-basic.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

import yaml

from deploy_preflight import immutable_image, unique_keys

REFS = Path(__file__).resolve().parents[1]
BUILD_FILES = ("main.py", "pyproject.toml", "uv.lock", "Dockerfile")


def prepare(destination: Path, agent_name: str, build: str, image: str | None = None) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", agent_name):
        raise ValueError("Use a unique lowercase agent name, 3-63 characters")
    if build not in {"local", "remote", "prebuilt"}:
        raise ValueError("Select local, remote or prebuilt container build, never preview code mode")
    if (build == "prebuilt" and not immutable_image(image)) or (build != "prebuilt" and image is not None):
        raise ValueError("Only prebuilt mode accepts (and requires) an immutable image digest")
    config = yaml.safe_load((REFS / "yaml/azure.yaml").read_text())
    agent = config["services"].pop("my-agent")
    agent.update(name=agent_name, project="app", description="No-tools BASIC model bootstrap")
    agent["docker"] = {"remoteBuild": build == "remote", "imagePassthrough": build == "prebuilt"}
    if build == "prebuilt":
        agent["image"] = image
    else:
        agent["docker"].update(
            path="Dockerfile", context=".", platform="linux/amd64",
            buildArgs=["PYTHON_IMAGE=${PYTHON_IMAGE}", "UV_IMAGE=${UV_IMAGE}"],
        )
    config["name"] = agent_name
    config["services"][agent_name] = agent
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    app = destination / "app"
    app.mkdir()
    for source, name in (
        (REFS / "python/basic.py", "main.py"),
        (REFS / "python/pyproject.toml", "pyproject.toml"),
        (REFS / "docker/Dockerfile.basic", "Dockerfile"),
        (REFS / "docker/basic.dockerignore", ".dockerignore"),
        (REFS / "docker/basic.dockerignore", ".azdignore"),
    ):
        shutil.copyfile(source, app / name)
    (destination / "azure.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def source_inventory(directory: Path) -> dict:
    """Hash the exact allowlisted context, not files in the operator directory."""
    app = directory / "app"
    if app.is_symlink():
        raise ValueError("Build context must not be a symlink")
    exclusions = (REFS / "docker/basic.dockerignore").read_bytes()
    for name in (".dockerignore", ".azdignore"):
        if (app / name).is_symlink() or (app / name).read_bytes() != exclusions:
            raise ValueError("Build/upload exclusions differ from the canonical allowlist")
    # Dockerfile-specific ignore files override the default ignore file.
    if any(path.name != ".dockerignore" for path in app.glob("*.dockerignore")):
        raise ValueError("Dockerfile-specific exclusions can override the allowlist")
    result = {}
    for name in BUILD_FILES:
        path = app / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or symlinked build input: {name}")
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def validate_build(directory: Path, agent_name: str) -> dict:
    """Check the rendered container route and effective base references locally."""
    config = yaml.safe_load((directory / "azure.yaml").read_text())
    service = config["services"][agent_name]
    if service.get("language") != "docker" or "codeConfiguration" in service or service.get("project") != "app":
        raise ValueError("Require the explicit app/ container route")
    docker = service.get("docker", {})
    if docker.get("imagePassthrough") is True:
        if docker.get("remoteBuild") is not False or not immutable_image(service.get("image")):
            raise ValueError("Prebuilt requires service image digest and remoteBuild:false")
        if "image" in docker:
            raise ValueError("docker.image is an ordinary publisher input, not passthrough")
        return {"path": "prebuilt", "image": service["image"]}
    if "image" in service or docker.get("remoteBuild") not in (True, False):
        raise ValueError("Select an explicit source build path")
    if docker.get("context") != "." or docker.get("path") != "Dockerfile" or docker.get("platform") != "linux/amd64":
        raise ValueError("Source build context/platform changed")
    bases = {key: os.environ.get(key) for key in ("PYTHON_IMAGE", "UV_IMAGE")}
    if not all(immutable_image(value) for value in bases.values()):
        raise ValueError("PYTHON_IMAGE and UV_IMAGE must be immutable, approved base references")
    if docker.get("buildArgs") != ["PYTHON_IMAGE=${PYTHON_IMAGE}", "UV_IMAGE=${UV_IMAGE}"]:
        raise ValueError("Source build arguments must consume the approved base references")
    return {"path": "remote" if docker["remoteBuild"] else "local",
            "base_images": bases, "context": source_inventory(directory)}


def manifest_inventory(raw: bytes, digest: str) -> dict:
    """Verify original registry bytes; retain format, config and layer descriptors."""
    if digest != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError("Registry manifest bytes do not match the selected image digest")
    manifest = json.loads(raw, object_pairs_hook=unique_keys)
    if (not isinstance(manifest, dict) or manifest.get("schemaVersion") != 2
            or not isinstance(manifest.get("mediaType"), str)
            or not isinstance(manifest.get("config"), dict)
            or not isinstance(manifest.get("layers"), list) or not manifest["layers"]):
        raise ValueError("Require the resolved platform manifest, not an unresolved image index")
    for descriptor in [manifest["config"], *manifest["layers"]]:
        if (not isinstance(descriptor, dict)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(descriptor.get("digest", "")))
                or type(descriptor.get("size")) is not int or descriptor["size"] < 0
                or not isinstance(descriptor.get("mediaType"), str)):
            raise ValueError("Incomplete manifest config/layer descriptor")
    return {key: manifest[key] for key in ("mediaType", "config", "layers")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("directory", type=Path)
    prepare_parser.add_argument("--agent", required=True)
    prepare_parser.add_argument("--build", choices=("local", "remote", "prebuilt"), required=True)
    prepare_parser.add_argument("--image")
    inventory_parser = sub.add_parser("inventory")
    inventory_parser.add_argument("directory", type=Path)
    build_parser = sub.add_parser("check-build")
    build_parser.add_argument("directory", type=Path)
    build_parser.add_argument("--agent", required=True)
    manifest_parser = sub.add_parser("manifest")
    manifest_parser.add_argument("file", type=Path)
    manifest_parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.directory, args.agent, args.build, args.image)
            result = {"status": "STAGED_NOT_DEPLOYED"}
        elif args.command == "inventory":
            result = source_inventory(args.directory)
        elif args.command == "check-build":
            result = validate_build(args.directory, args.agent)
        else:
            result = manifest_inventory(args.file.read_bytes(), args.digest)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        # File paths may identify private operator directories; keep CLI failure bounded.
        print(json.dumps({"status": "BLOCKED", "stage": args.command, "error_type": type(error).__name__,
                          "reason": str(error) if type(error) is ValueError else "Check the required inputs and paths"}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
