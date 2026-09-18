#!/usr/bin/env python3
"""Runner-owned Jobs fixture custody, using the existing ARM and native lifecycle."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from uuid import uuid4

spec = importlib.util.spec_from_file_location("hosted_lifecycle", Path(__file__).with_name("hosted-ci-lifecycle.py"))
hosted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosted)
common = hosted.common
require, Error = common.require, common.LifecycleError
SKILL = "foundry-mcp-aca-jobs"
INPUTS = {
    "resource_group_id": "MCP_ACA_JOBS_RESOURCE_GROUP_ID",
    "environment_id": "MCP_ACA_JOBS_ENVIRONMENT_ID",
    "app_identity_id": "MCP_ACA_JOBS_APP_IDENTITY_ID",
    "worker_identity_id": "MCP_ACA_JOBS_WORKER_IDENTITY_ID",
    "cosmos_account_id": "MCP_ACA_JOBS_COSMOS_ACCOUNT_ID",
    "cosmos_database": "MCP_ACA_JOBS_COSMOS_DATABASE",
    "storage_account_id": "MCP_ACA_JOBS_STORAGE_ACCOUNT_ID",
    "caller_principal_id": "MCP_ACA_JOBS_CALLER_PRINCIPAL_ID",
    "auth_client_id": "MCP_AUTH_APP_CLIENT_ID",
    "cosmos_endpoint": "MCP_ACA_JOBS_COSMOS_ENDPOINT",
    "storage_url": "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL",
    "network_perimeter_id": "MCP_ACA_JOBS_NETWORK_PERIMETER_ID",
}
PROVIDERS = {
    "environment_id": "Microsoft.App/managedEnvironments",
    "app_identity_id": "Microsoft.ManagedIdentity/userAssignedIdentities",
    "worker_identity_id": "Microsoft.ManagedIdentity/userAssignedIdentities",
    "cosmos_account_id": "Microsoft.DocumentDB/databaseAccounts",
    "storage_account_id": "Microsoft.Storage/storageAccounts",
}
APIS = {"app": "2024-03-01", "job": "2024-03-01", "cosmos": "2023-04-15",
        "output": "2023-05-01", "callbacks": "2023-05-01"}


def approval(env, raw=None):
    a = common.parse(env.get("MCP_ACA_JOBS_CI_LIFECYCLE_APPROVAL_JSON", "") if raw is None else raw)
    require(isinstance(a, dict) and set(a) == {
        "native", *INPUTS, "delete_run_resources", "standing_resources_retained",
    }, "APPROVAL")
    native_env = {**env, "HOSTED_CI_SKILL": "foundry-hosted-agents"}
    a["native"] = hosted.approval(native_env, json.dumps(a["native"]))
    require(a["delete_run_resources"] is True and a["standing_resources_retained"] is True, "APPROVAL")
    for key, variable in INPUTS.items():
        require(isinstance(a[key], str) and (a[key] or key == "network_perimeter_id") and
                a[key] == env.get(variable, ""), "CONTEXT")
    group = a["resource_group_id"]
    require(re.fullmatch(rf"/subscriptions/{env['AZURE_SUBSCRIPTION_ID']}/resourceGroups/[A-Za-z0-9_.()-]+", group), "SCOPE")
    for key, provider in PROVIDERS.items():
        require(re.fullmatch(re.escape(group) + "/providers/" + re.escape(provider) +
                             r"/[a-zA-Z0-9_-]+", a[key]), "SCOPE")
    require(a["app_identity_id"].lower() != a["worker_identity_id"].lower(), "SEPARATE_IDENTITIES")
    require(re.fullmatch(r"[a-zA-Z0-9_-]+", a["cosmos_database"]), "SCOPE")
    require(a["storage_url"] == "https://" + a["storage_account_id"].rsplit("/", 1)[1] + ".blob.core.windows.net" and
            a["cosmos_endpoint"].rstrip("/") == "https://" +
            a["cosmos_account_id"].rsplit("/", 1)[1] + ".documents.azure.com:443", "ENDPOINT")
    require(all(re.fullmatch(common.GUID, a[k]) for k in ("caller_principal_id", "auth_client_id")) and
            a["auth_client_id"] != env["AZURE_CLIENT_ID"], "CALLER")
    require(not a["network_perimeter_id"] or re.fullmatch(
        re.escape(group) + r"/providers/Microsoft.Network/networkSecurityPerimeters/[A-Za-z0-9_.-]+",
        a["network_perimeter_id"]), "PERIMETER_SCOPE")
    return a


def root(env):
    native_env = {**env, "HOSTED_CI_SKILL": "foundry-hosted-agents"}
    return hosted.root(native_env).with_name(f"jobs-lifecycle-{env['GITHUB_RUN_ID']}-{env['GITHUB_RUN_ATTEMPT']}")


class Ledger:
    def __init__(self, path, a, env):
        self.path, self.a, self.env = path, deepcopy(a), env
        self.data = common.parse(common.private_read(path / "receipt.json"))
        self.validate()

    def validate(self):
        require(self.data.get("approval") == self.a and
                self.data.get("approval_sha256") == hosted.fingerprint(self.a), "CUSTODY")

    def save(self):
        self.validate()
        common.write(self.path / "receipt.json", self.data)
        common.encrypt(self.path, self.a["native"], self.env)

    def gate(self, seconds=600):
        require(not self.data.get("blocked"), "UNKNOWN_BLOCKS_PRODUCERS")
        self.validate()
        common.require_lifetime(self.a["native"], seconds + 850)

    def intent(self, name, seconds=600):
        self.gate(seconds)
        require(name not in self.data["intents"], "RETRY_BLOCKED")
        self.data["intents"].append(name)
        self.save()
        self.gate(seconds)


class Arm(common.Arm):
    """Only the owned app's EasyAuth and revision restarts can be sent directly."""
    def __init__(self, ledger):
        super().__init__(ledger.env)
        self.ledger = ledger

    def put(self, resource_id, api, body, before_send, *, method="PUT"):
        allowed = {self.ledger.data["resources"]["app"]["id"] + "/authConfigs/current"}
        revision_restart = re.fullmatch(
            re.escape(self.ledger.data["resources"]["app"]["id"]) + r"/revisions/[A-Za-z0-9_-]+/restart",
            resource_id)
        require((method == "PUT" and resource_id in allowed or method == "POST" and revision_restart) and
                callable(before_send), "SCOPE")
        token = hosted.command(
            ["az", "account", "get-access-token", "--resource", common.ARM_ORIGIN + "/",
             "--subscription", self.env["AZURE_SUBSCRIPTION_ID"], "--query", "accessToken", "-o", "tsv"],
            self.env, self.ledger.path, 20).decode().strip()
        require(token, "CREDENTIAL")
        request = Request(common.ARM_ORIGIN + resource_id + "?api-version=" + api,
                          method=method, data=json.dumps(body).encode() if body is not None else None,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        opener = build_opener(ProxyHandler({}), common.NoRedirect())
        before_send()
        try:
            response = opener.open(request, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(common.MAX_BYTES + 1)
            return response.code, common.parse(raw) if raw else {}, response.headers.get("ETag")


def absent(status, body):
    return status == 404 and isinstance(body, dict) and isinstance(body.get("error"), dict) and (
        body["error"].get("code") in ("ResourceNotFound", "ContainerAppNotFound", "NotFound",
                                   "JobNotFound", "ContainerNotFound"))


def binding(kind, body, ledger):
    item = ledger.data["resources"][kind]
    require(isinstance(body, dict) and body.get("id", "").lower() == item["id"].lower(), "RESOURCE_BINDING")
    p = body.get("properties", {})
    if kind in ("app", "job"):
        identities = body.get("identity", {}).get("userAssignedIdentities", {})
        identity = ledger.a["app_identity_id" if kind == "app" else "worker_identity_id"]
        environment = p.get("environmentId", p.get("managedEnvironmentId", ""))
        created = body.get("systemData", {}).get("createdAt")
        require(environment.lower() == ledger.a["environment_id"].lower() and
                {k.lower() for k in identities} == {identity.lower()} and created, "RESOURCE_BINDING")
        parsed = datetime.fromisoformat(created)
        # Only ARM systemData.createdAt has the documented implicit-UTC wire shape.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        require(common.utc(ledger.data["provision_started_at"]) <= parsed <= common.utc_now(),
                "CREATION_TIME")
        return {"id": item["id"].lower(), "created_at": created,
                "identity": identity.lower(), "environment": environment.lower()}
    if kind == "cosmos":
        resource = p.get("resource", {})
        require(resource.get("id") == item["id"].rsplit("/", 1)[1] and resource.get("_rid") and
                resource.get("partitionKey", {}).get("paths") == ["/ownerScope"] and
                resource.get("uniqueKeyPolicy", {}).get("uniqueKeys") == [{"paths": ["/idempotencyKeyHash"]}],
                "RESOURCE_BINDING")
        return {"id": item["id"].lower(), "rid": resource["_rid"]}
    require(p.get("publicAccess") == "None" and p.get("lastModifiedTime") and
            body.get("etag"), "RESOURCE_BINDING")
    return {"id": item["id"].lower(), "created_at": p["lastModifiedTime"], "etag": body["etag"]}


def read_owned(ledger, arm, kind):
    item = ledger.data["resources"][kind]
    require(item.get("state") == "OWNED" and item.get("pre_get_404") is True and
            item.get("evidence"), "OWNERSHIP_UNKNOWN")
    status, body, etag = arm("GET", item["id"], APIS[kind])
    require(status == 200 and binding(kind, body, ledger) == item["binding"], "OWNERSHIP_CHANGED")
    return body, etag


def prepare_resources(ledger, arm):
    a, data = ledger.a, ledger.data
    token = hosted.command(
        ["az", "account", "get-access-token", "--resource", common.ARM_ORIGIN + "/",
         "--subscription", ledger.env["AZURE_SUBSCRIPTION_ID"], "--query", "accessToken", "-o", "tsv"],
        ledger.env, ledger.path, 20).decode().strip()
    parts = token.split(".")
    require(len(parts) == 3, "CALLER")
    claims = common.parse(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    require(claims.get("oid") == a["caller_principal_id"] and
            claims.get("tid") == a["native"]["tenant_id"] and
            claims.get("azp", claims.get("appid")) == ledger.env["AZURE_CLIENT_ID"] and
            claims.get("idtyp", "app") == "app", "CALLER")
    data["caller_binding"] = {key: claims[key] for key in ("oid", "tid")}
    for kind, item in data["resources"].items():
        common.require_cleanup_unlocked(arm, a, item["id"])
        require(absent(*arm("GET", item["id"], APIS[kind])[:2]), "PREEXISTING_OR_UNVERIFIED")
        item["pre_get_404"] = True
    for key, api in (("resource_group_id", "2022-09-01"), ("environment_id", "2024-03-01"),
                     ("cosmos_account_id", "2025-04-15"), ("storage_account_id", "2025-01-01"),
                     ("app_identity_id", "2023-01-31"), ("worker_identity_id", "2023-01-31")):
        status, body, _ = arm("GET", a[key], api)
        require(status == 200 and body.get("id", "").lower() == a[key].lower(), "STANDING_RESOURCE")
        data.setdefault("standing", {})[key] = body
    for key in ("app_identity_id", "worker_identity_id"):
        properties = data["standing"][key]["properties"]
        require(all(re.fullmatch(common.GUID, properties.get(k, "")) for k in ("clientId", "principalId")) and
                properties.get("tenantId") == a["native"]["tenant_id"], "IDENTITY")
    require(data["standing"]["app_identity_id"]["properties"]["principalId"] !=
            data["standing"]["worker_identity_id"]["properties"]["principalId"], "SEPARATE_IDENTITIES")
    validate_standing_posture(data["standing"], "SecuredByPerimeter" if a["network_perimeter_id"] else "Enabled")
    if a["network_perimeter_id"]:
        verify_perimeter(ledger, arm)
    database = a["cosmos_account_id"] + "/sqlDatabases/" + a["cosmos_database"]
    status, body, _ = arm("GET", database, APIS["cosmos"])
    require(status == 200 and body.get("id", "").lower() == database.lower(), "STANDING_DATABASE")
    verify_standing_data(ledger)
    ledger.save()


def validate_standing_posture(standing, expected_mode="Enabled"):
    require(expected_mode in ("Enabled", "SecuredByPerimeter"), "STANDING_NETWORK_MODE")
    storage = standing["storage_account_id"]["properties"]
    require(storage.get("allowSharedKeyAccess") is False and storage.get("allowBlobPublicAccess") is False and
            storage.get("publicNetworkAccess") == expected_mode, "STANDING_STORAGE")
    cosmos = standing["cosmos_account_id"]["properties"]
    require(cosmos.get("disableLocalAuth") is True and cosmos.get("publicNetworkAccess") == expected_mode,
            "STANDING_COSMOS_NETWORK")
    if expected_mode == "SecuredByPerimeter":
        identity = standing["cosmos_account_id"].get("identity", {})
        require(identity.get("type") == "SystemAssigned" and
                re.fullmatch(common.GUID, identity.get("principalId", "")), "PERIMETER_IDENTITY")


def verify_perimeter(ledger, arm):
    perimeter = ledger.a["network_perimeter_id"]
    profile = perimeter + "/profiles/jobs-data"
    rules = common.inventory(arm, profile + "/accessRules", "2024-07-01")
    require(len(rules) == 1 and rules[0].get("id", "").lower() ==
            (profile + "/accessRules/ci-subscription").lower(), "PERIMETER_RULE")
    p = rules[0]["properties"]
    require(p.get("provisioningState") == "Succeeded" and p.get("direction") == "Inbound" and
            p.get("subscriptions") == [{"id": "/subscriptions/" + ledger.env["AZURE_SUBSCRIPTION_ID"]}] and
            all(not p.get(key) for key in ("addressPrefixes", "fullyQualifiedDomainNames",
                                          "emailAddresses", "phoneNumbers", "serviceTags")), "PERIMETER_RULE")
    profiles = common.inventory(arm, perimeter + "/profiles", "2024-07-01")
    require(len(profiles) == 1 and profiles[0].get("id", "").lower() == profile.lower(), "PERIMETER_PROFILE")
    associations = common.inventory(arm, perimeter + "/resourceAssociations", "2024-07-01")
    require(len(associations) == 2, "PERIMETER_ASSOCIATION")
    for name, key in (("storage", "storage_account_id"), ("cosmos", "cosmos_account_id")):
        matches = [a for a in associations if a.get("id", "").lower() ==
                   (perimeter + "/resourceAssociations/" + name).lower()]
        require(len(matches) == 1, "PERIMETER_ASSOCIATION")
        p = matches[0]["properties"]
        require(p.get("provisioningState") == "Succeeded" and p.get("accessMode") == "Enforced" and
                p.get("profile", {}).get("id", "").lower() == profile.lower() and
                p.get("privateLinkResource", {}).get("id", "").lower() == ledger.a[key].lower(),
                "PERIMETER_ASSOCIATION")
    ledger.data["perimeter_binding"] = {"rules": rules, "associations": associations, "profile": profiles[0]}


def verify_standing_data(ledger):
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient
    from azure.cosmos import CosmosClient
    with AzureCliCredential(tenant_id=ledger.a["native"]["tenant_id"], process_timeout=20) as credential:
        with BlobServiceClient(ledger.a["storage_url"], credential=credential, retry_total=0,
                               connection_timeout=20, read_timeout=20) as client:
            require(client.get_account_information().get("sku_name"), "STANDING_STORAGE_DATA")
        with CosmosClient(ledger.a["cosmos_endpoint"], credential=credential, retry_total=0,
                          connection_timeout=20, read_timeout=20) as client:
            result = client.get_database_client(ledger.a["cosmos_database"]).read()
            require(result.get("id") == ledger.a["cosmos_database"] and result.get("_rid"), "STANDING_DATABASE_DATA")
    ledger.data["standing_data_reads"] = "PASS"


def git_file(ledger, relative):
    env = {k: v for k, v in ledger.env.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return hosted.command(["git", "show", ledger.a["native"]["sha"] + ":" + relative],
                          env, env["GITHUB_WORKSPACE"], 10)


def scaffold(ledger):
    require(not (ledger.path / "scaffold").exists(), "RETRY_BLOCKED")
    bases = ((f"skills/{SKILL}/templates/", ""),
             (f"skills/{SKILL}/references/python/app/", "app/"),
             ("skills/azd-patterns/references/bicep/aca-job.bicep", "azd-patterns/references/bicep/aca-job.bicep"),
             ("skills/azd-patterns/references/bicep/jobs-run-data.bicep", "azd-patterns/references/bicep/jobs-run-data.bicep"))
    # Preserve the canonical sibling-module path without copying any unrelated skill.
    project = ledger.path / "scaffold" / SKILL / "templates"
    project.mkdir(parents=True)
    ledger.data["project"] = str(project)
    files = hosted.command(["git", "ls-tree", "-r", "--name-only", ledger.a["native"]["sha"], "--",
                            *(source for source, _ in bases)], ledger.env, ledger.env["GITHUB_WORKSPACE"], 10)
    hashes = {}
    for relative in files.decode().splitlines():
        source, target = next((s, t) for s, t in bases if relative.startswith(s))
        destination = (ledger.path / "scaffold" / target if source.endswith(".bicep") else
                       project / (target + relative[len(source):]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = git_file(ledger, relative)
        destination.write_bytes(raw)
        hashes[relative] = hashlib.sha256(raw).hexdigest()
    require(hashes, "SOURCE")
    a, d = ledger.a, ledger.data
    p = {
        "location": d["standing"]["environment_id"]["location"],
        "appName": d["resources"]["app"]["id"].rsplit("/", 1)[1],
        "jobName": d["resources"]["job"]["id"].rsplit("/", 1)[1],
        "environmentId": a["environment_id"],
        "environmentDomain": d["standing"]["environment_id"]["properties"]["defaultDomain"],
        "acrServer": a["native"]["acr_server"], "appIdentityId": a["app_identity_id"],
        "workerIdentityId": a["worker_identity_id"],
        "appClientId": d["standing"]["app_identity_id"]["properties"]["clientId"],
        "workerClientId": d["standing"]["worker_identity_id"]["properties"]["clientId"],
        "workerPrincipalId": d["standing"]["worker_identity_id"]["properties"]["principalId"],
        "callerPrincipalId": a["caller_principal_id"], "authClientId": a["auth_client_id"],
        "storageAccountUrl": a["storage_url"], "storageAccountName": a["storage_account_id"].rsplit("/", 1)[1],
        "cosmosAccountEndpoint": a["cosmos_endpoint"],
        "cosmosAccountName": a["cosmos_account_id"].rsplit("/", 1)[1],
        "cosmosDatabaseName": a["cosmos_database"], "cosmosContainerName": d["resources"]["cosmos"]["id"].rsplit("/", 1)[1],
        "outputStorageContainerName": d["resources"]["output"]["id"].rsplit("/", 1)[1],
    }
    import yaml
    config = yaml.safe_load((project / "azure.yaml").read_text())
    config["infra"] = {"provider": "bicep", "path": "infra", "module": "ci"}
    (project / "azure.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    (project / "infra/ci.parameters.json").write_text(json.dumps({
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0", "parameters": {k: {"value": v} for k, v in p.items()}}))
    name = d["resources"]["app"]["id"].rsplit("/", 1)[1]
    settings = {"AZURE_ENV_NAME": name, "AZURE_SUBSCRIPTION_ID": ledger.env["AZURE_SUBSCRIPTION_ID"],
                "AZURE_TENANT_ID": a["native"]["tenant_id"], "AZURE_RESOURCE_GROUP": a["resource_group_id"].rsplit("/", 1)[1],
                "AZURE_LOCATION": p["location"], "AZURE_CONTAINER_REGISTRY_ENDPOINT": a["native"]["acr_server"]}
    (project / f".azure/{name}").mkdir(parents=True)
    (project / ".azure/config.json").write_text(json.dumps({"version": 1, "defaultEnvironment": name}))
    (project / f".azure/{name}/.env").write_text("".join(f"{k}={v}\n" for k, v in settings.items()))
    d.update(source_hashes=hashes, parameters=p)
    ledger.save()
    return project


def capture_deployments(ledger, arm, baseline):
    group = ledger.a["resource_group_id"]
    roots = common.inventory(arm, group + common.DEPLOY_PROVIDER, common.DEPLOY_API)
    prior = {x["id"].lower() for x in baseline}
    name = ledger.data["parameters"]["appName"]
    roots = [d for d in roots if d["id"].lower() not in prior and
             d.get("properties", {}).get("parameters", {}).get("appName", {}).get("value") == name]
    require(len(roots) == 1, "DEPLOYMENT_UNKNOWN")
    require(all(roots[0]["properties"].get("parameters", {}).get(key, {}).get("value") == value
                for key, value in ledger.data["parameters"].items()), "DEPLOYMENT_PARAMETERS")
    queue, seen = [roots[0]], set()
    candidates = {kind: [] for kind in APIS}
    while queue:
        deployment = queue.pop()
        did, props = deployment["id"], deployment["properties"]
        require(did.lower().startswith(group.lower() + common.DEPLOY_PROVIDER.lower() + "/") and
                did.lower() not in seen and len(seen) < 8 and
                props.get("provisioningState") in ("Succeeded", "Failed") and
                re.fullmatch(common.GUID, props.get("correlationId", "")), "DEPLOYMENT_UNKNOWN")
        seen.add(did.lower())
        for op in common.inventory(arm, did + "/operations", common.DEPLOY_API):
            detail = op.get("properties", {})
            require(isinstance(detail, dict), "DEPLOYMENT_UNKNOWN")
            target = detail.get("targetResource")
            if target is None:
                continue
            require(isinstance(target, dict), "DEPLOYMENT_UNKNOWN")
            tid = target.get("id", "")
            require(isinstance(tid, str) and tid, "DEPLOYMENT_UNKNOWN")
            if tid.lower().startswith(group.lower() + common.DEPLOY_PROVIDER.lower() + "/"):
                status, child, _ = arm("GET", tid, common.DEPLOY_API)
                require(status == 200 and isinstance(child, dict) and
                        child.get("id", "").lower() == tid.lower(), "DEPLOYMENT_UNKNOWN")
                queue.append(child)
            for kind in APIS:
                item = ledger.data["resources"][kind]
                if tid.lower() == item["id"].lower():
                    candidates[kind].append((detail, {
                        "deployment_id": did, "parent_correlation_id": props["correlationId"],
                        "operation_id": op.get("operationId"), "root_id": roots[0]["id"],
                    }))
    # No ownership promotion until the complete deployment tree has been validated.
    ledger.data["deployment_history"] = sorted(seen)
    failures = ledger.data["capture_errors"] = {}
    for kind, matches in candidates.items():
        item = ledger.data["resources"][kind]
        try:
            require(len(matches) == 1, "CREATE_ACK_UNKNOWN")
            detail, evidence = matches[0]
            require(detail.get("provisioningOperation") == "Create" and
                    detail.get("provisioningState") == "Succeeded" and
                    isinstance(evidence["operation_id"], str) and evidence["operation_id"],
                    "CREATE_ACK_UNKNOWN")
            status, body, _ = arm("GET", item["id"], APIS[kind])
            require(status == 200 and item["pre_get_404"], "CREATE_UNKNOWN")
            first = binding(kind, body, ledger)
            status, second, _ = arm("GET", item["id"], APIS[kind])
            require(status == 200 and binding(kind, second, ledger) == first, "RESOURCE_BINDING")
        except Error as error:
            failures[kind] = str(error)
            item["state"] = "UNKNOWN"
        else:
            item.update(binding=first, evidence=evidence, state="OWNED")
        ledger.save()
    require(not failures, "CREATE_ACK_UNKNOWN")


def deploy(ledger, arm):
    require(ledger.data["state"] == "PREPARED", "RETRY_BLOCKED")
    prepare_resources(ledger, arm)
    project = scaffold(ledger)
    baseline = common.inventory(arm, ledger.a["resource_group_id"] + common.DEPLOY_PROVIDER, common.DEPLOY_API)
    ledger.data["deployment_baseline"] = baseline
    ledger.intent("provision", 1800)
    ledger.data["provision_started_at"] = common.utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    for kind in APIS:
        item = ledger.data["resources"][kind]
        common.require_cleanup_unlocked(arm, ledger.a, item["id"])
        require(absent(*arm("GET", item["id"], APIS[kind])[:2]), "PREEXISTING_OR_UNVERIFIED")
        item["state"] = "UNKNOWN"
    ledger.save()
    ledger.gate(1800)
    provision_error = None
    try:
        hosted.command(["azd", "provision", "--no-prompt"], ledger.env, project, 1200)
    except (Error, subprocess.TimeoutExpired) as error:
        provision_error = error
        ledger.data["provision_outcome"] = "FAILED_OR_UNKNOWN"
        ledger.save()
    capture_deployments(ledger, arm, baseline)
    if provision_error is not None:
        raise provision_error
    ledger.intent("deploy", 1800)
    for kind in ("app", "job"):
        read_owned(ledger, arm, kind)
    ledger.gate(1800)
    hosted.command(["azd", "deploy", "--no-prompt"], ledger.env, project, 1200)
    for kind in ("app", "job"):
        read_owned(ledger, arm, kind)
    values = common.parse(hosted.command(["azd", "env", "get-values", "--output", "json"],
                                        ledger.env, project, 20))
    tagged = values["SERVICE_MCP_IMAGE_NAME"]
    require(tagged.startswith(ledger.a["native"]["acr_server"] + "/") and "@" not in tagged, "IMAGE")
    metadata = common.parse(hosted.command([
        "az", "acr", "manifest", "show-metadata", "--registry", ledger.a["native"]["acr_server"].split(".")[0],
        "--name", tagged.split("/", 1)[1], "-o", "json"], ledger.env, project, 30))
    require(re.fullmatch(hosted.DIGEST, metadata.get("digest", "")), "IMAGE")
    image = tagged.rsplit(":", 1)[0] + "@" + metadata["digest"]
    verified = hosted.command(
        ["uv", "run", "--frozen", "python", "verify_deployment.py"],
        {**ledger.env, "EXPECTED_IMAGE_DIGEST": image}, project / "infra/scripts", 120).decode().splitlines()
    require("SHARED_IMAGE_DIGEST_MATCH" in verified and "ENTRYPOINTS_MATCH" in verified, "VERIFICATION")
    ledger.data["image"] = image
    print("SHARED_IMAGE_DIGEST_MATCH\nENTRYPOINTS_MATCH")
    ledger.data["state"] = "DEPLOYED"
    ledger.save()


def remove_resource(ledger, arm, kind, *, clock=time.monotonic, sleep=time.sleep):
    item = ledger.data["resources"][kind]
    require(item.get("state") in ("OWNED", "DELETING", "ABSENT") and item.get("evidence"), "OWNERSHIP_UNKNOWN")
    status, body, _ = arm("GET", item["id"], APIS[kind])
    if not absent(status, body):
        require(item["state"] == "OWNED" and not item.get("delete_intent"), "DELETE_ALREADY_ATTEMPTED")
        _, etag = read_owned(ledger, arm, kind)
        common.require_lifetime(ledger.a["native"], 300)
        item["delete_intent"] = True
        ledger.save()
        def guard():
            read_owned(ledger, arm, kind)
            common.require_lifetime(ledger.a["native"], 300)
        status, _, _ = arm("DELETE", item["id"], APIS[kind], etag, before_send=guard)
        require(status in (200, 202, 204), "DELETE_UNKNOWN")
        item["state"] = "DELETING"
        ledger.save()
    else:
        require(item.get("delete_intent"), "ABSENCE_UNPROVEN")
    deadline, consecutive = clock() + 90, 0
    while clock() < deadline:
        status, body, _ = arm("GET", item["id"], APIS[kind])
        if absent(status, body):
            consecutive += 1
            if consecutive == 2:
                item["state"] = "ABSENT"
                ledger.save()
                return
        else:
            require(status == 200 and binding(kind, body, ledger) == item["binding"], "OWNERSHIP_CHANGED")
            consecutive = 0
        sleep(5)
    raise Error("ABSENCE_UNPROVEN")


def initialize(path, a, env):
    path.mkdir(mode=0o700)
    suffix = uuid4().hex
    group = a["resource_group_id"]
    resources = {
        "app": group + "/providers/Microsoft.App/containerApps/ci-jobs-" + suffix[:16],
        "job": group + "/providers/Microsoft.App/jobs/ci-jobs-" + suffix[:16],
        "cosmos": a["cosmos_account_id"] + "/sqlDatabases/" + a["cosmos_database"] + "/containers/" + suffix,
        "output": a["storage_account_id"] + "/blobServices/default/containers/ci-jobs-" + suffix,
        "callbacks": a["storage_account_id"] + "/blobServices/default/containers/ci-jobs-" + suffix + "-callbacks",
    }
    common.write(path / "approval.json", a)
    common.write(path / "receipt.json", {
        "approval": a, "approval_sha256": hosted.fingerprint(a), "state": "PREPARED", "suffix": suffix,
        "intents": [], "resources": {k: {"id": v, "state": "PLANNED"} for k, v in resources.items()},
        "standing_resources": "RETAINED_NOT_RUN_OWNED", "assignments": "NONE_CREATED",
        "images_and_provider_history": "RETAINED_OWNER_APPROVED",
    })
    ledger = Ledger(path, a, env)
    ledger.save()
    return ledger


def environment(ledger):
    d, a = ledger.data, ledger.a
    require(d["state"] == "DEPLOYED", "DEPLOYMENT_UNKNOWN")
    p = d["parameters"]
    return {
        "PROJECT_DIR": d["project"], "SUFFIX": d["suffix"],
        "MCP_ACA_JOBS_COSMOS_DATABASE": a["cosmos_database"],
        "MCP_ACA_JOBS_COSMOS_CONTAINER": p["cosmosContainerName"],
        "MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME": p["outputStorageContainerName"],
        "CALLBACK_CONTAINER_URL": a["storage_url"] + "/" + p["outputStorageContainerName"] + "-callbacks",
        "MCP_URL": f"https://{p['appName']}.{p['environmentDomain']}/mcp",
        "HOSTED_NAME": "ci-smoke-ha-" + d["suffix"],
        "PROMPT_NAME": "ci-jobs-prompt-" + d["suffix"],
    }


def before_probe(ledger, arm, name):
    require(ledger.data["state"] == "DEPLOYED", "DEPLOYMENT_UNKNOWN")
    for kind in APIS:
        read_owned(ledger, arm, kind)
    ledger.intent("probe-" + name, 1200)


def upload_inputs(ledger, arm):
    from azure.core import MatchConditions
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient
    before_probe(ledger, arm, "inputs")
    container = ledger.data["parameters"]["outputStorageContainerName"]
    with AzureCliCredential(tenant_id=ledger.a["native"]["tenant_id"], process_timeout=20) as credential:
        credential.get_token("https://storage.azure.com/.default")
        with BlobServiceClient(ledger.a["storage_url"], credential=credential, retry_total=0,
                               connection_timeout=20, read_timeout=20) as service:
            for label in ("direct", "PROMPT_AGENT_MCP_PASS", "HOSTED_AGENT_MCP_PASS"):
                name = "inputs/" + label + "-" + ledger.data["suffix"] + ".json"
                blob = service.get_blob_client(container, name)
                entry = {"container": container, "name": name, "state": "UNKNOWN"}
                ledger.data.setdefault("inputs", []).append(entry)
                ledger.save()
                read_owned(ledger, arm, "output")
                ledger.gate(1200)
                ack = blob.upload_blob(b'{"durationSeconds":2}', overwrite=False,
                                       etag="*", match_condition=MatchConditions.IfMissing, timeout=20)
                require(ack.get("etag"), "BLOB_ACK")
                properties = blob.get_blob_properties(timeout=20)
                require(properties.etag == ack["etag"], "BLOB_BINDING")
                entry.update(state="OWNED", etag=ack["etag"])
                ledger.save()


class NativeLedger(hosted.Ledger):
    def __init__(self, ledger):
        self.parent = ledger
        path = ledger.path / "hosted"
        if not path.exists():
            path.mkdir(mode=0o700)
            a = ledger.a["native"]
            common.write(path / "receipt.json", {
                "context": {k: a[k] for k in ("skill", "sha", "run_id", "run_attempt")},
                "approval": a, "approval_sha256": hosted.fingerprint(a), "state": "PREPARED",
            })
        super().__init__(path, ledger.a["native"], ledger.env)

    def save(self):
        super().save()
        self.parent.data["hosted"] = deepcopy(self.data)
        self.parent.save()


def hosted_project(ledger):
    import yaml
    name = environment(ledger)["HOSTED_NAME"]
    project = ledger.path / "hosted-project"
    require(not project.exists(), "RETRY_BLOCKED")
    project.mkdir()
    expected = {
        target: git_file(ledger, "skills/foundry-hosted-agents/references/" + source)
        for target, source in {"Dockerfile": "docker/Dockerfile", "pyproject.toml": "python/pyproject.toml"}.items()
    }
    expected["container.py"] = git_file(ledger, f"skills/{SKILL}/test-fixture/hosted-container.py")
    config = yaml.safe_load(git_file(ledger, "skills/foundry-hosted-agents/references/yaml/azure.yaml"))
    service = config["services"].pop("my-agent")
    service["name"] = name
    extras = {"MCP_SERVER_URL": environment(ledger)["MCP_URL"],
              "MCP_AUTH_AUDIENCE": "api://" + ledger.a["auth_client_id"] + "/.default"}
    service["environmentVariables"] += [{"name": k, "value": v} for k, v in extras.items()]
    config["services"][name] = service
    expected["azure.yaml"] = yaml.safe_dump(config, sort_keys=False).encode()
    expected["copilot-instructions.md"] = b"Use the ACA Jobs MCP tools exactly as instructed.\n"
    for file, raw in expected.items():
        (project / file).write_bytes(raw)
    a = ledger.a["native"]
    values = {"AZURE_ENV_NAME": name, "AZURE_SUBSCRIPTION_ID": ledger.env["AZURE_SUBSCRIPTION_ID"],
              "FOUNDRY_PROJECT_ENDPOINT": a["project_endpoint"], "AZURE_AI_PROJECT_ID": a["project_id"],
              "AZURE_CONTAINER_REGISTRY_ENDPOINT": a["acr_server"], "AZURE_AI_MODEL_DEPLOYMENT_NAME": a["model"]}
    (project / f".azure/{name}").mkdir(parents=True)
    (project / ".azure/config.json").write_text(json.dumps({"version": 1, "defaultEnvironment": name}))
    (project / f".azure/{name}/.env").write_text("".join(f"{k}={v}\n" for k, v in values.items()))

    def verify(env, approved, agent, directory, published=None):
        require(agent == name and directory == project and approved == a, "SOURCE")
        require(project.is_absolute() and project.resolve() == project and
                {p.name for p in project.iterdir()} <= set(expected) | {".azure"}, "SOURCE")
        for file, raw in expected.items():
            path = project / file
            require(not path.is_symlink() and path.read_bytes() == raw, "SOURCE")
        hosted.azd_environment(env, project, name, values, published)
        return {file: hashlib.sha256(raw).hexdigest() for file, raw in expected.items()}
    return project, verify, {"AZURE_AI_MODEL_DEPLOYMENT_NAME": a["model"], **extras}


def deploy_hosted(ledger, arm):
    before_probe(ledger, arm, "hosted-deploy")
    ledger.gate(3300)
    project, verify, variables = hosted_project(ledger)
    child = NativeLedger(ledger)
    hosted.deploy(child, hosted.Native(ledger.env, child.a), arm, project, environment(ledger)["HOSTED_NAME"],
                  source_check=verify, environment_variables=variables)


def prompt_binding(version, name):
    require(version.name == name and version.version == "1" and version.id and
            version.created_at.tzinfo is not None, "PROMPT_BINDING")
    return {"id": version.id, "name": name, "version": version.version,
            "created_at": version.created_at.isoformat(), "definition": version.definition.as_dict()}


def create_prompt(ledger, arm):
    from azure.ai.projects.models import MCPTool, PromptAgentDefinition
    from azure.identity import AzureCliCredential
    before_probe(ledger, arm, "prompt-create")
    native = hosted.Native(ledger.env, ledger.a["native"])
    name = environment(ledger)["PROMPT_NAME"]
    require(native.absent("get", agent_name=name), "PREEXISTING_OR_UNVERIFIED")
    with AzureCliCredential(tenant_id=ledger.a["native"]["tenant_id"], process_timeout=20) as credential:
        token = credential.get_token("api://" + ledger.a["auth_client_id"] + "/.default")
    definition = PromptAgentDefinition(
        model=ledger.a["native"]["model"],
        instructions="Call start_aca_job once, then get_aca_job_status with its taskId. "
                     "Use the requested inputRef exactly. Do not emit the verification marker as assistant text.",
        tools=[MCPTool(server_label="aca_jobs", server_url=environment(ledger)["MCP_URL"],
                       authorization=token.token, require_approval="never")],
    )
    item = {"name": name, "pre_get_404": True, "state": "UNKNOWN", "definition": definition.as_dict()}
    ledger.data["prompt"] = item
    ledger.save()
    with native.client(mutate=True) as agents:
        require(native.absent("get", agent_name=name), "PREEXISTING_OR_UNVERIFIED")
        ledger.gate(600)
        version = agents.create_version(agent_name=name, definition=definition)
    item["ack"] = prompt_binding(version, name)
    ledger.save()
    versions = native.inventory("versions", name)
    require(len(versions) == 1 and versions[0].version == "1", "PROMPT_UNKNOWN")
    direct = prompt_binding(native.call("get_version", agent_name=name, agent_version="1"), name)
    require(direct == item["ack"] and direct["definition"] == item["definition"], "PROMPT_BINDING")
    agent = native.call("get", agent_name=name)
    require(agent.name == name and agent.id and agent.created_at.tzinfo is not None, "PROMPT_BINDING")
    item.update(binding=direct, state="OWNED",
                agent_binding={"id": agent.id, "created_at": agent.created_at.isoformat()})
    ledger.save()


def authorize_hosted(ledger, arm):
    child = NativeLedger(ledger)
    native = hosted.Native(ledger.env, child.a)
    hosted.reconcile(child, native)
    principal = child.data["binding"]["identity"]["principal_id"]
    read_owned(ledger, arm, "app")
    resource_id = ledger.data["resources"]["app"]["id"] + "/authConfigs/current"
    status, original, _ = arm("GET", resource_id, "2025-01-01")
    require(status == 200 and original.get("id", "").lower() == resource_id.lower(), "AUTH_BINDING")
    expected = deepcopy(original["properties"])
    validation = expected["identityProviders"]["azureActiveDirectory"]["validation"]
    policy = validation["defaultAuthorizationPolicy"]
    require(set(policy) == {"allowedPrincipals"} and set(policy["allowedPrincipals"]["identities"]) == {
        ledger.a["caller_principal_id"], ledger.data["standing"]["worker_identity_id"]["properties"]["principalId"],
    }, "AUTH_BINDING")
    policy["allowedPrincipals"]["identities"].append(principal)
    ledger.data["easy_auth"] = {"original": original["properties"], "expected": expected, "state": "UNKNOWN"}
    ledger.intent("easy-auth", 600)
    def guard():
        read_owned(ledger, arm, "app")
        hosted.reconcile(child, native)
        current_status, current, _ = arm("GET", resource_id, "2025-01-01")
        require(current_status == 200 and current["properties"] == original["properties"], "AUTH_CHANGED")
        ledger.gate()
    status, _, _ = arm.put(resource_id, "2025-01-01", {"properties": expected}, guard)
    require(status in (200, 201), "AUTH_WRITE_UNKNOWN")
    for _ in range(12):
        status, current, _ = arm("GET", resource_id, "2025-01-01")
        require(status == 200, "AUTH_WRITE_UNKNOWN")
        if current["properties"] == expected:
            break
        time.sleep(5)
    else:
        raise Error("AUTH_WRITE_UNKNOWN")
    ledger.data["easy_auth"]["state"] = "OWNED_PARENT_CASCADE"
    ledger.save()
    app_id = ledger.data["resources"]["app"]["id"]
    revisions = common.inventory(arm, app_id + "/revisions", APIS["app"])
    active = [item for item in revisions if item.get("properties", {}).get("active") is True]
    require(1 <= len(active) <= 3, "REVISIONS_UNKNOWN")
    for revision in active:
        rid = revision.get("id", "")
        require(re.fullmatch(re.escape(app_id) + r"/revisions/[A-Za-z0-9_-]+", rid, re.I), "REVISION_SCOPE")
        ledger.intent("restart:" + rid, 600)
        def before_restart():
            read_owned(ledger, arm, "app")
            status, current, _ = arm("GET", resource_id, "2025-01-01")
            require(status == 200 and current["properties"] == expected, "AUTH_CHANGED")
            ledger.gate()
        status, _, _ = arm.put(rid + "/restart", APIS["app"], None, before_restart, method="POST")
        require(status in (200, 202, 204), "RESTART_UNKNOWN")
    ledger.data["easy_auth"]["restarts_acknowledged"] = [item["id"] for item in active]
    ledger.save()
    hosted.configure_routing(child, native)


def before_invoke(ledger, arm, kind):
    before_probe(ledger, arm, "invoke-" + kind)
    if kind == "hosted":
        child = NativeLedger(ledger)
        hosted.before_invoke(child, hosted.Native(ledger.env, child.a))
    else:
        item = ledger.data["prompt"]
        native = hosted.Native(ledger.env, ledger.a["native"])
        require(item["state"] == "OWNED" and prompt_binding(native.call(
            "get_version", agent_name=item["name"], agent_version="1"), item["name"]) == item["binding"],
            "PROMPT_BINDING")
    ledger.gate()


def cleanup_prompt(ledger):
    item = ledger.data.get("prompt")
    if item is None:
        return
    require(item["state"] == "OWNED" and item.get("binding") and item["pre_get_404"], "PROMPT_UNKNOWN")
    native = hosted.Native(ledger.env, ledger.a["native"])
    name = item["name"]
    for kind, kwargs in (("version", {"agent_name": name, "agent_version": "1"}),
                         ("agent", {"agent_name": name})):
        get, delete = ("get_version", "delete_version") if kind == "version" else ("get", "delete")
        if not native.absent(get, **kwargs):
            require(not item.get("delete_" + kind), "DELETE_ALREADY_ATTEMPTED")
            item["delete_" + kind] = True
            ledger.save()
            def guard():
                if kind == "version":
                    require(prompt_binding(native.call(get, **kwargs), name) == item["binding"],
                            "PROMPT_BINDING")
                    versions = native.inventory("versions", name)
                    require(len(versions) == 1 and versions[0].version == "1", "PROMPT_UNKNOWN")
                    require(native.inventory("sessions", name) == [], "PROMPT_UNKNOWN")
                else:
                    require(native.inventory("versions", name) == [] and
                            native.inventory("sessions", name) == [], "PROMPT_UNKNOWN")
                    agent = native.call("get", agent_name=name)
                    require(agent.name == name and {"id": agent.id, "created_at": agent.created_at.isoformat()} ==
                            item["agent_binding"], "PROMPT_BINDING")
                common.require_lifetime(ledger.a["native"], 300)
            native.call(delete, before_send=guard, **kwargs, force=False)
        else:
            require(item.get("delete_" + kind), "ABSENCE_UNPROVEN")
        require(native.absent(get, **kwargs), "ABSENCE_UNPROVEN")
        time.sleep(2)
        require(native.absent(get, **kwargs), "ABSENCE_UNPROVEN")
    item["state"] = "ABSENT"
    ledger.save()


def collect_pages(iterator, fields, *, clock=time.monotonic):
    records, deadline = [], clock() + 120
    for index, page in enumerate(iterator.by_page()):
        require(index < 20 and clock() < deadline, "INVENTORY_LIMIT")
        for entry in page:
            require(len(records) < 200 and clock() < deadline, "INVENTORY_LIMIT")
            record = {key: entry.get(key) for key in fields}
            require(all(record[key] is not None for key in fields if key != "acaExecutionId"), "DATA_INVENTORY")
            records.append(record)
    return records


def data_inventory(ledger):
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient
    from azure.cosmos import CosmosClient
    result = {}
    with AzureCliCredential(tenant_id=ledger.a["native"]["tenant_id"], process_timeout=20) as credential:
        with BlobServiceClient(ledger.a["storage_url"], credential=credential, retry_total=0,
                               connection_timeout=20, read_timeout=20) as storage:
            for kind in ("output", "callbacks"):
                if ledger.data["resources"][kind]["state"] != "OWNED":
                    continue
                name = ledger.data["resources"][kind]["id"].rsplit("/", 1)[1]
                result[kind] = collect_pages(storage.get_container_client(name).list_blobs(results_per_page=50),
                                       ("name", "etag", "size"))
        with CosmosClient(ledger.a["cosmos_endpoint"], credential=credential, retry_total=0,
                          connection_timeout=20, read_timeout=20) as cosmos:
            if ledger.data["resources"]["cosmos"]["state"] == "OWNED":
                container = cosmos.get_database_client(ledger.a["cosmos_database"]).get_container_client(
                    ledger.data["resources"]["cosmos"]["id"].rsplit("/", 1)[1])
                result["records"] = collect_pages(container.read_all_items(max_item_count=50),
                                        ("id", "_rid", "_etag", "ownerScope", "acaExecutionId"))
    ledger.data["data_inventory"] = result
    ledger.save()


def verify_data_absence(ledger, kind):
    from azure.core.exceptions import ResourceNotFoundError
    from azure.cosmos import CosmosClient
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient
    name = ledger.data["resources"][kind]["id"].rsplit("/", 1)[1]
    captured = ledger.data.get("data_inventory", {})
    key = "records" if kind == "cosmos" else kind
    require(key in captured, "DATA_INVENTORY_MISSING")
    with AzureCliCredential(tenant_id=ledger.a["native"]["tenant_id"], process_timeout=20) as credential:
        if kind == "cosmos":
            with CosmosClient(ledger.a["cosmos_endpoint"], credential=credential, retry_total=0,
                              connection_timeout=20, read_timeout=20) as client:
                container = client.get_database_client(ledger.a["cosmos_database"]).get_container_client(name)
                for item in captured[key]:
                    for _ in range(2):
                        try:
                            container.read_item(item["id"], partition_key=item["ownerScope"])
                        except CosmosResourceNotFoundError as error:
                            require(error.status_code == 404, "RECORD_ABSENCE_UNPROVEN")
                        else:
                            raise Error("RECORD_STILL_PRESENT")
        else:
            with BlobServiceClient(ledger.a["storage_url"], credential=credential, retry_total=0,
                                   connection_timeout=20, read_timeout=20) as client:
                for item in captured[key]:
                    blob = client.get_blob_client(name, item["name"])
                    for _ in range(2):
                        try:
                            blob.get_blob_properties(timeout=20)
                        except ResourceNotFoundError as error:
                            require(error.status_code == 404 and error.error_code in
                                    ("BlobNotFound", "ContainerNotFound"), "BLOB_ABSENCE_UNPROVEN")
                        else:
                            raise Error("BLOB_STILL_PRESENT")
    ledger.data.setdefault("data_absence", {})[kind] = {
        "captured_items": len(captured[key]), "reads_per_item": 2,
        "parent_arm_absence": ledger.data["resources"][kind]["state"],
    }
    ledger.save()


def runtime_errors():
    from azure.core.exceptions import AzureError
    from httpx import HTTPError as HttpxError
    from mcp.shared import exceptions as mcp_errors
    from openai import OpenAIError
    from fastmcp.exceptions import FastMCPError
    from httpx2 import HTTPError as Httpx2Error
    mcp_error = mcp_errors.MCPError if hasattr(mcp_errors, "MCPError") else mcp_errors.McpError
    return (AzureError, HttpxError, Httpx2Error, mcp_error, OpenAIError, FastMCPError)


def error_code(error):
    if isinstance(error, Error) and str(error) == "DEADLINE":
        raise error
    return str(error) if isinstance(error, Error) else "SDK_" + type(error).__name__


def verify_cascades(ledger, arm, kind):
    if kind == "job":
        for execution in ledger.data.get("executions", []):
            resource_id = execution.get("id", "")
            parent = ledger.data["resources"]["job"]["id"]
            require(re.fullmatch(re.escape(parent) + r"/executions/[a-zA-Z0-9_-]+", resource_id, re.I), "EXECUTION_SCOPE")
            for _ in range(2):
                require(absent(*arm("GET", resource_id, APIS[kind])[:2]), "EXECUTION_ABSENCE_UNPROVEN")
    if kind == "app":
        resource_id = ledger.data["resources"]["app"]["id"] + "/authConfigs/current"
        for _ in range(2):
            status, body, _ = arm("GET", resource_id, "2025-01-01")
            require(absent(status, body) or status == 404 and body.get("error", {}).get("code") ==
                    "ParentResourceNotFound", "AUTH_ABSENCE_UNPROVEN")


def cleanup(ledger, arm):
    common.require_lifetime(ledger.a["native"], 850)
    errors = []
    for name, action in (
        ("prompt", lambda: cleanup_prompt(ledger)),
        ("hosted", lambda: hosted.cleanup_native(NativeLedger(ledger), hosted.Native(ledger.env, ledger.a["native"]))
         if ledger.data.get("hosted") else None),
    ):
        try:
            action()
        except (Error, *runtime_errors()) as error:
            errors.append(name + ":" + error_code(error))
    # Stop all producers by removing ONLY the owned app and Job before deleting their data.
    for kind in ("app", "job"):
        item = ledger.data["resources"][kind]
        if item["state"] == "PLANNED":
            continue
        try:
            if kind == "job":
                if item["state"] == "OWNED":
                    read_owned(ledger, arm, kind)
                    ledger.data["executions"] = common.inventory(arm, item["id"] + "/executions", APIS[kind])
                    ledger.save()
            remove_resource(ledger, arm, kind)
            verify_cascades(ledger, arm, kind)
        except (Error, *runtime_errors()) as error:
            errors.append(kind + ":" + error_code(error))
    if (not any(error.startswith(("app:", "job:")) for error in errors) and
            all(ledger.data["resources"][kind]["state"] in ("ABSENT", "PLANNED") for kind in ("app", "job"))):
        try:
            if any(ledger.data["resources"][kind]["state"] == "OWNED" for kind in ("cosmos", "callbacks", "output")):
                data_inventory(ledger)
        except (Error, *runtime_errors()) as error:
            errors.append("inventory:" + error_code(error))
        for kind in (() if any(error.startswith("inventory:") for error in errors) else ("cosmos", "callbacks", "output")):
            if ledger.data["resources"][kind]["state"] == "PLANNED":
                continue
            try:
                remove_resource(ledger, arm, kind)
                verify_data_absence(ledger, kind)
            except (Error, *runtime_errors()) as error:
                errors.append(kind + ":" + error_code(error))
    else:
        errors.append("data:PRODUCER_ABSENCE_UNPROVEN")
    ledger.data["cleanup_errors"] = errors
    ledger.data["cleanup_state"] = ("RESIDUAL_OR_UNKNOWN" if errors else
        "RUN_RESOURCES_ABSENT_STANDING_IMAGES_HISTORY_RETAINED")
    ledger.save()
    require(not errors, "CLEANUP_RESIDUAL")


def smoke(ledger, arm):
    deploy(ledger, arm)
    upload_inputs(ledger, arm)
    raw = git_file(ledger, f"skills/{SKILL}/test-fixture/probes.py")
    probe_path = ledger.path / "probes.py"
    probe_path.write_bytes(raw)
    ledger.data["probe_sha256"] = hashlib.sha256(raw).hexdigest()
    ledger.save()
    spec = importlib.util.spec_from_file_location("jobs_probes", probe_path)
    probes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probes)
    module = sys.modules[__name__]
    asyncio.run(probes.direct(ledger, module))
    create_prompt(ledger, arm)
    probes.invoke(ledger, module, "prompt")
    deploy_hosted(ledger, arm)
    native = hosted.Native(ledger.env, ledger.a["native"])
    name = environment(ledger)["HOSTED_NAME"]
    for _ in range(24):
        version = native.call("get_version", agent_name=name, agent_version="1")
        require(version.status != "failed", "HOSTED_FAILED")
        if version.status == "active":
            break
        time.sleep(10)
    else:
        raise Error("HOSTED_NOT_ACTIVE")
    authorize_hosted(ledger, arm)
    probes.invoke(ledger, module, "hosted")
    ledger.data["functional"] = "PASS"
    ledger.save()
    Path("/tmp/foundry-mcp-aca-jobs-smoke-result").write_text("SMOKE_RESULT=PASS\n")


def main(argv=None, env=None):
    argv, env = sys.argv[1:] if argv is None else argv, dict(os.environ if env is None else env)
    ledger = None
    try:
        require(len(argv) == 1 and argv[0] in {
            "check", "init", "deploy", "env", "export-env", "upload-inputs", "direct", "create-prompt",
            "deploy-hosted", "authorize-hosted",             "invoke-prompt", "invoke-hosted", "cleanup", "smoke",
        }, "ARGUMENTS")
        mode, path = argv[0], root(env)
        a = approval(env, None if mode in ("check", "init") else common.private_read(path / "approval.json"))
        if mode == "check":
            print("JOBS_CI_LIFECYCLE=PASS CONFIG_ONLY")
            return 0
        if mode == "init":
            initialize(path, a, env)
        require(path.is_dir() and not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o700, "PATH")
        with hosted.exclusive(path):
            ledger = Ledger(path, a, env)
            if mode == "export-env":
                env.setdefault("MCP_ACA_JOBS_NETWORK_PERIMETER_ID", "")
                names = set(INPUTS.values()) | {
                    "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_AI_PROJECT_ID",
                    "FOUNDRY_PROJECT_ENDPOINT", "ACR_LOGIN_SERVER",
                }
                for name in sorted(names):
                    require(isinstance(env.get(name), str) and "\n" not in env[name] and "\r" not in env[name], "CONTEXT")
                    print(name + "=" + env[name])
                return 0
            if mode == "env":
                print(json.dumps(environment(ledger)))
                return 0
            if mode != "init":
                arm = Arm(ledger)
                actions = {
                    "smoke": lambda: smoke(ledger, arm),
                    "deploy": lambda: deploy(ledger, arm),
                    "upload-inputs": lambda: upload_inputs(ledger, arm),
                    "direct": lambda: before_probe(ledger, arm, "direct"),
                    "create-prompt": lambda: create_prompt(ledger, arm),
                    "deploy-hosted": lambda: deploy_hosted(ledger, arm),
                    "authorize-hosted": lambda: authorize_hosted(ledger, arm),
                    "invoke-prompt": lambda: before_invoke(ledger, arm, "prompt"),
                    "invoke-hosted": lambda: before_invoke(ledger, arm, "hosted"),
                    "cleanup": lambda: cleanup(ledger, arm),
                }
                try:
                    actions[mode]()
                except runtime_errors() as error:
                    raise Error(error_code(error)) from None
        print("JOBS_CI_LIFECYCLE=PASS " + mode.upper())
        return 0
    except (Error, OSError, ValueError, KeyError, TypeError, AttributeError, AssertionError,
            subprocess.TimeoutExpired) as error:
        if ledger is not None:
            ledger.data["blocked"] = True
            ledger.data["last_error"] = str(error) if isinstance(error, Error) else "INPUT_OR_EXECUTION"
            ledger.save()
        print("JOBS_CI_LIFECYCLE=FAIL " + (str(error) if isinstance(error, Error) else "INPUT_OR_EXECUTION"))
        if argv == ["smoke"]:
            Path("/tmp/foundry-mcp-aca-jobs-smoke-result").write_text("SMOKE_RESULT=FAIL lifecycle or functional assertion\n")
        return 1


if __name__ == "__main__":
    def deadline(_signal, _frame):
        raise Error("DEADLINE")
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, deadline)
    signal.alarm(850 if sys.argv[1:] == ["cleanup"] else 5400)
    sys.exit(main())
