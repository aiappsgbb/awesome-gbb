"""Private run inventory and exact cleanup for the producer fixture."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cli(args, absent=False):
    result = subprocess.run(
        ["az", *args, "--output", "json", "--only-show-errors"],
        capture_output=True, text=True, timeout=45,
    )
    if result.returncode:
        if absent and re.search(r"\(ResourceNotFound\)|\b(MANIFEST_UNKNOWN|NAME_UNKNOWN)\b", result.stderr):
            return None
        raw = Path(os.environ["PROJECT_DIR"]) / f"azure-error-{uuid.uuid4().hex}.json"
        write_new(raw, {"exit": result.returncode, "stderr": result.stderr, "stdout": result.stdout})
        raise RuntimeError("Azure operation failed; private evidence retained, absence/cleanup not proven")
    return json.loads(result.stdout) if result.stdout.strip() else None


def write_new(path, data):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def app_read(config):
    return cli(["rest", "--method", "get", "--url", config["url"]], absent=True)


def image_read(config):
    return cli(["acr", "manifest", "show-metadata", "--registry", config["registry"],
                "--name", config["name"] + ":run"], absent=True)


def inventory(project):
    config = json.loads((project / "run-owned.json").read_text())
    require(re.fullmatch(r"ci-smoke-mcp-[0-9a-f]{8}", config["name"]), "Invalid owned app name")
    group = config["identity"].split("/providers/")[0]
    require(re.fullmatch(r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[^/]+", group),
            "Invalid owned resource scope")
    require(config["id"] == group + "/providers/Microsoft.App/containerApps/" + config["name"],
            "Cleanup cannot target shared resource types")
    require(config["url"] == "https://management.azure.com" + config["id"] + "?api-version=2025-01-01",
            "Cleanup URL changed")
    require(re.fullmatch(r"[a-z0-9]+", config["registry"]), "Invalid registry name")
    return config


def prepare(project, environ):
    name, identity = environ["APP_NAME"], environ["UAMI_RESOURCE_ID"]
    require(re.fullmatch(r"ci-smoke-mcp-[0-9a-f]{8}", name), "Run name is not UUID-scoped")
    subscription = environ["AZURE_SUBSCRIPTION_ID"]
    group = identity.split("/providers/")[0]
    require(group.lower().startswith(f"/subscriptions/{subscription}/resourcegroups/".lower()), "Wrong identity scope")
    require(re.fullmatch(r"[a-z0-9]+\.azurecr\.io", environ["ACR_SERVER"]), "Invalid registry")
    account = cli(["account", "show"])
    require(account["id"].lower() == subscription.lower()
            and account["tenantId"].lower() == environ["AZURE_TENANT_ID"].lower(), "Active context mismatch")
    resource_id = group + "/providers/Microsoft.App/containerApps/" + name
    config = {"name": name, "id": resource_id, "identity": identity,
              "url": "https://management.azure.com" + resource_id + "?api-version=2025-01-01",
              "registry": environ["ACR_SERVER"].split(".")[0]}
    require(app_read(config) is None, "App already exists")
    repositories = cli(["acr", "repository", "list", "--name", config["registry"]])
    require(isinstance(repositories, list) and name not in repositories, "Image repository already exists")
    config["absent_at"] = datetime.now(timezone.utc).isoformat()
    write_new(project / "run-owned.json", config)
    manifest = project / "azure.yaml"
    text = manifest.read_text()
    anchor = "      context: .\n"
    require(text.count(anchor) == 1, "Unexpected canonical service shape")
    manifest.write_text(text.replace(anchor, anchor +
        f"      registry: {environ['ACR_SERVER']}\n      image: {name}\n      tag: run\n"))


def record(project):
    config = inventory(project)
    app, image = app_read(config), image_read(config)
    if app is not None:
        require(app["id"].lower() == config["id"].lower(), "App target changed")
        stamp = app.get("systemData", {}).get("createdAt")
        require(isinstance(stamp, str) and datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                >= datetime.fromisoformat(config["absent_at"]), "App creation ownership not proven")
        require(config["identity"] in app.get("identity", {}).get("userAssignedIdentities", {})
                and app.get("tags", {}).get("ci-run-id") == config["name"], "App ownership bindings differ")
    if image is not None:
        require(image.get("tags") == ["run"] and re.fullmatch(r"sha256:[0-9a-f]{64}", image.get("digest", "")),
                "Image ownership differs")
    write_new(project / "run-created.json", {"app": app, "image": image})


def cleanup(project):
    config = inventory(project)
    created = json.loads((project / "run-created.json").read_text())
    current = app_read(config)
    if current is not None:
        require(created["app"] is not None and current.get("systemData") == created["app"].get("systemData")
                and current.get("tags") == created["app"].get("tags")
                and current.get("identity") == created["app"].get("identity"), "App changed; cleanup blocked")
        cli(["rest", "--method", "delete", "--url", config["url"]])
        for _ in range(12):
            if app_read(config) is None:
                break
            time.sleep(5)
        else:
            raise RuntimeError("App deletion unverified")
    image = image_read(config)
    if image is not None:
        require(created["image"] is not None and image.get("digest") == created["image"].get("digest")
                and image.get("tags") == ["run"], "Image changed; cleanup blocked")
        cli(["acr", "repository", "delete", "--name", config["registry"],
             "--image", config["name"] + "@" + image["digest"], "--yes"])
        require(image_read(config) is None, "Image deletion unverified")
    print("PRODUCER_CLEANUP=VERIFIED app-and-image-only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "record", "cleanup"))
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.project, os.environ)
    elif args.action == "record":
        record(args.project)
    else:
        cleanup(args.project)
