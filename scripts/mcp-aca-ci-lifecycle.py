#!/usr/bin/env python3
"""Exact Container App lifecycle for the MCP ACA fixture, not a general janitor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


API = "2024-03-01"
DEPLOY_API = "2022-09-01"
LOCK_API = "2016-09-01"
MAX_BYTES = 4 * 1024 * 1024
MAX_LIST_PAGES = 100
MAX_LIST_ITEMS = 10000
MAX_LIST_BYTES = 32 * 1024 * 1024
LIST_SECONDS = 120
DEPLOY_SECONDS = 1200
CAPTURE_SECONDS = 300
FINALIZER_SECONDS = 300
MIN_DELETE_SECONDS = 120
ARM_ORIGIN = "https://management.azure.com"
SKILL = "foundry-mcp-aca"
APP_PROVIDER = "/providers/Microsoft.App/containerApps/"
DEPLOY_PROVIDER = "/providers/Microsoft.Resources/deployments"
LOCK_PROVIDER = "/providers/Microsoft.Authorization/locks"
GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class LifecycleError(Exception):
    """Only finite codes cross the public output boundary."""


def require(condition, code):
    if not condition:
        raise LifecycleError(code)


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "JSON")
            result[key] = value
        return result
    def constant(_):
        raise LifecycleError("JSON")
    try:
        require(len(raw) <= MAX_BYTES, "SIZE")
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise LifecycleError("JSON") from None


def utc(value):
    require(isinstance(value, str), "DATE")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise LifecycleError("DATE") from None
    require(parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value, "DATE")
    return parsed


def utc_now():
    return datetime.now(timezone.utc)


def require_lifetime(approved, seconds):
    # Recheck the frozen record, never reload a potentially renewed approval.
    require(utc(approved["expires_at"]) - utc_now() >= timedelta(seconds=seconds), "APPROVAL_LIFETIME")


def approval(env, now, raw=None):
    record = parse(env.get("MCP_ACA_CI_LIFECYCLE_APPROVAL_JSON", "") if raw is None else raw)
    require(isinstance(record, dict) and set(record) == {
        "schema_version", "repository", "sha", "run_id", "run_attempt", "expires_at",
        "resource_group_id", "environment_id", "identity_id", "acr_server",
        "tenant_id", "client_id", "age_recipient", "image_retain_until",
        "owner", "purpose", "delete_exact_created_app", "retain_images",
    }, "APPROVAL")
    require(type(record["schema_version"]) is int and record["schema_version"] == 1, "APPROVAL")
    for key in ("delete_exact_created_app", "retain_images"):
        require(record[key] is True, "APPROVAL")
    for key in ("owner", "purpose"):
        require(isinstance(record[key], str) and bool(record[key].strip()), "APPROVAL")
    for key, name in (("repository", "GITHUB_REPOSITORY"), ("sha", "GITHUB_SHA"),
                      ("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT"),
                      ("tenant_id", "AZURE_TENANT_ID"), ("client_id", "AZURE_CLIENT_ID"),
                      ("acr_server", "ACR_LOGIN_SERVER")):
        require(type(record[key]) is str and record[key] == env.get(name) and bool(record[key]), "CONTEXT")
    require(re.fullmatch(r"[0-9a-f]{40}", record["sha"]), "CONTEXT")
    require(all(re.fullmatch(r"[1-9][0-9]*", record[key]) for key in ("run_id", "run_attempt")), "CONTEXT")
    expiry, retention = utc(record["expires_at"]), utc(record["image_retain_until"])
    require(now < expiry <= now + timedelta(hours=24) and
            expiry <= retention <= now + timedelta(days=7), "EXPIRED")
    subscription = env.get("AZURE_SUBSCRIPTION_ID", "")
    require(re.fullmatch(GUID, subscription), "SCOPE")
    group = record["resource_group_id"]
    require(isinstance(group, str) and re.fullmatch(
        rf"/subscriptions/{subscription}/resourceGroups/[A-Za-z0-9_.()-]+", group), "SCOPE")
    require(record["environment_id"] == group + "/providers/Microsoft.App/managedEnvironments/cae-awesome-gbb-ci",
            "SCOPE")
    require(isinstance(record["identity_id"], str) and re.fullmatch(
        re.escape(group) + r"/providers/Microsoft.ManagedIdentity/userAssignedIdentities/[A-Za-z0-9_-]+",
        record["identity_id"]), "SCOPE")
    require(re.fullmatch(r"[a-z0-9]+\.azurecr\.io", record["acr_server"]), "SCOPE")
    require(re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", record["age_recipient"]), "CUSTODY")
    return record


def root(env):
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]*", env.get(key, "")), "CONTEXT")
    base = Path(env["RUNNER_TEMP"])
    require(base.is_absolute() and base.resolve() == base, "PATH")
    path = base / f"mcp-aca-lifecycle-{env['GITHUB_RUN_ID']}-{env['GITHUB_RUN_ATTEMPT']}"
    require(not path.is_symlink(), "PATH")
    return path


def private_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                stat.S_IMODE(info.st_mode) == 0o600, "PATH")
        return stream.read(MAX_BYTES + 1)


def write(path, document):
    raw = json.dumps(document, sort_keys=True).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                stat.S_IMODE(info.st_mode) == 0o600, "PATH")
        os.ftruncate(stream.fileno(), 0)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LifecycleError("REDIRECT")


class Arm:
    def __init__(self, env):
        self.env = env
        result = subprocess.run(["az", "account", "show", "-o", "json"], env=env,
                                capture_output=True, timeout=20, check=False)
        require(result.returncode == 0, "CREDENTIAL")
        account = parse(result.stdout)
        require(account.get("id") == env["AZURE_SUBSCRIPTION_ID"] and
                account.get("tenantId") == env["AZURE_TENANT_ID"] and
                account.get("user", {}).get("type") == "servicePrincipal" and
                account.get("user", {}).get("name") == env["AZURE_CLIENT_ID"], "CREDENTIAL")

    def __call__(self, method, resource_id, api, etag=None, *, next_link=None, before_send=None, role_principal=None):
        require(method in ("GET", "DELETE", "PUT") and resource_id.startswith("/subscriptions/"), "REQUEST")
        require(method == "GET" or callable(before_send), "MUTATION_GUARD")
        require(next_link is None or method == "GET", "REQUEST")
        body = None
        if method == "PUT":
            # Only the existing CI delegation: exact Foundry User assignment,
            # never a generic ARM body or an arbitrary role.
            project = self.env.get("AZURE_AI_PROJECT_ID", "")
            require(project and resource_id.rsplit("/providers/", 1)[0] in (
                project, project.rsplit("/projects/", 1)[0]), "REQUEST")
            require(api == "2022-04-01" and isinstance(role_principal, str) and
                    re.fullmatch(GUID, role_principal) and re.fullmatch(
                        rf"/subscriptions/{self.env['AZURE_SUBSCRIPTION_ID']}/resourceGroups/[A-Za-z0-9_.()-]+"
                        r"/providers/Microsoft.CognitiveServices/accounts/[a-zA-Z0-9-]+"
                        r"(?:/projects/[a-zA-Z0-9_-]+)?/providers/Microsoft.Authorization/roleAssignments/" + GUID,
                        resource_id), "REQUEST")
            body = json.dumps({"properties": {
                "principalId": role_principal, "principalType": "ServicePrincipal",
                "roleDefinitionId": "/subscriptions/" + self.env["AZURE_SUBSCRIPTION_ID"] +
                "/providers/Microsoft.Authorization/roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d",
            }}).encode()
        else:
            require(role_principal is None, "REQUEST")
        url = (ARM_ORIGIN + resource_id + "?api-version=" + api if next_link is None else
               continuation_url(next_link, resource_id, api))
        token = subprocess.run(
            ["az", "account", "get-access-token", "--resource", "https://management.azure.com/",
             "--subscription", self.env["AZURE_SUBSCRIPTION_ID"], "--query", "accessToken", "-o", "tsv"],
            env=self.env, capture_output=True, timeout=20, check=False,
        )
        require(token.returncode == 0 and token.stdout.strip(), "CREDENTIAL")
        headers = {"Authorization": "Bearer " + token.stdout.decode("ascii").strip(),
                   "Accept": "application/json"}
        if etag:
            headers["If-Match"] = etag
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(url, headers=headers, method=method, data=body)
        try:
            opener = build_opener(ProxyHandler({}), NoRedirect())
            # Token acquisition and request setup may consume the approval window.
            if before_send is not None:
                before_send()
            try:
                response = opener.open(req, timeout=20)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(MAX_BYTES + 1)
                data = parse(raw) if raw else {}
                return response.code, data, response.headers.get("ETag")
        except (URLError, OSError, HTTPException):
            raise LifecycleError("NETWORK") from None


def absent(status, body):
    # Not a failed lookup, missing marker, status string or generic CLI failure.
    return (status == 404 and isinstance(body, dict) and isinstance(body.get("error"), dict) and
            body["error"].get("code") in ("ResourceNotFound", "ContainerAppNotFound"))


def continuation_url(value, resource_id, api):
    require(isinstance(value, str) and len(value) <= 16384 and
            not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) and
            "\\" not in value and "#" not in value, "CONTINUATION")
    try:
        url = urlsplit(value)
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True, errors="strict")
    except (ValueError, UnicodeError):
        raise LifecycleError("CONTINUATION") from None
    require(url.scheme == "https" and url.netloc == "management.azure.com" and
            url.path.lower() == resource_id.lower() and
            len({key.lower() for key, _ in pairs}) == len(pairs) and
            all(key and item for key, item in pairs) and
            dict(pairs).get("api-version") == api, "CONTINUATION")
    return value


def inventory(arm, resource_id, api, *, clock=time.monotonic):
    """Read the complete collection or fail; partial lists cannot prove ownership."""
    items, seen = [], set()
    link = None
    total_bytes = 0
    deadline = clock() + LIST_SECONDS
    for _ in range(MAX_LIST_PAGES):
        require(clock() < deadline, "INVENTORY_LIMIT")
        response = (arm("GET", resource_id, api) if link is None else
                    arm("GET", resource_id, api, next_link=link))
        require(clock() < deadline, "INVENTORY_LIMIT")
        status, document, _ = response
        require(status == 200 and isinstance(document, dict) and
                isinstance(document.get("value"), list) and
                all(isinstance(item, dict) for item in document["value"]), "INVENTORY")
        total_bytes += len(json.dumps(document).encode("utf-8"))
        require(total_bytes <= MAX_LIST_BYTES and
                len(items) + len(document["value"]) <= MAX_LIST_ITEMS, "INVENTORY_LIMIT")
        items.extend(document["value"])
        link = document.get("nextLink")
        if link is None or link == "":
            return items
        link = continuation_url(link, resource_id, api)
        require(link not in seen, "CONTINUATION_LOOP")
        seen.add(link)
    raise LifecycleError("INVENTORY_LIMIT")


def require_cleanup_unlocked(arm, approved, app_id):
    group = approved["resource_group_id"]
    subscription = group.split("/resourceGroups/", 1)[0]
    for scope in (subscription, group, app_id):
        for lock in inventory(arm, scope + LOCK_PROVIDER, LOCK_API):
            lock_id, properties = lock.get("id"), lock.get("properties")
            require(isinstance(lock_id, str) and isinstance(properties, dict) and
                    lock.get("type", "").lower() == "microsoft.authorization/locks", "LOCK_INVENTORY")
            locked_scope, separator, name = lock_id.lower().rpartition(LOCK_PROVIDER.lower() + "/")
            require(separator and re.fullmatch(r"[a-z0-9_.()-]+", name) and
                    (locked_scope == subscription.lower() or
                     locked_scope.startswith(subscription.lower() + "/")) and
                    (locked_scope == scope.lower() or locked_scope.startswith(scope.lower() + "/") or
                     scope.lower().startswith(locked_scope + "/")) and
                    properties.get("level") in ("CanNotDelete", "ReadOnly"), "LOCK_INVENTORY")
            # Sibling resource locks (for example a standing LAW) do not protect this app.
            require(not (locked_scope == app_id.lower() or
                         app_id.lower().startswith(locked_scope + "/") or
                         locked_scope.startswith(app_id.lower() + "/")), "CLEANUP_LOCKED")


def scaffold(project, env, approved):
    """Compare all deploy inputs to the fixture's literal heredocs, not an LLM claim."""
    fixture = Path(env["GITHUB_WORKSPACE"]) / "skills/foundry-mcp-aca/test-fixture/consumer_prompt.md"
    git_env = {key: value for key, value in env.items()
               if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    git_env["GIT_NO_REPLACE_OBJECTS"] = "1"
    expected = subprocess.run(
        ["git", "-C", env["GITHUB_WORKSPACE"], "show",
         approved["sha"] + ":skills/foundry-mcp-aca/test-fixture/consumer_prompt.md"],
        capture_output=True, timeout=10, check=False,
        env=git_env,
    )
    require(expected.returncode == 0, "CHECKOUT")
    text = expected.stdout.decode("utf-8")
    require(text == fixture.read_text(), "CHECKOUT")
    block = text.split("### Deterministic scaffold-authoring Bash block (MANDATORY)", 1)[1].split(
        "## Step 4", 1)[0]
    values = {
        "APP_NAME": env["APP_NAME"], "UAMI_RESOURCE_ID": approved["identity_id"],
        "ACR_SERVER": approved["acr_server"],
    }
    require(re.fullmatch(r"ci-smoke-mcp-[0-9a-f]{8}", values["APP_NAME"]), "APP_NAME")
    files = {}
    for match in re.finditer(r"cat > (\S+) <<('?)([A-Z]+)\2\n(.*?)\n\3\n", block, re.S):
        name, quoted, _, content = match.groups()
        if not quoted:
            for key, value in values.items():
                content = content.replace("${" + key + "}", value)
            content = content.replace(r"\$schema", "$schema")
        files[name] = content + "\n"
    require(set(files) == {"src/server.py", "src/requirements.txt", "src/Dockerfile",
                          "infra/main.bicep", "infra/main.parameters.json", "azure.yaml"}, "SCAFFOLD")
    for name, expected in files.items():
        path = project / name
        require(path.resolve() == path.absolute() and path.read_text() == expected, "SCAFFOLD")
    name = values["APP_NAME"]
    configuration = parse((project / ".azure/config.json").read_bytes())
    require(configuration == {"version": 1, "defaultEnvironment": name}, "SCAFFOLD")
    settings = (project / f".azure/{name}/.env").read_text().splitlines()
    expected_env = {
        "AZURE_ENV_NAME": name, "AZURE_LOCATION": "swedencentral",
        "AZURE_SUBSCRIPTION_ID": env["AZURE_SUBSCRIPTION_ID"],
        "AZURE_RESOURCE_GROUP": approved["resource_group_id"].rsplit("/", 1)[1],
        "AZURE_TENANT_ID": env["AZURE_TENANT_ID"],
        **values, "AZURE_CONTAINER_REGISTRY_ENDPOINT": approved["acr_server"],
    }
    require(sorted(settings) == sorted(f"{key}={value}" for key, value in expected_env.items()), "SCAFFOLD")
    allowed = set(files) | {".azure/config.json", f".azure/{name}/.env"}
    require(all(not path.is_symlink() and (path.is_dir() or path.relative_to(project).as_posix() in allowed)
                for path in project.rglob("*")), "SCAFFOLD")
    return {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()}


def binding(document, approved, app_id):
    require(isinstance(document, dict) and document.get("id", "").lower() == app_id.lower(), "APP_BINDING")
    properties = document.get("properties", {})
    require(properties.get("environmentId", "").lower() == approved["environment_id"].lower(), "APP_BINDING")
    identities = document.get("identity", {}).get("userAssignedIdentities", {})
    require(isinstance(identities, dict) and len(identities) == 1 and
            {key.lower() for key in identities} == {approved["identity_id"].lower()}, "APP_BINDING")
    created = document.get("systemData", {}).get("createdAt")
    require(isinstance(created, str) and bool(created), "APP_BINDING")
    containers = properties.get("template", {}).get("containers")
    require(isinstance(containers, list) and len(containers) == 1, "IMAGE")
    image = containers[0].get("image", "")
    require(image.startswith(approved["acr_server"] + "/"), "IMAGE")
    return {"id": app_id, "created_at": created, "image": image,
            "environment_id": properties["environmentId"],
            "identity_id": approved["identity_id"]}


def capture_operation(before, deployments, operations, app_id, app_name):
    matches = []
    prior = {item["id"].lower() for item in before}
    for deployment in deployments:
        properties = deployment.get("properties", {})
        if deployment["id"].lower() in prior:
            continue
        if properties.get("parameters", {}).get("appName", {}).get("value") != app_name:
            continue
        require(properties.get("provisioningState") == "Succeeded" and
                re.fullmatch(GUID, properties.get("correlationId", "")), "CREATE_ACK")
        for operation in operations(deployment["id"]):
            op = operation.get("properties", {})
            target = op.get("targetResource")
            if target is None:
                continue
            require(isinstance(target, dict), "CREATE_ACK")
            if target.get("id", "").lower() != app_id.lower():
                continue
            require(op.get("provisioningOperation") == "Create" and
                    op.get("provisioningState") == "Succeeded" and operation.get("operationId"), "CREATE_ACK")
            matches.append({"deployment_id": deployment["id"],
                            "correlation_id": properties["correlationId"],
                            "operation_id": operation["operationId"]})
    require(len(matches) == 1, "CREATE_ACK")
    return matches[0]


def deploy(env, approved, path, arm, run=subprocess.run):
    receipt_path = path / "receipt.json"
    require(not receipt_path.exists(), "RETRY_BLOCKED")
    project = Path(env["PROJECT_DIR"])
    require(project.is_absolute() and project.resolve() == project, "PATH")
    hashes = scaffold(project, env, approved)
    app_id = approved["resource_group_id"] + APP_PROVIDER + env["APP_NAME"]
    receipt = {
        "schema_version": 1, "run_id": approved["run_id"], "run_attempt": approved["run_attempt"],
        "sha": approved["sha"], "app_id": app_id, "source_hashes": hashes,
        "state": "PREPARING", "image_disposition": "UNKNOWN",
    }
    write(receipt_path, receipt)
    status, body, _ = arm("GET", app_id, API)
    require(absent(status, body), "PREEXISTING_OR_UNVERIFIED")
    require_cleanup_unlocked(arm, approved, app_id)
    before = inventory(arm, approved["resource_group_id"] + DEPLOY_PROVIDER, DEPLOY_API)
    receipt.update(state="UNKNOWN", pre_get="404_RESOURCE_NOT_FOUND",
                   deployment_ids_before=[item["id"] for item in before])
    write(receipt_path, receipt)
    encrypt(path, approved, env)
    # The receipt exists before the first mutation; failure/lost ACK forbids retry.
    require_lifetime(approved, DEPLOY_SECONDS + CAPTURE_SECONDS + FINALIZER_SECONDS)
    result = run(["azd", "up", "--no-prompt"], cwd=project, env=env,
                 capture_output=True, timeout=DEPLOY_SECONDS, check=False)
    receipt["azd_exit"] = result.returncode
    write(receipt_path, receipt)
    require(result.returncode == 0, "DEPLOY_UNKNOWN")
    deployments = inventory(arm, approved["resource_group_id"] + DEPLOY_PROVIDER, DEPLOY_API)
    receipt["create_ack"] = capture_operation(
        before, deployments,
        lambda deployment: deployment_operations(arm, deployment, approved),
        app_id, env["APP_NAME"],
    )
    write(receipt_path, receipt)
    status, document, _ = arm("GET", app_id, API)
    require(status == 200, "READBACK")
    receipt.update(binding=binding(document, approved, app_id), state="OWNED",
                   image_disposition="RETAINED_OWNER_APPROVED",
                   image_retain_until=approved["image_retain_until"])
    write(receipt_path, receipt)


def deployment_operations(arm, deployment_id, approved):
    require(isinstance(deployment_id, str) and re.fullmatch(
        re.escape(approved["resource_group_id"] + DEPLOY_PROVIDER) + r"/[A-Za-z0-9_.()-]+",
        deployment_id), "SCOPE")
    return inventory(arm, deployment_id + "/operations", DEPLOY_API)


def cleanup(approved, path, arm, *, clock=time.monotonic, sleep=time.sleep):
    receipt_path = path / "receipt.json"
    receipt = parse(private_read(receipt_path))
    for key in ("run_id", "run_attempt", "sha"):
        require(receipt.get(key) == approved[key], "CONTEXT")
    app_id = receipt.get("app_id", "")
    require(re.fullmatch(re.escape(approved["resource_group_id"] + APP_PROVIDER) +
                         r"ci-smoke-mcp-[0-9a-f]{8}", app_id), "SCOPE")
    if receipt.get("state") not in ("OWNED", "DELETE_REQUESTED", "APP_ABSENT_IMAGE_RETAINED"):
        raise LifecycleError("INVENTORY_UNKNOWN")
    require(receipt.get("pre_get") == "404_RESOURCE_NOT_FOUND" and
            receipt.get("azd_exit") == 0 and receipt.get("create_ack"), "CREATE_ACK")
    deadline = clock() + 240
    ack = receipt["create_ack"]
    operations = deployment_operations(arm, ack["deployment_id"], approved)
    status, deployment, _ = arm("GET", ack["deployment_id"], DEPLOY_API)
    require(status == 200, "CREATE_ACK")
    require(capture_operation(
        [{"id": value} for value in receipt["deployment_ids_before"]], [deployment],
        lambda _: operations, app_id, app_id.rsplit("/", 1)[1],
    ) == ack, "CREATE_ACK")
    status, document, etag = arm("GET", app_id, API)
    if not absent(status, document):
        require(status == 200 and binding(document, approved, app_id) == receipt.get("binding"), "OWNERSHIP_CHANGED")
        # Persist intent before DELETE so a cancelled run never claims absence.
        receipt["state"] = "DELETE_REQUESTED"
        write(receipt_path, receipt)
        def before_delete():
            require_lifetime(approved, FINALIZER_SECONDS)
            require(deadline - clock() >= MIN_DELETE_SECONDS, "CLEANUP_TIMEOUT")
        status, _, _ = arm("DELETE", app_id, API, etag, before_send=before_delete)
        require(status in (200, 202, 204), "DELETE_FAILED")
        while clock() < deadline:
            status, document, _ = arm("GET", app_id, API)
            if absent(status, document):
                break
            require(status == 200, "READBACK")
            require(binding(document, approved, app_id) == receipt.get("binding"), "OWNERSHIP_CHANGED")
            sleep(5)
        else:
            raise LifecycleError("CLEANUP_TIMEOUT")
    receipt["state"] = "APP_ABSENT_IMAGE_RETAINED"
    write(receipt_path, receipt)


def encrypt(path, approved, env, run=subprocess.run):
    source = private_read(path / "receipt.json")
    binary = Path(env["AGENTOPS_CI_AGE_BIN"])
    require(binary.is_absolute() and binary.resolve() == binary and
            hashlib.sha256(binary.read_bytes()).hexdigest() == env["AGENTOPS_CI_AGE_SHA256"], "CUSTODY")
    result = run([str(binary), "-r", approved["age_recipient"]],
                 input=source, capture_output=True, timeout=20, check=False)
    require(result.returncode == 0 and result.stdout.startswith(b"age-encryption.org/v1\n"), "CUSTODY")
    output = path / "inventory.age"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                stat.S_IMODE(info.st_mode) == 0o600, "PATH")
        os.ftruncate(stream.fileno(), 0)
        stream.write(result.stdout)


