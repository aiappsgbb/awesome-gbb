"""Canonical read-only hosted deployment evidence gate.

Source of truth for the prose example in `../../SKILL.md § Deployment preflight`.
Consumes operator-owned JSON observations; never calls Azure, runs subprocesses,
repairs resources, or authenticates. A passing setup is NOT hosted execution.
See ../deployment-preflight.md for collection, trust boundary and schema.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


CONNECTIONS = (
    "threadStorageConnections", "vectorStoreConnections",
    "storageConnections", "aiServicesConnections",
)
BASIC_MODULE = (
    "skills/foundry-vnet-deploy/templates/basic-vnet/"
    "modules-network-secured/add-project-capability-host.bicep"
)
MAX_AGE_SECONDS = 1800


class GateError(ValueError):
    def __init__(self, code: str, scope: str, action: str):
        super().__init__(code)
        self.issue = {"code": code, "scope": scope, "action": action}


def require(condition: bool, code: str, scope: str, action: str) -> None:
    if not condition:
        raise GateError(code, scope, action)


def obj(value: object) -> dict:
    require(isinstance(value, dict), "INPUT", "evidence", "Supply a JSON object per the documented schema.")
    return value


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def immutable_image(value: object) -> bool:
    return text(value) and re.fullmatch(r"[^/\s]+/[^@\s:]+@sha256:[0-9a-f]{64}", value) is not None


def same_id(actual: object, expected: str) -> bool:
    return isinstance(actual, str) and actual.lower() == expected.lower()


def timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return result


def fresh(value: object, now: datetime) -> bool:
    try:
        return 0 <= (now - timestamp(value)).total_seconds() <= MAX_AGE_SECONDS
    except (ValueError, TypeError, OverflowError):
        return False


def receipt(value: object) -> bool:
    return isinstance(value, dict) and value.get("result") == "pass" and text(value.get("evidence"))


def failure(error: GateError) -> dict:
    return {"status": "BLOCKED", "live_execution": "NOT_PROVEN", "issues": [error.issue]}


def host_list(value: object, scope: str) -> list:
    require(
        isinstance(value, dict) and isinstance(value.get("value"), list)
        and not value.get("nextLink") and "error" not in value,
        "HOST_INVENTORY", scope,
        "Collect the complete successful GET inventory (all pages). A failed read is not an empty inventory.",
    )
    return value["value"]


def check_host(hosts: list, scope: str, kind: str, required: bool) -> dict | None:
    missing_action = (
        f"Stop registration. Obtain explicit authorization to create ONLY the missing project host using {BASIC_MODULE}; read back Agents/Succeeded."
        if kind == "PROJECT" else
        "Stop registration. Review the selected Standard account-host module with foundry-caphost-lifecycle; no automatic creation."
    )
    require(not required or bool(hosts), f"{kind}_HOST_MISSING", scope, missing_action)
    if not hosts:
        return None
    require(len(hosts) == 1 and isinstance(hosts[0], dict), f"{kind}_HOST_INVALID", scope,
            "Preserve all hosts. Resolve ambiguous inventory before registration.")
    host = hosts[0]
    host_id = host.get("id", "")
    properties = obj(host.get("properties"))
    require(
        isinstance(host_id, str) and host_id.lower().startswith(scope.lower() + "/")
        and "/" not in host_id[len(scope) + 1:] and len(host_id) > len(scope) + 1
        and properties.get("capabilityHostKind") == "Agents"
        and properties.get("provisioningState") == "Succeeded",
        f"{kind}_HOST_INVALID", scope,
        "Read the exact host GET/error. Preserve it; bound any in-flight wait. No recreate/delete as troubleshooting.",
    )
    return properties


def connections(properties: dict) -> dict:
    result = {}
    for key in CONNECTIONS:
        values = properties.get(key)
        if values is None:
            values = []
        require(isinstance(values, list) and all(text(v) for v in values),
                "HOST_CONNECTIONS", key, "Read connection names without credentials; do not rewrite the host.")
        result[key] = sorted(values)
    return result


def check_setup(data: object, *, now: datetime | None = None) -> dict:
    """Validate a fresh snapshot. First blocker wins; input remains unchanged."""
    now = now or datetime.now(timezone.utc)
    try:
        data = obj(data)
        require(data.get("schema_version") == 1, "INPUT", "evidence", "Use schema_version 1.")
        require(fresh(data.get("observed_at"), now), "EVIDENCE_AGE", "evidence",
                "Recollect all observations within 30 minutes; use the oldest observation timestamp, not file-save time.")
        target = obj(data.get("target"))
        mode = target.get("mode")
        require(isinstance(mode, str) and mode in {"basic-private", "standard-private", "managed-public"},
                "MODE", "target.mode", "Select a documented setup mode; other/legacy/raw-public paths require explicit contract review.")
        private = mode != "managed-public"
        ids = {}
        for key, segment in (("account", "/accounts/"), ("project", "/projects/"),
                             ("model", "/deployments/"), ("registry", "/registries/")):
            expected = target.get(key + "_id")
            require(text(expected) and expected.startswith("/subscriptions/") and segment in expected,
                    "INPUT", key, "Supply the approved full resource ID; never discover a default.")
            ids[key] = expected
            actual = obj(data.get(key))
            require(same_id(actual.get("id"), expected), "RESOURCE_SCOPE", expected,
                    "Read the exact approved resource, not a sibling or cached default.")
            require(obj(actual.get("properties")).get("provisioningState") == "Succeeded",
                    "RESOURCE_STATE", expected, "Inspect the exact resource error/state; stop until Succeeded. Do not recreate.")
        for key, segment in (("project", "/projects/"), ("model", "/deployments/")):
            prefix = ids["account"] + segment
            require(ids[key].lower().startswith(prefix.lower()) and "/" not in ids[key][len(prefix):],
                    "RESOURCE_SCOPE", ids[key], "Bind the project/model to the selected account.")
        endpoint = target.get("project_endpoint")
        endpoints = obj(data["project"]["properties"].get("endpoints"))
        require(text(endpoint) and endpoint.startswith("https://") and endpoint in endpoints.values(),
                "PROJECT_ENDPOINT", ids["project"],
                "Read the selected project's data-plane endpoint; do not borrow another project endpoint.")
        account = obj(data["account"]["properties"])
        require(data["account"].get("kind") == "AIServices", "ACCOUNT_KIND", ids["account"],
                "Use the approved Foundry AIServices account; a model-only OpenAI account is not hosted setup.")
        injections = account.get("networkInjections")
        if injections is None:
            injections = []
        if private:
            subnet = target.get("subnet_id")
            require(text(subnet) and account.get("publicNetworkAccess") == "Disabled"
                    and isinstance(injections, list) and any(
                        isinstance(i, dict) and i.get("scenario") == "agent"
                        and same_id(i.get("subnetArmId"), subnet)
                        and i.get("useMicrosoftManagedNetwork") is False for i in injections),
                    "NETWORK_MODE", ids["account"],
                    "Verify the original private agent injection/subnet. Do not enable public access or retrofit injection.")
        else:
            require(account.get("publicNetworkAccess") == "Enabled" and injections == [],
                    "NETWORK_MODE", ids["account"],
                    "managed-public is only the selected public/platform-managed azd route, not a bypass for private setup.")
        project_scope = ids["project"] + "/capabilityHosts"
        account_scope = ids["account"] + "/capabilityHosts"
        project_hosts = host_list(data.get("project_hosts"), project_scope)
        account_hosts = host_list(data.get("account_hosts"), account_scope)
        account_host = check_host(account_hosts, account_scope, "ACCOUNT", mode == "standard-private")
        if mode == "standard-private" and not project_hosts:
            raise GateError("PROJECT_HOST_MISSING", project_scope,
                            "Obtain explicit authorization for the Standard project-host module and approved BYO connections; never use Basic as a fallback.")
        project_host = check_host(project_hosts, project_scope, "PROJECT", private)
        expected_connections = connections(obj(target.get("connections")))
        if mode == "standard-private":
            require(all(expected_connections[k] for k in CONNECTIONS[:3])
                    and same_id(account_host.get("customerSubnet"), target["subnet_id"]),
                    "HOST_CONNECTIONS", account_scope,
                    "Verify the Standard account subnet and approved BYO connection names; preserve all stores.")
        else:
            require(not any(expected_connections.values()), "HOST_CONNECTIONS", project_scope,
                    "Basic/platform-managed does not select BYO stores; stop for an explicit mode decision.")
        if project_host is not None:
            require(connections(project_host) == expected_connections, "HOST_CONNECTIONS", project_scope,
                    "Existing host differs from selected mode/BYO names. Preserve hosts, connections and stores; request an explicit decision.")
        if mode != "standard-private" and account_host is not None:
            require(not any(connections(account_host).values()), "HOST_CONNECTIONS", account_scope,
                    "Existing account BYO defaults are not Basic. Preserve them and resolve mode explicitly.")
        registry = obj(data["registry"]["properties"])
        image = target.get("image")
        require(immutable_image(image),
                "IMAGE", ids["registry"], "Freeze an immutable repository@sha256 digest before registration/signing.")
        registry_host, repository = image.split("@", 1)[0].split("/", 1)
        require(registry.get("loginServer") == registry_host, "IMAGE", ids["registry"],
                "Use the digest in the selected registry; image changes require a new observation and signed association.")
        registry_network = target.get("registry_network")
        require(registry_network in ("private", "public")
                and registry.get("publicNetworkAccess") == ("Disabled" if registry_network == "private" else "Enabled"),
                "ACR_NETWORK", ids["registry"],
                "Match the approved registry network boundary. Do not expose a private registry to pass preflight.")
        if registry["publicNetworkAccess"] == "Disabled":
            created = obj(data["project"].get("systemData")).get("createdAt")
            try:
                created_date = timestamp(created).astimezone(timezone.utc).date()
            except (ValueError, TypeError, OverflowError):
                created_date = None
            require(created_date is not None and created_date > datetime(2026, 6, 25).date(),
                    "PRIVATE_ACR_GENERATION", ids["project"],
                    "Verify project creation AFTER June 25, 2026 (Learn checked 2026-09-12). Boundary/older/unknown: stop for supported-route review; do not expose ACR.")
        policy = obj(obj(registry.get("policies")).get("azureADAuthenticationAsArmPolicy"))
        require(policy.get("status") == "enabled", "ACR_POLICY", ids["registry"],
                "Have the registry owner verify azureADAuthenticationAsArmPolicy; no automatic policy change.")
        registry_mode = registry.get("roleAssignmentMode")
        require(isinstance(registry_mode, str), "ACR_PULL", ids["registry"],
                "Read roleAssignmentMode before choosing a pull role.")
        role = {"AbacRepositoryPermissions": "Container Registry Repository Reader",
                "LegacyRegistryPermissions": "AcrPull"}.get(registry_mode)
        pull = obj(data.get("pull"))
        principal = obj(data["project"].get("identity")).get("principalId")
        require(role is not None and text(principal) and receipt(pull)
                and pull.get("principal_id") == principal and same_id(pull.get("scope"), ids["registry"])
                and pull.get("role") == role and pull.get("repository") == repository
                and pull.get("condition_allows_repository") is True,
                "ACR_PULL", ids["registry"],
                "Verify the project MI's mode-appropriate pull role at registry scope and any ABAC condition for this repository. Agent/operator access is not pull proof.")
        probes = data.get("probes")
        tools = target.get("tool_endpoints")
        require(isinstance(probes, list) and isinstance(tools, list) and all(text(t) for t in tools)
                and all(text(target.get(k)) for k in ("operator_route", "runtime_route", "project_endpoint")),
                "PATH_UNVERIFIED", ids["project"], "List the actual operator and runtime routes and every requested tool endpoint.")
        required_probes = [
            ("operator-project", target["project_endpoint"], target["operator_route"]),
            ("runtime-model", ids["model"], target["runtime_route"]),
            ("registry-network", image, target["runtime_route"]),
            *(("runtime-tool", tool, target["runtime_route"]) for tool in tools),
        ]
        for purpose, destination, route in required_probes:
            matching = [p for p in probes if isinstance(p, dict) and p.get("purpose") == purpose
                        and p.get("target") == destination and p.get("route") == route]
            require(len(matching) == 1 and receipt(matching[0])
                    and matching[0].get("network_reachable" if purpose == "registry-network" else "authenticated") is True
                    and matching[0].get("tls_verified") is True,
                    "PATH_UNVERIFIED", destination,
                    f"Collect one unambiguous current {purpose} DNS/TLS and applicable authentication receipt from {route}; conflicting/duplicate evidence and unavailable paths stay blocked.")
        runtime = obj(data.get("runtime"))
        require(receipt(runtime) and runtime.get("image") == image
                and runtime.get("platform") == "linux/amd64" and runtime.get("container_user") == ""
                and runtime.get("session_home") == "/home/session" and runtime.get("session_home_writable") is True
                and runtime.get("session_home_check") in ("local-candidate", "hosted-session")
                and runtime.get("protocol") == "responses" and runtime.get("protocol_version") == "2.0.0"
                and text(runtime.get("cohort_reference")) and runtime.get("cohort_verified") is True
                and runtime.get("management_environment_separate") is True,
                "RUNTIME", image,
                "Verify this image: default UID, writable native session home, linux/amd64, Responses 2.0.0 and selected tested runtime cohort in a separate environment. Do not guess new pins or chmod platform mounts.")
        environment = obj(data.get("environment_variables"))
        require(all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()),
                "INPUT", "environment_variables", "Supply the user-declared string map, excluding injected values.")
        reserved = [k for k in environment if k.startswith(("FOUNDRY_", "AGENT_"))
                    or k == "APPLICATIONINSIGHTS_CONNECTION_STRING"]
        require(not reserved, "RESERVED_ENV", "environment_variables",
                "Remove user-declared FOUNDRY_*, AGENT_* and APPLICATIONINSIGHTS_CONNECTION_STRING; never echo their values.")
        model_env = target.get("model_env")
        require(text(model_env) and environment.get(model_env) == ids["model"].rsplit("/", 1)[1],
                "MODEL_BINDING", ids["model"],
                "Set the selected runtime model environment key to this deployment's name, not a model SKU or another deployment.")
        registration = obj(data.get("registration"))
        require(registration.get("path") in ("sdk", "azd") and text(registration.get("evidence"))
                and obj(registration.get("metadata")).get("enableVnextExperience") == "true",
                "REGISTRATION", ids["project"],
                "Compare the frozen creation request with the selected native azd contract, including metadata.enableVnextExperience='true'. A metadata correction is not provisioning proof.")
        return {
            "status": "READY_FOR_REGISTRATION", "live_execution": "NOT_TESTED", "issues": [],
            "pending_live_checks": [
                "project-mi-platform-pull", "native-session-home", "hosted-model-and-tool-access",
                "direct-version-readiness", "endpoint-routing", "requested-business-result",
            ],
        }
    except GateError as error:
        return failure(error)


def check_execution(data: object, *, now: datetime | None = None) -> dict:
    """Check recorded execution evidence, never derive readiness from LIST."""
    now = now or datetime.now(timezone.utc)
    try:
        data = obj(data)
        require(fresh(data.get("observed_at"), now), "EVIDENCE_AGE", "execution evidence",
                "Recollect current endpoint/invocation/business evidence; use the oldest included observation timestamp.")
        binding = {key: data.get(key) for key in ("version", "image", "identity")}
        require(all(text(v) for v in binding.values()), "BINDING", "version",
                "Record actual version, immutable image and hosted identity; do not substitute VM identity.")
        require(immutable_image(binding["image"]), "IMAGE", "version",
                "Record the immutable image digest, not matching mutable tags across receipts.")
        observations = data.get("observations")
        require(isinstance(observations, list) and len(observations) >= 2,
                "VERSION_GET", "version", "Collect two consecutive direct version GETs; LIST is inventory only.")
        previous_time = None
        for observation in observations:
            require(isinstance(observation, dict), "VERSION_GET", str(binding["version"]),
                    "Retain well-formed chronological observations; malformed history cannot establish the latest state.")
            try:
                observed_time = timestamp(observation.get("observed_at"))
            except (ValueError, TypeError, OverflowError):
                raise GateError("VERSION_GET", str(binding["version"]),
                                "Every observation needs a timezone-aware timestamp; unknown history cannot be skipped.")
            require(previous_time is None or previous_time < observed_time,
                    "VERSION_GET", str(binding["version"]),
                    "Supply strictly chronological distinct observations; out-of-order history may conceal a newer failure.")
            previous_time = observed_time
        selected = observations[-2:]
        for observation in selected:
            require(isinstance(observation, dict) and observation.get("source") == "direct-version-get"
                    and observation.get("status") == "active" and not observation.get("error")
                    and all(observation.get(k) == v for k, v in binding.items())
                    and fresh(observation.get("observed_at"), now),
                    "VERSION_GET", str(binding["version"]),
                    "Preserve the direct GET state/error and all artifacts. Failed/unknown beats LIST active; bound waiting, never recreate automatically.")
        for key in ("endpoint", "invocation"):
            value = obj(data.get(key))
            require(receipt(value) and all(value.get(k) == v for k, v in binding.items()),
                    "EXECUTION", key, "Observe exact endpoint routing and an authenticated invocation of the selected version/identity/image.")
        invocation = data["invocation"]
        require(text(invocation.get("response_id")) and text(invocation.get("session_id")),
                "EXECUTION", "invocation", "Retain actual response/session identifiers; health or startup alone is not invocation.")
        hosted = obj(data.get("hosted_runtime"))
        require(receipt(hosted) and all(hosted.get(k) == v for k, v in binding.items())
                and hosted.get("session_id") == invocation["session_id"]
                and hosted.get("native_session_home_writable") is True,
                "HOSTED_RUNTIME", "native session",
                "Verify the actual hosted session mount for this image/identity; local-candidate checks do not prove it.")
        business = obj(data.get("business"))
        require(receipt(business) and business.get("response_id") == invocation["response_id"]
                and all(text(business.get(k)) for k in ("tool_call_id", "audit_id"))
                and business.get("requested_result_verified") is True,
                "BUSINESS_PROOF", "requested operation",
                "Match the real requested tool result to its response, tool call and independent audit. Empty/noop/assistant prose is not business proof.")
        return {"status": "BUSINESS_PROOF_RECORDED", "live_execution": "RECORDED_NOT_INDEPENDENTLY_VERIFIED", "issues": []}
    except GateError as error:
        return failure(error)


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--phase", choices=("setup", "execution"), default="setup")
    args = parser.parse_args()
    try:
        data = json.loads(args.evidence.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, ValueError):
        result = failure(GateError("INPUT", "evidence file",
                                   "Supply readable UTF-8 JSON with unique keys; do not include credentials."))
    else:
        result = (check_setup if args.phase == "setup" else check_execution)(data)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
