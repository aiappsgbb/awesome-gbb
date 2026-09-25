"""Exact hosted fixture ownership and cleanup; no shared repository deletion."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def acr(registry, args):
    result = subprocess.run(
        ["az", "acr", *args, "--name", registry, "--output", "json", "--only-show-errors"],
        capture_output=True, text=True, timeout=45,
    )
    require(result.returncode == 0, "ACR operation failed; cleanup remains unverified")
    return json.loads(result.stdout) if result.stdout.strip() else None


def image_binding(definition, registry, agent):
    image = definition["container_configuration"]["image"]
    require(isinstance(image, str) and image.startswith(registry + "/"), "Image registry mismatch")
    reference = image[len(registry) + 1:]
    repository = reference.split("@", 1)[0].split(":", 1)[0]
    require(repository == agent or repository.startswith(agent + "/"), "Image is outside the run namespace")
    return reference, repository


def version_fingerprint(version):
    return hashlib.sha256(json.dumps(
        {k: version[k] for k in ("name", "version", "created_at", "definition")},
        sort_keys=True, default=str,
    ).encode()).hexdigest()


def get_version(client, name):
    try:
        return client.agents.get_version(agent_name=name, agent_version="1").as_dict()
    except ResourceNotFoundError:
        return None


def prepare(client, path, name, registry, endpoint):
    require(re.fullmatch(r"ci-smoke-ha-[0-9a-f]{8}", name), "Invalid fixture agent name")
    require(re.fullmatch(r"[a-z0-9]+\.azurecr\.io", registry), "Invalid registry hostname")
    url = urlsplit(endpoint)
    require(url.scheme == "https" and url.hostname and not url.query and not url.fragment
            and not url.username and re.fullmatch(r"/api/projects/[A-Za-z0-9_-]+", url.path), "Invalid project endpoint")
    try:
        client.agents.get(agent_name=name)
    except ResourceNotFoundError:
        pass
    else:
        raise ValueError("Agent already exists; never adopt an existing fixture name")
    repos = acr(registry.split(".")[0], ["repository", "list"])
    require(isinstance(repos, list) and not any(r == name or r.startswith(name + "/") for r in repos),
            "Run image namespace already exists")
    write_new(path, {"name": name, "registry": registry, "endpoint": endpoint, "absent_at": int(time.time())})


def record(client, path, owner):
    version = get_version(client, owner["name"])
    require(version is not None and version["name"] == owner["name"] and version["version"] == "1", "Version binding mismatch")
    require(float(version["created_at"]) >= owner["absent_at"], "Native creation predates run")
    reference, repository = image_binding(version["definition"], owner["registry"], owner["name"])
    metadata = acr(owner["registry"].split(".")[0], ["repository", "show", "--image", reference])
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", metadata.get("digest", "")), "Registry manifest digest missing")
    write_new(path, {"version_fingerprint": version_fingerprint(version), "reference": reference,
                     "repository": repository, "digest": metadata["digest"]})


def cleanup(client, owner, created):
    version = get_version(client, owner["name"])
    if version is not None:
        require(version_fingerprint(version) == created["version_fingerprint"], "Version changed; do not delete")
        reference, repository = image_binding(version["definition"], owner["registry"], owner["name"])
        require(reference == created["reference"] and repository == created["repository"], "Image binding changed")
        client.agents.delete_version(agent_name=owner["name"], agent_version="1")
        for _ in range(12):
            if get_version(client, owner["name"]) is None:
                break
            time.sleep(5)
        else:
            raise RuntimeError("Version deletion not verified")
    # The original namespace was absent before this run; preserve any added version.
    try:
        versions = list(client.agents.list_versions(agent_name=owner["name"]))
    except ResourceNotFoundError:
        versions = []
    require(not versions, "Additional versions exist; preserve agent and image")
    try:
        client.agents.get(agent_name=owner["name"])
    except ResourceNotFoundError:
        pass
    else:
        client.agents.delete(agent_name=owner["name"])
        try:
            client.agents.get(agent_name=owner["name"])
        except ResourceNotFoundError:
            pass
        else:
            raise RuntimeError("Agent deletion not verified")
    registry = owner["registry"].split(".")[0]
    repos = acr(registry, ["repository", "list"])
    if created["repository"] in repos:
        manifests = acr(registry, ["repository", "show-manifests", "--repository", created["repository"]])
        require(len(manifests) == 1 and manifests[0]["digest"] == created["digest"], "Image namespace changed; preserve it")
        acr(registry, ["repository", "delete", "--image", created["repository"] + "@" + created["digest"], "--yes"])
        require(created["repository"] not in acr(registry, ["repository", "list"]), "Image deletion not verified")
    print("HOSTED_CLEANUP=VERIFIED exact-version-agent-image")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "record", "cleanup"))
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--agent")
    args = parser.parse_args()
    endpoint, registry = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/"), os.environ["ACR_LOGIN_SERVER"]
    with AzureCliCredential(process_timeout=30) as credential, AIProjectClient(
        endpoint=endpoint, credential=credential, retry_total=0, connection_timeout=10, read_timeout=30,
    ) as client:
        if args.action == "prepare":
            prepare(client, args.state, args.agent, registry, endpoint)
        else:
            owner = json.loads(args.state.read_text())
            require(owner["endpoint"] == endpoint and owner["registry"] == registry, "Target drift")
            created_path = args.state.with_suffix(".created.json")
            if args.action == "record":
                record(client, created_path, owner)
            else:
                cleanup(client, owner, json.loads(created_path.read_text()))
