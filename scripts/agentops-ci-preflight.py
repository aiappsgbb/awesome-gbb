#!/usr/bin/env python3
"""Fail-closed runtime owner-approval gate, not a native AgentOps artifact schema.

Initial invocation: --write-approval PATH reads AGENTOPS_CI_TELEMETRY_APPROVAL_JSON.
Retry invocation: --approval-file PATH needs no approval secret. Both revalidate
CI context, isolated CLI identity, routing and effective retention before PASS.
PATH and both credential directories must be under
$RUNNER_TEMP/agentops-ci-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT.
The caller owns unconditional directory cleanup
and enforcement of the approved native execution/capture/artifact policies.

Only exact-ID ARM metadata reads and `az account show` are performed. No login,
discovery, inference, roles, configuration repair or native execution is allowed.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import urlsplit
import uuid


PRIVATE_PREFIX = "agentops-ci-"
MAX_JSON_BYTES = 1024 * 1024
CLI_TIMEOUT_SECONDS = 20
ERROR_CODES = frozenset({
    "ARGUMENTS", "AZD_NOT_EMPTY", "CI_CONTEXT", "CLI_FAILED", "CLI_IDENTITY",
    "CLI_TIMEOUT", "COMPONENT_BINDING", "CONNECTION_STRING", "CREDENTIAL_ROUTE",
    "EXPIRED", "EXPORT_OVERRIDE", "IDENTITY_BINDING", "INTERNAL_ERROR",
    "INVALID_DATE", "INVALID_ENDPOINT", "INVALID_IDENTIFIER", "INVALID_INPUT",
    "INVALID_JSON", "INVALID_RESOURCE", "METADATA", "MISSING_ENV", "MISSING_FIELD",
    "MODEL_BINDING", "OUTPUT_EXISTS", "POLICY", "PROJECT_BINDING", "PURGE_DEADLINE",
    "RECORD_CHANGED", "RESOURCE_BINDING", "ROUTING_KEY", "SCHEMA",
    "TABLE_BINDING", "TABLE_RETENTION", "TELEMETRY_BINDING", "UAMI_BINDING",
    "UNSAFE_FILE", "UNSAFE_PATH", "UNSAFE_PERMISSIONS", "WORKSPACE_BINDING", "WORKSPACE_QUOTA",
})
TABLES = (
    "AppAvailabilityResults", "AppBrowserTimings", "AppDependencies", "AppEvents",
    "AppExceptions", "AppMetrics", "AppPageViews", "AppPerformanceCounters",
    "AppRequests", "AppSystemEvents", "AppTraces", "AppGenAIContent",
)
SOURCES = ("results_history", "azure_monitor", "foundry_control", "azure_resources")

# These are normative schema-v1 policy clauses, not free-form audit annotations.
POLICY = {
    "authorization": {
        "status": "approved", "event_name": "pull_request", "merge_release_authorized": False,
    },
    "identity": {"credential_route": "ci-cli"},
    "foundry": {
        "project_selection": "Use the existing CI project endpoint only after exact membership validation; do not change projects or infer a default",
        "existing_workloads_must_remain_unchanged": True,
    },
    "telemetry": {
        "retention_in_days": 30, "total_retention_in_days": 30,
        "immediate_purge_data_on_30_days": True, "daily_quota_gb": 0.1,
        "quota_is_not_a_hard_cost_or_ingestion_guarantee": True,
        "retention_authority": "Linked workspace and explicit table analytical/total retention; the legacy component RetentionInDays field is not authoritative",
        "export_scope": "Only these dedicated telemetry destinations and private runner-local native artifacts are approved; no shared telemetry secret fallback",
        "public_network_access": "Required for the existing GitHub-hosted runner; no private-network or Citadel changes",
        "ingestion_auth": "Native connection-string routing on the dedicated component; not permission to add an ingestion/write role or use inference API keys",
        "shared_secret_replacement_authorized": False,
    },
    "source_scope": {
        "azure_monitor_lookback_days": 1, "azure_monitor_query_count": 4,
        "azure_monitor_aggregate_only": True, "azure_monitor_has_no_run_filter": True,
        "historical_aggregates_are_not_current_run_ingestion_proof": True,
        "shared_resource_repairs_authorized": False,
    },
    "capture": {
        "synthetic_only": True, "synthetic_dataset_rows": 1,
        "existing_user_conversations_authorized": False,
        "native_prompt_response_tool_content_and_findings": "Approved only for the synthetic fixture; includes evaluation/Doctor judge inputs, native logs, evidence and any native Azure Monitor export",
        "full_doctor_required": True, "quality_failure_must_remain_failure": True,
        "unverified_coverage_must_remain_unverified": True,
        "retry_to_obtain_green_authorized": False,
        "other_telemetry_or_judge_destinations_authorized": False,
    },
    "storage_and_cleanup": {
        "responses_service_storage": "Operator accepts applicable native Foundry Responses service retention for the single synthetic fixture response; this is separate from Azure Monitor retention",
        "individual_response_purge_proven": False, "native_response_id_loss_limitation_accepted": True,
        "agent_deletion_does_not_prove_response_purge": True,
        "delete_only_fixture_owned_agents_and_versions": True,
        "preserve_existing_model_deployments": True,
        "runner_credentials_and_approval_file": "Private directories and approval file mode0600; remove in unconditional cleanup; never print or upload",
        "raw_artifact_access": "Restricted workflow/operator access only; raw native artifacts may contain the synthetic content and resource metadata",
        "public_artifacts": "Only sanitized summaries and source/artifact hashes; never approval record, connection string or credentials",
        "azure_monitor_retention_is_not_an_exact_physical_purge_deadline": True,
    },
}
VARIABLE_FIELDS = {
    "authorization": {"basis", "repository", "pull_request", "head_branch", "expires_at", "purpose"},
    "identity": {"tenant_id", "subscription_id", "client_id", "principal_id", "resource_id"},
    "foundry": {"account_resource_id", "allowed_project_endpoints", "agent_model_deployment",
                "eval_judge_deployment", "doctor_judge_deployment"},
    "telemetry": {"component_resource_id", "application_id", "workspace_resource_id",
                  "workspace_customer_id", "location", "ingestion_endpoint", "live_endpoint",
                  "retention_tables", "access"},
    "source_scope": {"enabled"},
    "capture": set(),
    "storage_and_cleanup": {"raw_artifact_purge_by"},
}


class PreflightError(Exception):
    """Carries only a code selected by this module, never input or CLI output."""


def require(condition, code):
    if not condition:
        raise PreflightError(code)


def exact(actual, expected, code):
    require(type(actual) is type(expected) and actual == expected, code)


def same_arm_id(actual, expected, code):
    """Compare the whole ID against validated approval, allowing only ASCII case."""
    require(type(actual) is str and type(expected) is str and
            actual.isascii() and expected.isascii() and actual.lower() == expected.lower(), code)


def text(value, code):
    require(isinstance(value, str) and bool(value.strip()), code)
    return value


def field(value, *keys):
    for key in keys:
        require(isinstance(value, dict) and key in value, "MISSING_FIELD")
        value = value[key]
    return value


def required_env(environ, name):
    return text(environ.get(name), "MISSING_ENV")


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "INVALID_JSON")
            result[key] = value
        return result

    def constant(_):
        raise PreflightError("INVALID_JSON")

    require(isinstance(raw, str) and len(raw.encode("utf-8")) <= MAX_JSON_BYTES, "INVALID_JSON")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError):
        raise PreflightError("INVALID_JSON") from None


def utc_date(value):
    require(isinstance(value, str) and
            re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value), "INVALID_DATE")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise PreflightError("INVALID_DATE") from None


def guid(value):
    text(value, "INVALID_IDENTIFIER")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise PreflightError("INVALID_IDENTIFIER") from None
    require(str(parsed) == value.lower(), "INVALID_IDENTIFIER")


def arm_resource(value, subscription, provider, kind):
    text(value, "INVALID_RESOURCE")
    pattern = (
        r"/subscriptions/" + re.escape(subscription) +
        r"/resourceGroups/([A-Za-z0-9_.()-]+)/providers/" +
        re.escape(provider) + "/" + re.escape(kind) + r"/([A-Za-z0-9_.()-]+)"
    )
    match = re.fullmatch(pattern, value, flags=re.IGNORECASE)
    require(match is not None, "INVALID_RESOURCE")
    return match.group(1), match.group(2)


def https_endpoint(value):
    text(value, "INVALID_ENDPOINT")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and
            not parsed.password and parsed.port is None and not parsed.query and
            not parsed.fragment and not any(char.isspace() for char in value), "INVALID_ENDPOINT")
    return parsed


def string_set(value, expected, code):
    require(isinstance(value, list) and all(isinstance(item, str) for item in value), code)
    require(len(value) == len(expected) and set(value) == set(expected), code)


def validate_record(record, now):
    require(isinstance(record, dict) and set(record) == {"schema_version", *POLICY}, "SCHEMA")
    exact(record["schema_version"], 1, "SCHEMA")
    for group, policies in POLICY.items():
        values = record[group]
        require(isinstance(values, dict) and
                set(values) == set(policies) | VARIABLE_FIELDS[group], "SCHEMA")
        for key, expected in policies.items():
            exact(values[key], expected, "POLICY")
    auth, identity, foundry, telemetry, storage = (
        record["authorization"], record["identity"], record["foundry"],
        record["telemetry"], record["storage_and_cleanup"],
    )
    for key in ("basis", "purpose", "repository", "head_branch"):
        text(auth[key], "SCHEMA")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", auth["repository"]), "SCHEMA")
    require(type(auth["pull_request"]) is int and auth["pull_request"] > 0, "SCHEMA")
    expiry, purge = utc_date(auth["expires_at"]), utc_date(storage["raw_artifact_purge_by"])
    require(now.tzinfo is not None and expiry > now, "EXPIRED")
    require(purge > now and purge >= expiry, "PURGE_DEADLINE")
    for key in ("tenant_id", "subscription_id", "client_id", "principal_id"):
        guid(identity[key])
    rg, _ = arm_resource(identity["resource_id"], identity["subscription_id"],
                         "Microsoft.ManagedIdentity", "userAssignedIdentities")
    _, account = arm_resource(foundry["account_resource_id"], identity["subscription_id"],
                              "Microsoft.CognitiveServices", "accounts")
    arm_resource(telemetry["component_resource_id"], identity["subscription_id"],
                 "Microsoft.Insights", "components")
    arm_resource(telemetry["workspace_resource_id"], identity["subscription_id"],
                 "Microsoft.OperationalInsights", "workspaces")
    endpoints = foundry["allowed_project_endpoints"]
    require(isinstance(endpoints, list) and 1 <= len(endpoints) <= 16, "SCHEMA")
    require(all(isinstance(endpoint, str) for endpoint in endpoints) and
            len(set(endpoints)) == len(endpoints), "SCHEMA")
    for endpoint in endpoints:
        https_endpoint(endpoint)
        require(re.fullmatch(
            r"https://" + re.escape(account) +
            r"\.services\.ai\.azure\.com/api/projects/[A-Za-z0-9_-]+", endpoint
        ), "PROJECT_BINDING")
    for key in ("agent_model_deployment", "eval_judge_deployment", "doctor_judge_deployment"):
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", text(foundry[key], "SCHEMA")), "SCHEMA")
    for key in ("application_id", "workspace_customer_id"):
        guid(telemetry[key])
    text(telemetry["location"], "SCHEMA")
    for key in ("ingestion_endpoint", "live_endpoint"):
        https_endpoint(telemetry[key])
    string_set(telemetry["retention_tables"], TABLES, "POLICY")
    string_set(record["source_scope"]["enabled"], SOURCES, "POLICY")
    access = (
        "Existing subscription/resource-group inherited Azure RBAC, including CI UAMI Contributor on " +
        rg + "; this is not exclusive access for the CI principal. Parent retained a private readback of "
    )
    suffix = (
        " inherited assignments. No new roles were added; any additional roles require separate "
        "verification and are restricted to read access on these two new resources"
    )
    require(re.fullmatch(re.escape(access) + r"(0|[1-9][0-9]*)" + re.escape(suffix),
                         text(telemetry["access"], "POLICY")), "POLICY")


def absolute_path(value):
    text(value, "UNSAFE_PATH")
    require(value.startswith("/") and not any(part in (".", "..") for part in value.split("/")),
            "UNSAFE_PATH")
    return Path(value)


@contextmanager
def directory_fd(path, private_root=None, *, create=False, missing_ok=False):
    """Walk using no-follow directory descriptors, including every ancestor."""
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        walked = Path("/")
        for part in path.parts[1:]:
            walked /= part
            private = private_root is not None and walked.is_relative_to(private_root)
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if create and private:
                    os.mkdir(part, 0o700, dir_fd=fd)
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                elif missing_ok and private:
                    yield None
                    return
                else:
                    raise PreflightError("UNSAFE_PATH") from None
            os.close(fd)
            fd = child
            if private:
                info = os.fstat(fd)
                require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                        "UNSAFE_PERMISSIONS")
        yield fd
    finally:
        os.close(fd)


def regular_file(info, private):
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "UNSAFE_FILE")
    if private:
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                "UNSAFE_PERMISSIONS")


def read_file(path, private_root=None):
    with directory_fd(path.parent, private_root) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            regular_file(os.fstat(stream.fileno()), private_root is not None)
            raw = stream.read(MAX_JSON_BYTES + 1)
            require(len(raw) <= MAX_JSON_BYTES, "INVALID_JSON")
            return raw.decode("utf-8")


def inspect_output(path, private_root):
    with directory_fd(path.parent, private_root, missing_ok=True) as parent:
        if parent is not None:
            try:
                info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            regular_file(info, True)
            raise PreflightError("OUTPUT_EXISTS")


def validate_azure_cache(fd):
    """Inspect cache entries without reading credentials or following links."""
    with os.scandir(fd) as entries:
        for entry in entries:
            info = entry.stat(follow_symlinks=False)
            require(not stat.S_ISLNK(info.st_mode), "UNSAFE_FILE")
            if stat.S_ISDIR(info.st_mode):
                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=fd)
                try:
                    validate_azure_cache(child)
                finally:
                    os.close(child)


def validate_paths(path, environ, write):
    runner = absolute_path(required_env(environ, "RUNNER_TEMP"))
    run = required_env(environ, "GITHUB_RUN_ID")
    attempt = required_env(environ, "GITHUB_RUN_ATTEMPT")
    require(re.fullmatch(r"[1-9][0-9]*", run) and re.fullmatch(r"[1-9][0-9]*", attempt),
            "CI_CONTEXT")
    private_root = runner / f"{PRIVATE_PREFIX}{run}-{attempt}"
    require(path.is_relative_to(private_root) and path != private_root, "UNSAFE_PATH")
    azure = absolute_path(required_env(environ, "AZURE_CONFIG_DIR"))
    azd = absolute_path(required_env(environ, "AZD_CONFIG_DIR"))
    for config in (azure, azd):
        require(config.is_relative_to(private_root) and config != private_root, "UNSAFE_PATH")
        require(not path.is_relative_to(config) and not config.is_relative_to(path), "UNSAFE_PATH")
        with directory_fd(config, private_root) as fd:
            if config == azure:
                validate_azure_cache(fd)
    require(not azure.is_relative_to(azd) and not azd.is_relative_to(azure), "UNSAFE_PATH")
    with directory_fd(azd, private_root) as fd:
        require(not os.listdir(fd), "AZD_NOT_EMPTY")
    if write:
        inspect_output(path, private_root)
    return private_root


def write_private(path, private_root, raw):
    with directory_fd(path.parent, private_root, create=True) as parent:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        info = os.fstat(fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                regular_file(os.fstat(stream.fileno()), True)
                stream.write(raw.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            # Delete only the inode this invocation created, never a replacement.
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino):
                os.unlink(path.name, dir_fd=parent)
            raise


def validate_context(record, environ):
    auth = record["authorization"]
    exact(required_env(environ, "GITHUB_REPOSITORY"), auth["repository"], "CI_CONTEXT")
    exact(required_env(environ, "GITHUB_EVENT_NAME"), "pull_request", "CI_CONTEXT")
    event = parse_json(read_file(absolute_path(required_env(environ, "GITHUB_EVENT_PATH"))))
    for keys, expected in (
        (("number",), auth["pull_request"]),
        (("repository", "full_name"), auth["repository"]),
        (("pull_request", "number"), auth["pull_request"]),
        (("pull_request", "base", "repo", "full_name"), auth["repository"]),
        (("pull_request", "head", "repo", "full_name"), auth["repository"]),
        (("pull_request", "head", "ref"), auth["head_branch"]),
    ):
        exact(field(event, *keys), expected, "CI_CONTEXT")
    identity, foundry, telemetry = record["identity"], record["foundry"], record["telemetry"]
    for env, key in (("AZURE_TENANT_ID", "tenant_id"), ("AZURE_SUBSCRIPTION_ID", "subscription_id"),
                     ("AZURE_CLIENT_ID", "client_id")):
        exact(required_env(environ, env), identity[key], "IDENTITY_BINDING")
    exact(required_env(environ, "AZURE_TOKEN_CREDENTIALS"), "AzureCliCredential", "CREDENTIAL_ROUTE")
    endpoint = required_env(environ, "FOUNDRY_PROJECT_ENDPOINT")
    require(endpoint in foundry["allowed_project_endpoints"], "PROJECT_BINDING")
    project_id = foundry["account_resource_id"] + "/projects/" + endpoint.rsplit("/", 1)[1]
    same_arm_id(required_env(environ, "AZURE_AI_PROJECT_ID"), project_id, "PROJECT_BINDING")
    for key in ("agent_model_deployment", "eval_judge_deployment", "doctor_judge_deployment"):
        exact(required_env(environ, "FOUNDRY_MODEL_DEPLOYMENT"), foundry[key], "MODEL_BINDING")
    exact(required_env(environ, "LAW_WORKSPACE_ID"), telemetry["workspace_customer_id"], "WORKSPACE_BINDING")
    if "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT" in environ:
        exact(environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"], endpoint, "PROJECT_BINDING")
    if "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING" in environ:
        exact(environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"], "false", "EXPORT_OVERRIDE")
    allowed = {
        "APPLICATIONINSIGHTS_CONNECTION_STRING", "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING",
        "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON",
    }
    for name in environ:
        if name in allowed:
            continue
        if (name.startswith(("OTEL_", "AZURE_MONITOR_", "APPLICATIONINSIGHTS_", "APPINSIGHTS_")) or
            (name.startswith("AGENTOPS_") and any(
                token in name for token in ("OTLP", "TELEMETRY", "EXPORT", "APPLICATIONINSIGHTS")
            ))):
            raise PreflightError("EXPORT_OVERRIDE")
    routing = parse_connection(required_env(environ, "APPLICATIONINSIGHTS_CONNECTION_STRING"))
    if "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING" in environ:
        require(parse_connection(environ["AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING"]) == routing,
                "EXPORT_OVERRIDE")
    validate_routing(routing, telemetry)
    return routing


def parse_connection(value):
    text(value, "CONNECTION_STRING")
    result = {}
    for segment in value.split(";"):
        if not segment:
            continue
        key, separator, item = segment.partition("=")
        key = key.lower()
        require(separator and item and key not in result, "CONNECTION_STRING")
        result[key] = item
    require(set(result) == {"instrumentationkey", "ingestionendpoint", "liveendpoint", "applicationid"},
            "CONNECTION_STRING")
    guid(result["instrumentationkey"])
    guid(result["applicationid"])
    https_endpoint(result["ingestionendpoint"])
    https_endpoint(result["liveendpoint"])
    return result


def validate_routing(routing, telemetry):
    for key, approved in (("applicationid", "application_id"), ("ingestionendpoint", "ingestion_endpoint"),
                          ("liveendpoint", "live_endpoint")):
        exact(routing[key], telemetry[approved], "TELEMETRY_BINDING")


def cli_read_json(argv, environ):
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, check=True,
            timeout=CLI_TIMEOUT_SECONDS, env=environ,
        )
    except subprocess.TimeoutExpired:
        raise PreflightError("CLI_TIMEOUT") from None
    except (subprocess.SubprocessError, OSError):
        raise PreflightError("CLI_FAILED") from None
    return parse_json(result.stdout)


def validate_metadata(record, routing, read_json):
    def read(argv):
        try:
            result = read_json(argv)
        except PreflightError:
            raise
        except subprocess.TimeoutExpired:
            raise PreflightError("CLI_TIMEOUT") from None
        except Exception:
            # This is an untrusted CLI/JSON boundary: errors always deny, never default.
            raise PreflightError("CLI_FAILED") from None
        require(isinstance(result, dict), "METADATA")
        return result

    def resource(resource_id, api):
        result = read(["az", "resource", "show", "--ids", resource_id, "--api-version", api, "-o", "json"])
        same_arm_id(field(result, "id"), resource_id, "RESOURCE_BINDING")
        return result

    identity, telemetry = record["identity"], record["telemetry"]
    account = read(["az", "account", "show", "-o", "json"])
    for keys, expected in (
        (("id",), identity["subscription_id"]), (("tenantId",), identity["tenant_id"]),
        (("user", "type"), "servicePrincipal"), (("user", "name"), identity["client_id"]),
    ):
        exact(field(account, *keys), expected, "CLI_IDENTITY")
    uami = resource(identity["resource_id"], "2023-01-31")
    for actual, approved in (("tenantId", "tenant_id"), ("clientId", "client_id"),
                             ("principalId", "principal_id")):
        exact(field(uami, "properties", actual), identity[approved], "UAMI_BINDING")
    component = resource(telemetry["component_resource_id"], "2020-02-02")
    for keys, expected in (
        (("location",), telemetry["location"]),
        (("properties", "AppId"), telemetry["application_id"]),
    ):
        exact(field(component, *keys), expected, "COMPONENT_BINDING")
    same_arm_id(field(component, "properties", "WorkspaceResourceId"),
                telemetry["workspace_resource_id"], "COMPONENT_BINDING")
    component_routing = parse_connection(field(component, "properties", "ConnectionString"))
    validate_routing(component_routing, telemetry)
    actual_key = text(field(component, "properties", "InstrumentationKey"), "CONNECTION_STRING")
    require(hmac.compare_digest(routing["instrumentationkey"], actual_key) and
            hmac.compare_digest(component_routing["instrumentationkey"], actual_key), "ROUTING_KEY")
    workspace = resource(telemetry["workspace_resource_id"], "2023-09-01")
    for keys, expected in (
        (("location",), telemetry["location"]),
        (("properties", "customerId"), telemetry["workspace_customer_id"]),
        (("properties", "retentionInDays"), 30),
        (("properties", "features", "immediatePurgeDataOn30Days"), True),
    ):
        exact(field(workspace, *keys), expected, "WORKSPACE_BINDING")
    quota = field(workspace, "properties", "workspaceCapping", "dailyQuotaGb")
    require(type(quota) in (int, float) and math.isfinite(quota) and quota == 0.1, "WORKSPACE_QUOTA")
    # Workspace/table policy is authoritative; component RetentionInDays may be 90.
    for table in telemetry["retention_tables"]:
        metadata = resource(telemetry["workspace_resource_id"] + "/tables/" + table, "2022-10-01")
        exact(field(metadata, "name"), table, "TABLE_BINDING")
        for key in ("retentionInDays", "totalRetentionInDays"):
            exact(field(metadata, "properties", key), 30, "TABLE_RETENTION")


def main(argv=None, *, environ=None, read_json=None, now=None):
    try:
        args = sys.argv[1:] if argv is None else argv
        require(len(args) == 2 and args[0] in ("--write-approval", "--approval-file"), "ARGUMENTS")
        env = dict(os.environ if environ is None else environ)
        write = args[0] == "--write-approval"
        path = absolute_path(args[1])
        private_root = validate_paths(path, env, write)
        raw = (required_env(env, "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON") if write
               else read_file(path, private_root))
        record = parse_json(raw)
        validate_record(record, now if now is not None else datetime.now(timezone.utc))
        routing = validate_context(record, env)
        validate_metadata(record, routing, read_json if read_json is not None
                          else lambda argv: cli_read_json(argv, env))
        # Recheck private paths and deadlines after bounded but potentially slow reads.
        validate_paths(path, env, write)
        validate_record(record, now if now is not None else datetime.now(timezone.utc))
        if not write:
            exact(read_file(path, private_root), raw, "RECORD_CHANGED")
        if write:
            write_private(path, private_root, raw)
    except PreflightError as exc:
        code = exc.args[0] if len(exc.args) == 1 else None
        if not isinstance(code, str) or code not in ERROR_CODES:
            code = "INTERNAL_ERROR"
        print("AGENTOPS_CI_PREFLIGHT=FAIL " + code)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        print("AGENTOPS_CI_PREFLIGHT=FAIL INVALID_INPUT")
        return 1
    except Exception:
        # A programming fault must not emit a traceback containing private inputs.
        print("AGENTOPS_CI_PREFLIGHT=FAIL INTERNAL_ERROR")
        return 1
    print("AGENTOPS_CI_PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