def main(args=None, environ=None):
    env = dict(os.environ if environ is None else environ)
    args = sys.argv[1:] if args is None else args
    path = None
    approved = None
    try:
        require(args in (["check"], ["init"], ["deploy"], ["cleanup"]), "ARGUMENTS")
        if args == ["check"]:
            approval(env, datetime.now(timezone.utc))
            print("MCP_ACA_LIFECYCLE=PASS CONFIG_ONLY")
            return 0
        path = root(env)
        approved = approval(env, datetime.now(timezone.utc),
                            None if args == ["init"] else private_read(path / "approval.json"))
        if args == ["init"]:
            path.mkdir(mode=0o700)
            write(path / "approval.json", approved)
            write(path / "receipt.json", {"state": "NOT_STARTED"})
            encrypt(path, approved, env)  # Prove encrypted custody before creation.
            (path / "receipt.json").unlink()
            print("MCP_ACA_LIFECYCLE=PASS PREPARED")
            return 0
        require(path.is_dir() and stat.S_IMODE(path.stat().st_mode) == 0o700, "PATH")
        if args == ["deploy"]:
            deploy(env, approved, path, Arm(env))
        else:
            cleanup(approved, path, Arm(env))
        encrypt(path, approved, env)
        state = parse(private_read(path / "receipt.json"))["state"]
        print(f"MCP_ACA_LIFECYCLE=PASS {state}")
        return 0
    except (LifecycleError, OSError, ValueError, KeyError, TypeError,
            AttributeError, IndexError, subprocess.TimeoutExpired) as error:
        code = str(error) if isinstance(error, LifecycleError) else "INPUT_OR_EXECUTION"
        print(f"MCP_ACA_LIFECYCLE=FAIL {code}")
        if path is not None and approved is not None and (path / "receipt.json").exists():
            try:
                receipt = parse(private_read(path / "receipt.json"))
                receipt["last_error"] = code
                write(path / "receipt.json", receipt)
                encrypt(path, approved, env)
            except (LifecycleError, OSError, ValueError, KeyError, TypeError,
                    AttributeError, IndexError, subprocess.TimeoutExpired):
                print("MCP_ACA_LIFECYCLE=FAIL CUSTODY")
        return 1


if __name__ == "__main__":
    def deadline(_signum, _frame):
        raise LifecycleError("DEADLINE")

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(280 if sys.argv[1:] == ["cleanup"] else 1500)
    try:
        sys.exit(main())
    finally:
        signal.alarm(0)
