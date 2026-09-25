"""Canonical explicit CI standing-resource preflight, staging and cleanup.

Source of truth for ../../../SKILL.md § Deploy with azd.
prepare/check use authenticated reads only; cleanup requires --execute.
No identity, role, database, resource-group or network provisioning fallback.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit


INPUTS = {
    "group": "MCP_ACA_JOBS_RESOURCE_GROUP_ID",
    "environment": "MCP_ACA_JOBS_ENVIRONMENT_ID",
    "app_identity": "MCP_ACA_JOBS_APP_IDENTITY_ID",
    "worker_identity": "MCP_ACA_JOBS_WORKER_IDENTITY_ID",
    "cosmos": "MCP_ACA_JOBS_COSMOS_ACCOUNT_ID",
    "database": "MCP_ACA_JOBS_COSMOS_DATABASE",
    "storage": "MCP_ACA_JOBS_STORAGE_ACCOUNT_ID",
    "registry": "MCP_ACA_JOBS_REGISTRY_ID",
    "registry_host": "ACR_LOGIN_SERVER",
    "executor": "MCP_ACA_JOBS_CALLER_PRINCIPAL_ID",
    "audience": "MCP_AUTH_APP_CLIENT_ID",
    "cosmos_endpoint": "MCP_ACA_JOBS_COSMOS_ENDPOINT",
    "storage_endpoint": "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL",
    "tenant": "AZURE_TENANT_ID",
    "subscription": "AZURE_SUBSCRIPTION_ID",
    "executor_client": "AZURE_CLIENT_ID",
}
TYPES = {
    "environment": "Microsoft.App/managedEnvironments",
    "app_identity": "Microsoft.ManagedIdentity/userAssignedIdentities",
    "worker_identity": "Microsoft.ManagedIdentity/userAssignedIdentities",
    "cosmos": "Microsoft.DocumentDB/databaseAccounts",
    "storage": "Microsoft.Storage/storageAccounts",
    "registry": "Microsoft.ContainerRegistry/registries",
}
VERSIONS = {"group": "2022-09-01", "environment": "2024-03-01",
            "app_identity": "2023-01-31", "worker_identity": "2023-01-31",
            "cosmos": "2024-11-15", "storage": "2023-01-01", "registry": "2023-07-01"}
JOB_ACTIONS = {"Microsoft.App/jobs/read", "Microsoft.App/jobs/start/action",
               "Microsoft.App/jobs/execution/read", "Microsoft.App/jobs/executions/read",
               "Microsoft.App/jobs/stop/execution/action"}
BUILTIN_ROLES = {
    "Contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
    "AcrPull": "7f951dda-4ed3-4680-a7ca-43fe172d538d",
    "AcrPush": "8311e382-0749-4cb8-b61a-304f252e45ec",
    "Storage Blob Data Contributor": "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
}


class ReuseError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise ReuseError(code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_KEY")
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write_new(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, indent=2)
        output.flush()
        os.fsync(output.fileno())


def same(a, b):
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()


def endpoint(value):
    require(isinstance(value, str) and not any(c.isspace() for c in value), "ENDPOINT")
    url = urlsplit(value)
    require(url.scheme == "https" and url.hostname and url.port in (None, 443)
            and not url.username and not url.password and not url.query and not url.fragment
            and url.path in ("", "/"), "ENDPOINT")
    return "https://" + url.hostname.lower()


def settings(environ, run_id):
    require(environ.get("MCP_ACA_JOBS_CI_REUSE") == "existing", "EXPLICIT_CI_REUSE_REQUIRED")
    require(re.fullmatch("[0-9a-f]{8}", run_id or "") is not None, "RUN_ID")
    config = {key: environ.get(name, "") for key, name in INPUTS.items()}
    require(all(isinstance(v, str) and v.strip() and v == v.strip() for v in config.values()), "MISSING_STANDING_INPUT")
    for key in ("tenant", "subscription", "executor", "executor_client", "audience"):
        require(re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", config[key]) is not None, "IDENTIFIER")
    prefix = "/subscriptions/" + config["subscription"] + "/resourceGroups/"
    require(config["group"].lower().startswith(prefix.lower())
            and re.fullmatch(r"[A-Za-z0-9_.()-]+", config["group"][len(prefix):]) is not None, "GROUP_SCOPE")
    for key, kind in TYPES.items():
        expected = config["group"] + "/providers/" + kind + "/"
        require(config[key].lower().startswith(expected.lower())
                and re.fullmatch(r"[A-Za-z0-9_-]+", config[key][len(expected):]) is not None, "STANDING_SCOPE_" + key)
    require(not same(config["app_identity"], config["worker_identity"]), "DISTINCT_IDENTITIES")
    require(re.fullmatch(r"[A-Za-z0-9_-]+", config["database"]) is not None, "DATABASE_NAME")
    config.update(run_id=run_id, mode="existing")
    config["cosmos_endpoint"] = endpoint(config["cosmos_endpoint"])
    config["storage_endpoint"] = endpoint(config["storage_endpoint"])
    require(re.fullmatch(r"[a-z0-9]+\.azurecr\.io", config["registry_host"]) is not None, "REGISTRY_HOST")
    return config


def cli(config, args, *, absent=False):
    command = ["az", *args, "--output", "json", "--only-show-errors"]
    if args[:2] != ["account", "show"]:
        command += ["--subscription", config["subscription"]]
    result = subprocess.run(command,
                            capture_output=True, text=True, timeout=45)
    if result.returncode:
        # Only exact resource-not-found is absence. Generic HTTP404/auth/transport is unknown.
        if absent and re.search(r"\((ResourceNotFound|ResourceGroupNotFound)\)", result.stderr):
            return None
        if absent and args[:2] == ["acr", "manifest"] and re.search(r"\b(MANIFEST_UNKNOWN|NAME_UNKNOWN)\b", result.stderr):
            return None
        raise ReuseError("AZURE_READ_OR_OPERATION_FAILED")
    return json.loads(result.stdout) if result.stdout.strip() else None


def get(config, resource_id, version, *, absent=False):
    return cli(config, ["rest", "--method", "get", "--url",
                        f"https://management.azure.com{resource_id}?api-version={version}"], absent=absent)


def observations(config):
    data = {key: get(config, config[key], version) for key, version in VERSIONS.items()}
    data["database"] = get(config, config["cosmos"] + "/sqlDatabases/" + config["database"], "2024-11-15")
    data["account"] = cli(config, ["account", "show"])
    identities = cli(config, ["identity", "list", "--resource-group", config["group"].rsplit("/", 1)[1]])
    matches = [i for i in identities if same(i.get("clientId"), config["executor_client"])]
    require(len(matches) == 1, "EXECUTOR_IDENTITY_MAPPING")
    data["executor_identity"] = matches[0]
    data["grants"] = {}
    principals = {"executor": config["executor"],
                  "app": data["app_identity"]["properties"]["principalId"],
                  "worker": data["worker_identity"]["properties"]["principalId"]}
    for actor, principal in principals.items():
        data["grants"][actor] = {}
        for scope_name in ("group", "registry", "storage"):
            rows = cli(config, ["role", "assignment", "list", "--assignee-object-id", principal,
                               "--scope", config[scope_name], "--include-inherited"])
            require(isinstance(rows, list), "ROLE_INVENTORY")
            data["grants"][actor][scope_name] = rows
    data["cosmos_roles"] = cli(config, ["cosmosdb", "sql", "role", "assignment", "list",
        "--account-name", config["cosmos"].rsplit("/", 1)[1], "--resource-group", config["group"].rsplit("/", 1)[1]])
    data["cosmos_definitions"] = cli(config, ["cosmosdb", "sql", "role", "definition", "list",
        "--account-name", config["cosmos"].rsplit("/", 1)[1], "--resource-group", config["group"].rsplit("/", 1)[1]])
    definitions = {}
    for actor in data["grants"].values():
        for rows in actor.values():
            for row in rows:
                role = row["roleDefinitionId"]
                if role not in definitions:
                    definitions[role] = get(config, role, "2022-04-01")
    data["role_definitions"] = definitions
    return data


def covers(scope, target):
    return (isinstance(scope, str) and bool(scope) and isinstance(target, str)
            and (same(scope, target) or target.lower().startswith(scope.lower().rstrip("/") + "/")))


def role_actions(config, data, actor, scope):
    actions = set()
    for grant in data["grants"][actor][scope]:
        if not covers(grant.get("scope", ""), config[scope]):
            continue
        require(not grant.get("condition"), "CONDITIONAL_ROLE_REQUIRES_REVIEW")
        definition = data["role_definitions"].get(grant["roleDefinitionId"], {}).get("properties", {})
        for permission in definition.get("permissions", []):
            # Narrow known built-ins below use their recorded names; custom job role
            # is checked against explicit actions and cannot silently include exclusions.
            if not permission.get("notActions"):
                actions.update(permission.get("actions", []))
    return actions


def has_role(config, data, actor, scope, names):
    ids = {BUILTIN_ROLES[name] for name in names}
    return any(row.get("roleDefinitionId", "").rsplit("/", 1)[-1].lower() in ids and not row.get("condition")
               and covers(row.get("scope", ""), config[scope])
               for row in data["grants"][actor][scope])


def validate(config, data):
    for key in VERSIONS:
        require(isinstance(data.get(key), dict) and isinstance(data[key].get("properties", {}), dict), "STANDING_RESPONSE_SHAPE")
        require(same(data[key].get("id"), config[key]), "TARGET_MISMATCH_" + key)
        if key not in ("group", "app_identity", "worker_identity"):
            require(data[key].get("properties", {}).get("provisioningState") == "Succeeded", "STANDING_NOT_READY")
    account = data["account"]
    require(same(account.get("id"), config["subscription"]) and same(account.get("tenantId"), config["tenant"]), "ACTIVE_CONTEXT")
    user = account.get("user") or {}
    require(user.get("type") == "servicePrincipal" and same(user.get("name"), config["executor_client"]), "EXECUTOR_CONTEXT")
    require(same(data["executor_identity"].get("principalId"), config["executor"])
            and same(data["executor_identity"].get("clientId"), config["executor_client"]), "EXECUTOR_IDENTITY_MAPPING")
    require(same(data["database"].get("id"), config["cosmos"] + "/sqlDatabases/" + config["database"]), "DATABASE_SCOPE")
    registry = data["registry"]["properties"]
    require(registry.get("roleAssignmentMode") == "LegacyRegistryPermissions"
            and registry.get("adminUserEnabled") is False, "REGISTRY_CONTRACT")
    require(registry.get("loginServer") == config["registry_host"], "REGISTRY_HOST_MISMATCH")
    require(endpoint(data["cosmos"]["properties"]["documentEndpoint"]) == config["cosmos_endpoint"], "COSMOS_ENDPOINT")
    require(endpoint(data["storage"]["properties"]["primaryEndpoints"]["blob"]) == config["storage_endpoint"], "STORAGE_ENDPOINT")
    require(data["cosmos"]["properties"].get("disableLocalAuth") is True
            and data["storage"]["properties"].get("allowSharedKeyAccess") is False, "KEYLESS_STANDING")
    app = data["app_identity"]["properties"]
    worker = data["worker_identity"]["properties"]
    require(len({app["principalId"].lower(), worker["principalId"].lower(), config["executor"].lower()}) == 3, "DISTINCT_PRINCIPALS")
    require(same(app.get("tenantId"), config["tenant"]) and same(worker.get("tenantId"), config["tenant"]), "IDENTITY_TENANT")
    require(has_role(config, data, "executor", "group", {"Contributor"}), "EXECUTOR_RG_CONTRIBUTOR")
    require(has_role(config, data, "executor", "registry", {"AcrPush"}), "EXECUTOR_PUSH")
    for actor in ("executor", "app", "worker"):
        require(has_role(config, data, actor, "storage", {"Storage Blob Data Contributor"}), "STANDING_BLOB_ACCESS_" + actor)
    for actor in ("app", "worker"):
        require(has_role(config, data, actor, "registry", {"AcrPull", "AcrPush"}), "STANDING_PULL_" + actor)
    require(JOB_ACTIONS <= role_actions(config, data, "app", "group"), "STANDING_JOB_OPERATOR")
    definitions = {d["id"].lower(): d for d in data["cosmos_definitions"]}
    db_scope = config["cosmos"] + "/dbs/" + config["database"]
    for actor, principal in (("executor", config["executor"]), ("app", app["principalId"]), ("worker", worker["principalId"])):
        matched = [r for r in data["cosmos_roles"] if same(r.get("principalId"), principal)
                   and covers(r.get("scope", ""), db_scope)]
        actions = {a for r in matched for p in definitions.get(r["roleDefinitionId"].lower(), {}).get("permissions", [])
                   for a in p.get("dataActions", [])}
        required = {"Microsoft.DocumentDB/databaseAccounts/readMetadata",
                    "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read",
                    "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery"}
        if actor != "executor":
            required.add("Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*")
        require(all(a in actions or (a.startswith("Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/")
                    and "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*" in actions)
                    for a in required), "STANDING_COSMOS_ACCESS_" + actor)
    return {"app": app, "worker": worker, "registry": registry,
            "location": data["environment"]["location"].replace(" ", "").lower()}


def owned(config):
    group, run = config["group"], config["run_id"]
    storage = config["storage"] + "/blobServices/default/containers/"
    return {
        "app": (group + "/providers/Microsoft.App/containerApps/ci-smoke-mcp-jobs-" + run, "2024-03-01"),
        "job": (group + "/providers/Microsoft.App/jobs/ci-smoke-mcp-jobs-worker-" + run, "2026-01-01"),
        "control": (config["cosmos"] + "/sqlDatabases/" + config["database"] + "/containers/ci-smoke-mcp-jobs-task-" + run, "2024-11-15"),
        "output": (storage + "mcpjobs-" + run, "2023-01-01"),
        "callbacks": (storage + "mcpjobs-" + run + "-callbacks", "2023-01-01"),
    }


def check(config, *, absent=False, evidence_dir=None):
    snapshot = observations(config)
    if evidence_dir is not None:
        write_new(evidence_dir / f"ci-preflight-{time.time_ns()}.json", {
            "observed_at": datetime.now(timezone.utc).isoformat(), "observations": snapshot,
        })
    details = validate(config, snapshot)
    if absent:
        for resource_id, version in owned(config).values():
            require(get(config, resource_id, version, absent=True) is None, "RUN_TARGET_ALREADY_EXISTS")
        # Freeze one new repository/tag before any build; no retained/shared repo.
        repos = cli(config, ["acr", "repository", "list", "--name", config["registry"].rsplit("/", 1)[1]])
        require(isinstance(repos, list) and all(image_repository(config, hosted) not in repos
                for hosted in (False, True)), "IMAGE_REPOSITORY_ALREADY_EXISTS")
    return details


def prepare(project, config):
    require(project.is_dir(), "STAGED_PROJECT_REQUIRED")
    details = check(config, absent=True, evidence_dir=project)
    parameters = {
        "location": details["location"], "runId": config["run_id"], "environmentId": config["environment"],
        "acrServer": details["registry"]["loginServer"], "appIdentityId": config["app_identity"],
        "workerIdentityId": config["worker_identity"], "appClientId": details["app"]["clientId"],
        "workerClientId": details["worker"]["clientId"], "workerPrincipalId": details["worker"]["principalId"],
        "callerPrincipalId": config["executor"], "authClientId": config["audience"],
        "cosmosAccountName": config["cosmos"].rsplit("/", 1)[1], "cosmosEndpoint": config["cosmos_endpoint"],
        "cosmosDatabaseName": config["database"], "storageAccountName": config["storage"].rsplit("/", 1)[1],
        "storageAccountUrl": config["storage_endpoint"],
    }
    # This dedicated staged tree opts in; ordinary templates are never edited.
    write_new(project / "ci-reuse.json", config)
    write_new(project / "ci-run-owned.json", {"config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
              "absent_before": {key: rid for key, (rid, _) in owned(config).items()},
              "image_repositories_absent_before": [image_repository(config), image_repository(config, True)],
              "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()})
    azure_yaml = project / "azure.yaml"
    manifest = azure_yaml.read_text()
    anchor = "      context: .\n"
    require(manifest.count(anchor) == 1, "CANONICAL_AZD_SERVICE_SHAPE")
    azure_yaml.write_text(manifest.replace(anchor, anchor +
        f"      registry: {config['registry_host']}\n"
        f"      image: {image_repository(config)}\n"
        "      tag: run\n"))
    (project / "infra/main.bicep").write_bytes((project / "infra/ci-reuse.bicep").read_bytes())
    (project / "infra/main.parameters.json").write_text(json.dumps({
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0", "parameters": {k: {"value": v} for k, v in parameters.items()},
    }, indent=2))
    write_new(project / "ci-stage.json", {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
              for name in ("infra/main.bicep", "infra/main.parameters.json")})
    return parameters


def check_staged_target(project, config):
    expected = {
        "AZURE_SUBSCRIPTION_ID": config["subscription"], "AZURE_TENANT_ID": config["tenant"],
        "AZURE_RESOURCE_GROUP": config["group"].rsplit("/", 1)[1], "ACR_LOGIN_SERVER": config["registry_host"],
        "MCP_ACA_JOBS_COSMOS_DATABASE": config["database"],
        "MCP_ACA_JOBS_COSMOS_ENDPOINT": config["cosmos_endpoint"],
        "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": config["storage_endpoint"],
    }
    result = subprocess.run(["azd", "env", "get-values", "--output", "json"], cwd=project,
                            capture_output=True, text=True, timeout=30, check=True)
    actual = json.loads(result.stdout, object_pairs_hook=unique)
    require(isinstance(actual, dict) and all(actual.get(k) == v for k, v in expected.items()), "AZD_TARGET_DRIFT")
    hashes = load(project / "ci-stage.json")
    require(set(hashes) == {"infra/main.bicep", "infra/main.parameters.json"}, "STAGED_GRAPH_DRIFT")
    require(all(hashlib.sha256((project / name).read_bytes()).hexdigest() == digest
                for name, digest in hashes.items()), "STAGED_GRAPH_DRIFT")


def image_repository(config, hosted=False):
    return ("ci-smoke-mcp-jobs-hosted-" if hosted else "ci-smoke-mcp-jobs-") + config["run_id"]


def image_metadata(config, *, absent=False, hosted=False):
    return cli(config, ["acr", "manifest", "show-metadata", "--registry",
                       config["registry"].rsplit("/", 1)[1], "--name", image_repository(config, hosted) + ":run"], absent=absent)


def record_image(project, config, *, hosted=False):
    cleanup_plan(config, load(project / "ci-run-owned.json"))
    item = image_metadata(config, hosted=hosted)
    require(isinstance(item, dict) and re.fullmatch(r"sha256:[0-9a-f]{64}", item.get("digest", "")), "IMAGE_RECEIPT")
    require(item.get("tags") == ["run"], "IMAGE_TAG_OWNERSHIP")
    write_new(project / ("ci-hosted-image.json" if hosted else "ci-image.json"),
              {"repository": image_repository(config, hosted), "digest": item["digest"]})


def record_created(project, config):
    manifest = load(project / "ci-run-owned.json")
    cleanup_plan(config, manifest)
    created = {}
    for name, (resource_id, version) in owned(config).items():
        item = get(config, resource_id, version, absent=True)
        if item is None:
            continue
        require(same(item.get("id"), resource_id), "CREATED_TARGET_MISMATCH")
        started = datetime.fromisoformat(manifest["observed_at"])
        stamp = (item.get("systemData") or {}).get("createdAt")
        require(isinstance(stamp, str) and datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= started,
                "CREATION_OWNERSHIP_UNVERIFIED")
        created[name] = {"id": resource_id, "created_at": stamp}
    write_new(project / "ci-created.json", created)


def cleanup_plan(config, manifest):
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    expected = {key: rid for key, (rid, _) in owned(config).items()}
    require(manifest.get("config_sha256") == digest and manifest.get("absent_before") == expected, "OWNERSHIP_MANIFEST_MISMATCH")
    require(manifest.get("image_repositories_absent_before") ==
            [image_repository(config), image_repository(config, True)], "IMAGE_PREWRITE_CUSTODY")
    return [(name, *owned(config)[name]) for name in ("job", "app", "control", "callbacks", "output")]


def cleanup(config, manifest, created):
    plan = cleanup_plan(config, manifest)
    require(isinstance(created, dict) and set(created) <= set(owned(config)), "UNREGISTERED_CLEANUP_TARGET")
    for name, resource_id, version in plan:
        if name not in created:
            require(get(config, resource_id, version, absent=True) is None, "UNREGISTERED_RESOURCE_PRESENT")
            continue
        require(same(created[name].get("id"), resource_id), "UNREGISTERED_CLEANUP_TARGET")
        current = get(config, resource_id, version, absent=True)
        if current is None:
            continue
        require(same(current.get("id"), resource_id), "CLEANUP_TARGET_MISMATCH")
        require((current.get("systemData") or {}).get("createdAt") == created[name].get("created_at"),
                "CLEANUP_RESOURCE_REPLACED")
        # Ownership needs both the recorded pre-write absence and exact expected
        # deployed bindings; names alone do not justify deleting a shared object.
        if name in ("app", "job"):
            identity = config["app_identity" if name == "app" else "worker_identity"]
            require(identity in (current.get("identity", {}).get("userAssignedIdentities") or {}), "CLEANUP_IDENTITY_MISMATCH")
            props = current["properties"]
            require(same(props.get("environmentId") or props.get("managedEnvironmentId"), config["environment"]), "CLEANUP_ENVIRONMENT_MISMATCH")
        cli(config, ["rest", "--method", "delete", "--url",
                     f"https://management.azure.com{resource_id}?api-version={version}"])
        for _ in range(12):
            if get(config, resource_id, version, absent=True) is None:
                break
            time.sleep(5)
        else:
            raise ReuseError("CLEANUP_ABSENCE_UNVERIFIED")


def cleanup_image(config, image, *, hosted=False):
    require(image.get("repository") == image_repository(config, hosted)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", image.get("digest", "")), "IMAGE_OWNERSHIP_MANIFEST")
    actual = image_metadata(config, absent=True, hosted=hosted)
    if actual is None:
        return
    require(actual.get("digest") == image["digest"] and actual.get("tags") == ["run"], "IMAGE_CHANGED")
    cli(config, ["acr", "repository", "delete", "--name", config["registry"].rsplit("/", 1)[1],
                 "--image", image["repository"] + "@" + image["digest"], "--yes"])
    require(image_metadata(config, absent=True, hosted=hosted) is None, "IMAGE_ABSENCE_UNVERIFIED")


def invoke_once(client, kind, options):
    """Fixture invocation custody; SDK and application retries are both disabled."""
    from operation_evidence import begin_operation, capture_response, error_metadata
    require(kind in ("prompt", "hosted"), "INVOKE_KIND")
    path = Path(f"ci-{kind}-operation.jsonl")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        def record(event, fields):
            output.write(json.dumps({"event": event, **fields}) + "\n")
            output.flush()
            os.fsync(output.fileno())
        begin_operation(record, target=str(client.base_url), intent={"kind": kind, "options": options})
        try:
            bounded = client.with_options(max_retries=0, timeout=180)
            raw = bounded.responses.with_raw_response.create(**options)
            return capture_response(raw, record)
        except Exception as error:
            record("unresolved", error_metadata(error))
            raise ReuseError("INVOKE_OUTCOME_UNKNOWN_NO_REPLAY") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "record", "record-image", "cleanup", "cleanup-image"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--hosted-image", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            config = settings(os.environ, args.run_id)
            prepare(args.project, config)
        else:
            config = load(args.project / "ci-reuse.json")
            # Revalidate config shape and exact shell context; no default selection.
            expected = settings({**os.environ, "MCP_ACA_JOBS_CI_REUSE": "existing"}, config["run_id"])
            require(config == expected, "STANDING_INPUT_DRIFT")
            if args.action == "check":
                check_staged_target(args.project, config)
                check(config, evidence_dir=args.project)
            elif args.action == "record":
                record_created(args.project, config)
            elif args.action == "record-image":
                record_image(args.project, config, hosted=args.hosted_image)
            else:
                require(args.execute, "CLEANUP_EXECUTION_NOT_APPROVED")
                check(config, evidence_dir=args.project)
                manifest = load(args.project / "ci-run-owned.json")
                if args.action == "cleanup-image":
                    cleanup_plan(config, manifest)
                    if args.hosted_image:
                        require(load(args.project / "ci-hosted-deleted.json") ==
                                {"name": image_repository(config, True), "version": "1", "absent": True},
                                "HOSTED_IMAGE_STILL_DEPLOYED")
                    # Delete the image only after both consumers are absent.
                    for key in ("app", "job"):
                        rid, version = owned(config)[key]
                        require(get(config, rid, version, absent=True) is None, "IMAGE_STILL_DEPLOYED")
                    cleanup_image(config, load(args.project / ("ci-hosted-image.json" if args.hosted_image else "ci-image.json")),
                                  hosted=args.hosted_image)
                else:
                    cleanup(config, manifest, load(args.project / "ci-created.json"))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "BLOCKED", "stage": args.action,
                          "code": str(error) if isinstance(error, ReuseError) else type(error).__name__}))
        return 1
    print("CI_REUSE_" + args.action.upper() + "_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
