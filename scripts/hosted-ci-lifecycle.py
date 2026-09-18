#!/usr/bin/env python3
"""Runner-owned Hosted/GHCP reconciliation. Never treats azd output as a CREATE ACK."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
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
from uuid import uuid4


spec = importlib.util.spec_from_file_location(
    "mcp_aca_lifecycle", Path(__file__).with_name("mcp-aca-ci-lifecycle.py"))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
require, Error = common.require, common.LifecycleError
SKILLS = {"foundry-hosted-agents": ("ci-smoke-ha-", "responses", 1),
          "ghcp-hosted-agents": ("ci-smoke-ghcp-", "invocations", 6)}
ROLE = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
ROLE_API = "2022-04-01"
DIGEST = r"sha256:[0-9a-f]{64}"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def approval(env, raw=None):
    a = common.parse(env.get("HOSTED_CI_LIFECYCLE_APPROVAL_JSON", "") if raw is None else raw)
    require(isinstance(a, dict) and set(a) == {
        "schema_version", "skill", "repository", "sha", "run_id", "run_attempt",
        "tenant_id", "client_id", "project_id", "project_endpoint", "acr_server",
        "model", "expires_at", "retain_until", "age_recipient", "owner", "purpose",
        "delete_reconciled_native_objects", "retain_images_identities_and_stored_responses",
        "temporary_foundry_user_grants",
    }, "APPROVAL")
    require(type(a["schema_version"]) is int and a["schema_version"] == 1, "APPROVAL")
    require(a["skill"] in SKILLS and a["skill"] == env.get("HOSTED_CI_SKILL"), "CONTEXT")
    for key, variable in (
        ("repository", "GITHUB_REPOSITORY"), ("sha", "GITHUB_SHA"),
        ("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT"),
        ("tenant_id", "AZURE_TENANT_ID"), ("client_id", "AZURE_CLIENT_ID"),
        ("project_id", "AZURE_AI_PROJECT_ID"), ("project_endpoint", "FOUNDRY_PROJECT_ENDPOINT"),
        ("acr_server", "ACR_LOGIN_SERVER"),
    ):
        require(isinstance(a[key], str) and a[key] and a[key] == env.get(variable), "CONTEXT")
    require(re.fullmatch(r"[0-9a-f]{40}", a["sha"]) and
            all(re.fullmatch(r"[1-9][0-9]*", a[k]) for k in ("run_id", "run_attempt")), "CONTEXT")
    subscription = env.get("AZURE_SUBSCRIPTION_ID", "")
    require(re.fullmatch(common.GUID, subscription) and
            all(re.fullmatch(common.GUID, a[k]) for k in ("tenant_id", "client_id")), "SCOPE")
    require(re.fullmatch(
        rf"/subscriptions/{subscription}/resourceGroups/[A-Za-z0-9_.()-]+"
        r"/providers/Microsoft.CognitiveServices/accounts/[a-zA-Z0-9-]+/projects/[a-zA-Z0-9_-]+",
        a["project_id"]), "SCOPE")
    project_name = a["project_id"].rsplit("/", 1)[1]
    require(re.fullmatch(r"https://[a-z0-9-]+\.services\.ai\.azure\.com/api/projects/" +
                         re.escape(project_name), a["project_endpoint"]), "SCOPE")
    require(re.fullmatch(r"[a-z0-9]+\.azurecr\.io", a["acr_server"]) and
            a["model"] == "gpt-5.4-mini", "SCOPE")
    require(a["delete_reconciled_native_objects"] is True and
            a["retain_images_identities_and_stored_responses"] is True, "APPROVAL")
    require(type(a["temporary_foundry_user_grants"]) is bool and
            a["temporary_foundry_user_grants"] == (a["skill"] == "ghcp-hosted-agents"), "APPROVAL")
    require(all(isinstance(a[k], str) and a[k].strip() for k in ("owner", "purpose")), "APPROVAL")
    now = common.utc_now()
    expiry, retention = common.utc(a["expires_at"]), common.utc(a["retain_until"])
    require(now < expiry <= now + timedelta(hours=24) and
            expiry <= retention <= now + timedelta(days=7), "EXPIRED")
    require(re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", a["age_recipient"]), "CUSTODY")
    return a


def root(env):
    require(env.get("HOSTED_CI_SKILL") in SKILLS, "CONTEXT")
    base = Path(env["RUNNER_TEMP"])
    require(base.is_absolute() and base.resolve() == base, "PATH")
    require(all(re.fullmatch(r"[1-9][0-9]*", env.get(k, ""))
                for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "CONTEXT")
    path = base / f"hosted-lifecycle-{env['HOSTED_CI_SKILL']}-{env['GITHUB_RUN_ID']}-{env['GITHUB_RUN_ATTEMPT']}"
    require(not path.is_symlink(), "PATH")
    return path


class Ledger:
    def __init__(self, path, approved, env):
        self.path, self.a, self.env = path, common.parse(json.dumps(approved)), env
        self.data = common.parse(common.private_read(path / "receipt.json"))
        self.validate_custody()

    def validate_custody(self):
        require(self.data.get("approval") == self.a and
                self.data.get("approval_sha256") == fingerprint(self.a), "CUSTODY")
        require(self.data.get("context") == {
            k: self.a[k] for k in ("skill", "sha", "run_id", "run_attempt")
        }, "CONTEXT")

    def save(self):
        self.validate_custody()
        common.write(self.path / "receipt.json", self.data)
        common.encrypt(self.path, self.a, self.env)

    def state(self, value):
        self.data["state"] = value
        self.save()


@contextmanager
def exclusive(path):
    # A process lock, not a deletable sentinel: runner loss releases it, durable
    # intent in receipt.json still prohibits another build/deploy/DELETE.
    import fcntl
    fd = os.open(path / "process.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                stat.S_IMODE(info.st_mode) == 0o600, "PATH")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Error("CONCURRENT_PROCESS") from None
        yield
    finally:
        os.close(fd)


class Native:
    """A fresh CLI token and retry-disabled SDK client per bounded operation."""

    def __init__(self, env, approved):
        self.env, self.a = env, approved

    @contextmanager
    def client(self, mutate=False):
        from azure.ai.projects import AIProjectClient
        from azure.core.credentials import AccessToken
        from azure.identity import AzureCliCredential
        common.Arm(self.env)  # Verify the active CLI identity, not just env claims.
        # CLI rejects --tenant together with --subscription. Arm above already
        # verified the subscription's tenant and service-principal identity.
        with AzureCliCredential(subscription=self.env["AZURE_SUBSCRIPTION_ID"],
                                process_timeout=20) as credential:
            token = credential.get_token("https://ai.azure.com/.default")
        class FrozenCredential:
            def get_token(self, *scopes, **kwargs):
                require(scopes == ("https://ai.azure.com/.default",), "CREDENTIAL_SCOPE")
                if mutate:
                    common.require_lifetime(self_approval, 300)
                return AccessToken(token.token, token.expires_on)
        self_approval = self.a
        # Token acquisition is complete before the mutation's lifetime check.
        if mutate:
            common.require_lifetime(self.a, 300)
        with AIProjectClient(endpoint=self.a["project_endpoint"], credential=FrozenCredential(),
                             retry_total=0, redirect_max=0, connection_timeout=20,
                             read_timeout=20) as project:
            yield project.agents

    def call(self, method, *, before_send=None, **kwargs):
        from azure.core.exceptions import AzureError, ResourceNotFoundError
        require(method != "update_details" or before_send is not None, "ROUTING_GUARD")
        try:
            with self.client(mutate=method.startswith("delete") or method == "update_details") as agents:
                if before_send:
                    before_send()
                    common.require_lifetime(self.a, 300)
                return getattr(agents, method)(**kwargs)
        except ResourceNotFoundError as error:
            require(error.status_code == 404, "ABSENCE_UNPROVEN")
            raise Error("NATIVE_NOT_FOUND") from None
        except AzureError:
            raise Error("NATIVE_REQUEST") from None

    def absent(self, method, **kwargs):
        try:
            self.call(method, **kwargs)
        except Error as error:
            if str(error) == "NATIVE_NOT_FOUND":
                return True
            raise
        return False

    def inventory(self, kind, name):
        from azure.core.exceptions import AzureError
        deadline = time.monotonic() + 120
        result = []
        try:
            with self.client() as agents:
                pages = iter(getattr(agents, "list_" + kind)(agent_name=name).by_page())
                for _ in range(4):
                    require(time.monotonic() < deadline, "INVENTORY_LIMIT")
                    page = next(pages, None)
                    require(time.monotonic() < deadline, "INVENTORY_LIMIT")
                    if page is None:
                        return result
                    for item in page:
                        require(time.monotonic() < deadline and len(result) < 6, "INVENTORY_LIMIT")
                        result.append(item)
        except AzureError:
            raise Error("INVENTORY_UNKNOWN") from None
        raise Error("INVENTORY_LIMIT")


def version_binding(version, ledger):
    data = ledger.data
    require(version.name == data["agent"] and isinstance(version.version, str) and
            re.fullmatch(r"[1-9][0-9]*", version.version), "VERSION")
    definition = version.definition.as_dict()
    # The service may add this empty legacy field alongside protocol_versions.
    # Do not discard a populated/null field or change the required protocol.
    if "container_protocol_versions" not in data["definition"] and "container_protocol_versions" in definition:
        require(definition["container_protocol_versions"] == [], "DEFINITION_CHANGED")
        definition = {k: v for k, v in definition.items() if k != "container_protocol_versions"}
    require(definition == data["definition"] and
            definition["container_configuration"]["image"] == data["image"], "DEFINITION_CHANGED")
    identity = version.instance_identity.as_dict() if version.instance_identity else {}
    require(all(isinstance(identity.get(k), str) and re.fullmatch(common.GUID, identity[k])
                for k in ("principal_id", "client_id")), "IDENTITY_UNKNOWN")
    require((version.metadata or {}).get("enableVnextExperience") == "true", "VERSION")
    require(isinstance(version.id, str) and version.id and
            isinstance(version.created_at, datetime) and version.created_at.tzinfo is not None, "VERSION")
    created = version.created_at.timestamp()
    require(int(common.utc(data["deploy_started_at"]).timestamp()) <= created <=
            common.utc_now().timestamp() + 2, "CREATION_TIME")
    return {"version": version.version, "version_id": version.id,
            "created_at": version.created_at.isoformat(), "definition_sha256": fingerprint(definition),
            "identity": identity}


def agent_binding(native, name):
    agent = native.call("get", agent_name=name)
    identity = agent.instance_identity.as_dict() if agent.instance_identity else {}
    require(agent.name == name and isinstance(agent.id, str) and agent.id and
            re.fullmatch(common.GUID, identity.get("principal_id", "")), "IDENTITY_UNKNOWN")
    blueprint = agent.blueprint.as_dict() if agent.blueprint else None
    return {"id": agent.id, "identity": identity, "blueprint": blueprint}


def reconcile(ledger, native):
    require(ledger.data.get("pre_get_404") is True and ledger.data.get("deploy_intent") is True, "OWNERSHIP_UNKNOWN")
    versions = native.inventory("versions", ledger.data["agent"])
    require(len(versions) == 1, "OWNERSHIP_UNKNOWN")
    version = native.call("get_version", agent_name=ledger.data["agent"], agent_version=versions[0].version)
    binding = version_binding(version, ledger)
    require(ledger.data.get("binding", binding) == binding, "OWNERSHIP_CHANGED")
    second = native.call("get_version", agent_name=ledger.data["agent"], agent_version=version.version)
    require(version_binding(second, ledger) == binding, "OWNERSHIP_CHANGED")
    agent = agent_binding(native, ledger.data["agent"])
    require(agent["identity"] == binding["identity"] and
            ledger.data.get("agent_binding", agent) == agent, "OWNERSHIP_CHANGED")
    ledger.data["agent_binding"] = agent
    ledger.data["binding"] = binding
    ledger.state("RECONCILED_OWNERSHIP")


def command(argv, env, cwd, seconds=1200):
    result = subprocess.run(argv, env=env, cwd=cwd, capture_output=True,
                            timeout=seconds, check=False)
    require(result.returncode == 0, "COMMAND_FAILED")
    require(len(result.stdout) <= common.MAX_BYTES, "SIZE")
    return result.stdout


def azd_environment(env, project, name, expected_env, published=None):
    """Validate the pinned azd local state before invoking its env reader."""
    root = project / ".azure"
    directories = {root, root / name}
    required = {root / "config.json", root / name / ".env"}
    optional = {
        root / ".gitignore": b"# .azure is not intended to be committed\n*",
        root / name / ".env.lock": b"",
        root / name / "config.json": None,
    }
    for path in directories:
        require(not path.is_symlink() and path.is_dir(), "SOURCE")
    paths = list(root.rglob("*"))
    require(required <= set(paths), "SOURCE")
    for path in paths:
        info = path.lstat()
        if path in directories:
            require(stat.S_ISDIR(info.st_mode), "SOURCE")
            continue
        require(path in required or path in optional, "SOURCE")
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                info.st_size <= common.MAX_BYTES, "SOURCE")
        if path in optional:
            raw = path.read_bytes()
            require(common.parse(raw) == {} if optional[path] is None else raw == optional[path], "SOURCE")
    config = common.parse((root / "config.json").read_bytes())
    require(config == {"version": 1, "defaultEnvironment": name}, "AZD_ENV")
    lines = (root / name / ".env").read_text().splitlines()
    wanted = dict(expected_env)
    image_key = "SERVICE_" + name.upper().replace("-", "_") + "_IMAGE_NAME"
    if published is not None and any(
            line in (f"{image_key}={published}", f'{image_key}="{published}"') for line in lines):
        wanted[image_key] = published
    require(len(lines) == len(wanted) and all(
        sum(line in (f"{key}={value}", f'{key}="{value}"') for line in lines) == 1
        for key, value in wanted.items()), "AZD_ENV")
    actual = common.parse(command(["azd", "env", "get-values", "--output", "json"], env, project, 20))
    require(isinstance(actual, dict) and actual == wanted, "AZD_ENV")


def source(env, a, name, project, published=None):
    require(re.fullmatch(re.escape(SKILLS[a["skill"]][0]) + r"[0-9a-f]{32}", name), "AGENT_NAME")
    require(project.is_absolute() and project.resolve() == project, "PATH")
    from_path = {"Dockerfile": "docker/Dockerfile", "container.py": "python/container.py",
                 "pyproject.toml": "python/pyproject.toml", "azure.yaml": "yaml/azure.yaml"}
    if a["skill"] == "ghcp-hosted-agents":
        from_path.update(Dockerfile="Dockerfile", **{"container.py": "container.py", "pyproject.toml": "pyproject.toml"})
    require({p.name for p in project.iterdir()} <= {*from_path, "copilot-instructions.md", ".azure"}, "SOURCE")
    safe_env = {k: v for k, v in env.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    safe_env["GIT_NO_REPLACE_OBJECTS"] = "1"
    hashes = {}
    for target, relative in from_path.items():
        expected = command(["git", "show", f"{a['sha']}:skills/{a['skill']}/references/{relative}"],
                           safe_env, env["GITHUB_WORKSPACE"], 10)
        if target == "azure.yaml":
            expected = expected.replace(b"  my-agent:\n", f"  {name}:\n".encode(), 1)
            expected = expected.replace(b"    name: my-agent\n", f"    name: {name}\n".encode(), 1)
        path = project / target
        require(not path.is_symlink() and path.read_bytes() == expected, "SOURCE")
        hashes[target] = hashlib.sha256(expected).hexdigest()
    instructions = project / "copilot-instructions.md"
    require(not instructions.is_symlink(), "SOURCE")
    if a["skill"] == "foundry-hosted-agents":
        require(instructions.read_bytes() == b"You are a customer-support triage assistant.\n", "SOURCE")
        hashes["copilot-instructions.md"] = hashlib.sha256(instructions.read_bytes()).hexdigest()
    else:
        require(not instructions.exists(), "SOURCE")
    expected_env = {
        "AZURE_ENV_NAME": name, "AZURE_SUBSCRIPTION_ID": env["AZURE_SUBSCRIPTION_ID"],
        "FOUNDRY_PROJECT_ENDPOINT": a["project_endpoint"], "AZURE_AI_PROJECT_ID": a["project_id"],
        "AZURE_CONTAINER_REGISTRY_ENDPOINT": a["acr_server"], "AZURE_AI_MODEL_DEPLOYMENT_NAME": a["model"],
    }
    azd_environment(env, project, name, expected_env, published)
    return hashes


def package_receipt(raw, agent):
    data = common.parse(raw)
    require(isinstance(data, dict) and set(data.get("services", {})) == {agent}, "PACKAGE")
    artifacts = data["services"][agent].get("artifacts")
    require(isinstance(artifacts, list) and all(
        isinstance(item, dict) and item.get("kind") in ("container", "config") for item in artifacts), "PACKAGE")
    containers = [item for item in artifacts if item["kind"] == "container"]
    require(len(containers) == 1, "PACKAGE")
    item = containers[0]
    location, metadata = item.get("location"), item.get("metadata", {})
    require(item.get("locationKind") == "local" and isinstance(location, str) and
            re.fullmatch(r"[a-z0-9/._-]+:[A-Za-z0-9._-]+", location), "PACKAGE")
    require(location.rsplit(":", 1)[0] == f"my-agent-project/{agent}-{agent}" and
            metadata.get("targetImage") == location and metadata.get("sourceImage") == "" and
            re.fullmatch(DIGEST, metadata.get("imageHash", "")), "PACKAGE")
    return {"local_image": location, "config_digest": metadata["imageHash"],
            "package_sha256": hashlib.sha256(raw).hexdigest()}


def deploy(ledger, native, arm, project, name, *, source_check=None, environment_variables=None):
    a, env, data = ledger.a, ledger.env, ledger.data
    source_check = source if source_check is None else source_check
    require(data["state"] == "PREPARED", "RETRY_BLOCKED")
    ledger.save()
    hashes = source_check(env, a, name, project)
    require(common.parse(command(["azd", "version", "--output", "json"], env, project, 20))
            .get("azd", {}).get("version") == "1.34.1", "AZD_COMPATIBILITY")
    extensions = common.parse(command(["azd", "ext", "list", "--output", "json"], env, project, 20))
    require(isinstance(extensions, list) and any(
        item.get("id") == "azure.ai.agents" and item.get("installedVersion") == "1.0.0-beta.14"
        for item in extensions), "AZD_COMPATIBILITY")
    require(native.absent("get", agent_name=name), "PREEXISTING_OR_UNVERIFIED")
    group = a["project_id"].split("/providers/", 1)[0]
    common.require_cleanup_unlocked(arm, {"resource_group_id": group}, a["project_id"])
    data.update(agent=name, source_hashes=hashes, pre_get_404=True, image_disposition="RETAINED_OWNER_APPROVED",
                identities_disposition="RETAINED_OWNER_APPROVED",
                stored_responses_disposition="RETAINED_OWNER_APPROVED", retain_until=a["retain_until"])
    ledger.state("UNKNOWN")
    common.require_lifetime(a, 2700)
    data["package_intent"] = True
    ledger.save()
    common.require_lifetime(a, 2700)
    data["package"] = package_receipt(
        command(["azd", "package", name, "--output", "json", "--no-prompt"], env, project), name)
    data["remote_tag"] = a["acr_server"] + "/" + data["package"]["local_image"]
    ledger.save()
    repositories = common.parse(command(
        ["az", "acr", "repository", "list", "--name", a["acr_server"].split(".")[0], "-o", "json"],
        env, project, 30))
    require(isinstance(repositories, list) and all(isinstance(item, str) for item in repositories) and
            len(set(repositories)) == len(repositories) and
            data["package"]["local_image"].rsplit(":", 1)[0] not in repositories, "PUBLICATION_NAMESPACE")
    data["publication_baseline_sha256"] = fingerprint(repositories)
    common.require_lifetime(a, 1500)
    data["publish_intent"] = True
    ledger.save()
    common.require_lifetime(a, 1500)
    command(["azd", "publish", name, "--from-package", data["package"]["local_image"],
             "--to", data["remote_tag"], "--no-prompt"], env, project, 600)
    data["publish_ack"] = True
    ledger.save()
    metadata = common.parse(command(
        ["az", "acr", "manifest", "show-metadata", "--registry", a["acr_server"].split(".")[0],
         "--name", data["package"]["local_image"], "-o", "json"], env, project, 30))
    require(re.fullmatch(DIGEST, metadata.get("digest", "")), "IMAGE")
    image = data["remote_tag"].rsplit(":", 1)[0] + "@" + metadata["digest"]
    raw = command(["docker", "buildx", "imagetools", "inspect", image, "--raw"], env, project, 30)
    manifest = common.parse(raw)
    require("sha256:" + hashlib.sha256(raw).hexdigest() == metadata["digest"] and
            manifest.get("config", {}).get("digest") == data["package"]["config_digest"], "IMAGE")
    from azure.ai.projects.models import HostedAgentDefinition
    data["image"] = image
    data["definition"] = HostedAgentDefinition(
        kind="hosted", cpu="1", memory="2Gi", container_configuration={"image": image},
        environment_variables=({"AZURE_AI_MODEL_DEPLOYMENT_NAME": a["model"]}
                               if environment_variables is None else environment_variables),
        protocol_versions=[{"protocol": SKILLS[a["skill"]][1], "version": "2.0.0"}],
    ).as_dict()
    # Verify the initial source and azd context again, then make only the
    # reviewed prebuilt transformation. No hooks or additional services.
    require(source_check(env, a, name, project, data["remote_tag"]) == hashes, "SOURCE")
    import yaml
    config = yaml.safe_load((project / "azure.yaml").read_text())
    config["services"][name].update(image=image, docker={"remoteBuild": False, "imagePassthrough": True})
    (project / "azure.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    data["prebuilt_yaml_sha256"] = hashlib.sha256((project / "azure.yaml").read_bytes()).hexdigest()
    ledger.save()
    # Repeat absence immediately before the single native deploy.
    require(native.absent("get", agent_name=name), "PREEXISTING_OR_UNVERIFIED")
    common.require_lifetime(a, 1500)
    data["deploy_intent"] = True
    data["deploy_started_at"] = common.utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger.save()
    common.require_lifetime(a, 1500)
    command(["azd", "deploy", name, "--from-package", image, "--no-prompt"], env, project)
    data["azd_exit"] = 0
    ledger.save()
    reconcile(ledger, native)


def configure_routing(ledger, native):
    from azure.ai.projects.models import (
        AgentEndpointConfig, FixedRatioVersionSelectionRule, ProtocolConfiguration,
        ResponsesProtocolConfiguration, VersionSelector,
    )
    data = ledger.data
    require(ledger.a["skill"] == "foundry-hosted-agents", "SCOPE")
    require(data["state"] == "RECONCILED_OWNERSHIP" and
            data.get("binding") and data.get("agent_binding"), "OWNERSHIP_UNKNOWN")
    require(data["binding"]["version"] == "1", "VERSION")
    require(not data.get("routing_intent"), "ROUTING_ALREADY_ATTEMPTED")
    common.require_lifetime(ledger.a, 600)
    data["routing_intent"] = True
    ledger.save()

    def recheck():
        versions = native.inventory("versions", data["agent"])
        require(len(versions) == 1 and versions[0].version == data["binding"]["version"],
                "OWNERSHIP_CHANGED")
        version = native.call("get_version", agent_name=data["agent"], agent_version=data["binding"]["version"])
        require(version_binding(version, ledger) == data["binding"] and
                agent_binding(native, data["agent"]) == data["agent_binding"], "OWNERSHIP_CHANGED")
        common.require_lifetime(ledger.a, 600)

    native.call(
        "update_details", before_send=recheck, agent_name=data["agent"],
        agent_endpoint=AgentEndpointConfig(
            version_selector=VersionSelector(version_selection_rules=[
                FixedRatioVersionSelectionRule(agent_version="1", traffic_percentage=100),
            ]),
            protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration()),
        ),
    )
    data["routing_ack"] = True
    ledger.save()


def before_invoke(ledger, native):
    require(ledger.data["state"] == "RECONCILED_OWNERSHIP", "OWNERSHIP_UNKNOWN")
    if ledger.a["skill"] == "foundry-hosted-agents":
        require(ledger.data.get("routing_intent") is True and
                ledger.data.get("routing_ack") is True, "ROUTING_UNKNOWN")
    else:
        require(len(ledger.data.get("roles", [])) == 2 and all(
            item["state"] in ("OWNED", "STANDING") for item in ledger.data["roles"]), "ROLE_OWNERSHIP_UNKNOWN")
    reconcile(ledger, native)
    count = ledger.data.get("invoke_intents", 0)
    require(count < SKILLS[ledger.a["skill"]][2], "INVOKE_BUDGET")
    common.require_lifetime(ledger.a, 600)
    ledger.data["invoke_intents"] = count + 1
    ledger.save()
    common.require_lifetime(ledger.a, 600)


def role_absent(status, body):
    return status == 404 and isinstance(body, dict) and isinstance(body.get("error"), dict) and (
        body["error"].get("code") in ("RoleAssignmentDoesNotExist", "ResourceNotFound"))


def role_binding(document, scope, principal, subscription):
    resource_id, props = document.get("id"), document.get("properties")
    require(isinstance(resource_id, str) and re.fullmatch(
        re.escape(scope) + "/providers/Microsoft.Authorization/roleAssignments/" + common.GUID,
        resource_id, re.I) and isinstance(props, dict), "ROLE_BINDING")
    expected_role = f"/subscriptions/{subscription}/providers/Microsoft.Authorization/roleDefinitions/{ROLE}"
    require(str(props.get("scope", "")).lower() == scope.lower() and
            props.get("principalId") == principal and props.get("principalType") == "ServicePrincipal" and
            str(props.get("roleDefinitionId", "")).lower() == expected_role.lower() and
            props.get("condition") in (None, ""), "ROLE_BINDING")
    return {"id": resource_id, "scope": scope, "principal": principal, "role": expected_role,
            "created_on": props.get("createdOn")}


def grant_roles(ledger, native, arm):
    require(ledger.a["skill"] == "ghcp-hosted-agents" and
            ledger.a["temporary_foundry_user_grants"] is True, "APPROVAL")
    require("roles" not in ledger.data, "RETRY_BLOCKED")
    reconcile(ledger, native)
    a, data = ledger.a, ledger.data
    principal = data["binding"]["identity"]["principal_id"]
    scopes = (a["project_id"].rsplit("/projects/", 1)[0], a["project_id"])
    group = a["project_id"].split("/providers/", 1)[0]
    # Complete read-only preflight for both scopes before the first assignment.
    candidates = []
    for scope in scopes:
        common.require_cleanup_unlocked(arm, {"resource_group_id": group}, scope)
        matches = []
        for item in common.inventory(arm, scope + "/providers/Microsoft.Authorization/roleAssignments", ROLE_API):
            props = item.get("properties", {})
            if (props.get("principalId") == principal and
                    str(props.get("roleDefinitionId", "")).lower().endswith("/" + ROLE) and
                    str(props.get("scope", "")).lower() == scope.lower()):
                matches.append(role_binding(item, scope, principal, ledger.env["AZURE_SUBSCRIPTION_ID"]))
        require(len(matches) <= 1, "ROLE_AMBIGUOUS")
        candidates.append({"scope": scope, "state": "STANDING", "binding": matches[0]} if matches else {
            "scope": scope, "state": "PLANNED",
            "id": scope + "/providers/Microsoft.Authorization/roleAssignments/" + str(uuid4()),
        })
    data["roles"] = candidates
    ledger.save()
    for item in candidates:
        if item["state"] == "STANDING":
            continue
        status, body, _ = arm("GET", item["id"], ROLE_API)
        require(role_absent(status, body), "ROLE_PREEXISTING_OR_UNVERIFIED")
        item.update(state="UNKNOWN", pre_get_404=True)
        ledger.save()
        def before_create():
            status, body, _ = arm("GET", item["id"], ROLE_API)
            require(role_absent(status, body), "ROLE_PREEXISTING_OR_UNVERIFIED")
            common.require_lifetime(a, 600)
        status, body, _ = arm("PUT", item["id"], ROLE_API, role_principal=principal,
                             before_send=before_create)
        require(status == 201, "ROLE_CREATE_UNKNOWN")
        bound = role_binding(body, item["scope"], principal, ledger.env["AZURE_SUBSCRIPTION_ID"])
        require(bound["id"].lower() == item["id"].lower(), "ROLE_BINDING")
        item["create_ack"] = bound
        ledger.save()
        status, body, _ = arm("GET", item["id"], ROLE_API)
        require(status == 200 and role_binding(body, item["scope"], principal,
                ledger.env["AZURE_SUBSCRIPTION_ID"]) == bound, "ROLE_BINDING")
        item.update(state="OWNED", binding=bound)
        ledger.save()
    print("HOSTED_CI_ROLES=VERIFIED INSTANCE_ONLY ACCOUNT_AND_PROJECT")


def cleanup_roles(ledger, arm, *, clock=time.monotonic, sleep=time.sleep):
    for item in ledger.data.get("roles", []):
        if item["state"] in ("PLANNED", "STANDING"):
            continue
        require(item["state"] in ("OWNED", "DELETE_REQUESTED", "ABSENT") and
                item.get("pre_get_404") is True and item.get("create_ack") == item.get("binding"),
                "ROLE_OWNERSHIP_UNKNOWN")
        binding = item["binding"]
        require(binding["scope"] in (ledger.a["project_id"], ledger.a["project_id"].rsplit("/projects/", 1)[0]) and
                binding["principal"] == ledger.data["binding"]["identity"]["principal_id"], "ROLE_BINDING")
        status, body, etag = arm("GET", binding["id"], ROLE_API)
        if not role_absent(status, body):
            require(status == 200 and role_binding(body, binding["scope"], binding["principal"],
                    ledger.env["AZURE_SUBSCRIPTION_ID"]) == binding, "ROLE_BINDING")
            require(item["state"] == "OWNED", "DELETE_ALREADY_ATTEMPTED")
            item["state"] = "DELETE_REQUESTED"
            ledger.save()
            def before_delete():
                status, body, _ = arm("GET", binding["id"], ROLE_API)
                require(status == 200 and role_binding(body, binding["scope"], binding["principal"],
                        ledger.env["AZURE_SUBSCRIPTION_ID"]) == binding, "ROLE_BINDING")
                common.require_lifetime(ledger.a, 300)
            status, _, _ = arm("DELETE", binding["id"], ROLE_API, etag,
                              before_send=before_delete)
            require(status in (200, 202, 204), "ROLE_DELETE_UNKNOWN")
        deadline = clock() + 45
        while clock() < deadline:
            status, body, _ = arm("GET", binding["id"], ROLE_API)
            if role_absent(status, body):
                item["state"] = "ABSENT"
                ledger.save()
                break
            require(status == 200 and role_binding(body, binding["scope"], binding["principal"],
                    ledger.env["AZURE_SUBSCRIPTION_ID"]) == binding, "ROLE_BINDING")
            sleep(5)
        else:
            raise Error("ROLE_ABSENCE_UNPROVEN")


def remove_once(ledger, native, kind, arguments, *, clock=time.monotonic, sleep=time.sleep):
    key = kind + ":" + fingerprint(arguments)
    intents = ledger.data.setdefault("delete_intents", [])
    absent = ledger.data.setdefault("absent", [])
    get = "get" if kind == "agent" else "get_" + kind
    delete = "delete" if kind == "agent" else "delete_" + kind
    deadline = clock() + 60
    if not native.absent(get, **arguments):
        require(key not in intents, "DELETE_ALREADY_ATTEMPTED")
        def recheck():
            if kind == "version":
                require(version_binding(native.call(get, **arguments), ledger) == ledger.data["binding"],
                        "OWNERSHIP_CHANGED")
                require(native.inventory("sessions", arguments["agent_name"]) == [], "SESSION_UNKNOWN")
            elif kind == "session":
                session = native.call(get, **arguments)
                require(session.agent_session_id == arguments["session_id"] and
                        session.version_indicator.type == "version_ref" and
                        session.version_indicator.get("agent_version") == ledger.data["binding"]["version"],
                        "SESSION_CHANGED")
                require(version_binding(native.call("get_version", agent_name=arguments["agent_name"],
                        agent_version=ledger.data["binding"]["version"]), ledger) == ledger.data["binding"],
                        "OWNERSHIP_CHANGED")
            else:
                require(agent_binding(native, arguments["agent_name"]) == ledger.data["agent_binding"] and
                        native.inventory("versions", arguments["agent_name"]) == [] and
                        native.inventory("sessions", arguments["agent_name"]) == [], "OWNERSHIP_CHANGED")
        common.require_lifetime(ledger.a, 300)
        intents.append(key)
        ledger.save()
        native.call(delete, before_send=recheck, **arguments,
                    **({"force": False} if kind in ("agent", "version") else {}))
    consecutive = 0
    while clock() < deadline:
        consecutive = consecutive + 1 if native.absent(get, **arguments) else 0
        if consecutive == 2:
            if key not in absent:
                absent.append(key)
            ledger.save()
            return
        sleep(5)
    raise Error("ABSENCE_UNPROVEN")


def record_native_absence(ledger, native, *, sleep=time.sleep):
    data = ledger.data
    name = data["agent"]
    if not native.absent("get", agent_name=name):
        require(not data.get("native_absent") and not data.get("parent_cascade_observed"), "OWNERSHIP_CHANGED")
        return False
    agent_key = "agent:" + fingerprint({"agent_name": name})
    if agent_key not in data.get("delete_intents", []):
        arguments = {"agent_name": name, "agent_version": data["binding"]["version"]}
        version_key = "version:" + fingerprint(arguments)
        require(version_key in data.get("delete_intents", []) and
                version_key in data.get("absent", []), "OWNERSHIP_UNKNOWN")
        if not data.get("parent_cascade_observed"):
            data["parent_cascade_observed"] = True
            ledger.save()
        require(native.absent("get_version", **arguments), "OWNERSHIP_CHANGED")
    # Final-version deletion may remove the parent. Verify through GET, never
    # reinterpret a failed inventory as empty or manufacture a parent DELETE.
    sleep(5)
    require(native.absent("get", agent_name=name), "OWNERSHIP_CHANGED")
    data["native_absent"] = True
    ledger.state("NATIVE_ABSENT_IMAGES_IDENTITIES_RETAINED")
    return True


def cleanup_native(ledger, native):
    data = ledger.data
    require(data.get("binding") and data.get("agent_binding") and
            data["agent_binding"]["identity"] == data["binding"]["identity"] and
            data.get("deploy_intent") is True and
            data.get("pre_get_404") is True, "OWNERSHIP_UNKNOWN")
    name, version = data["agent"], data["binding"]["version"]
    require(re.fullmatch(re.escape(SKILLS[ledger.a["skill"]][0]) + r"[0-9a-f]{32}", name), "SCOPE")
    # On a resumed finalizer after native deletion, do not reconstruct ownership
    # from a newly appeared name or silently restart DELETE.
    if record_native_absence(ledger, native):
        return
    if native.absent("get_version", agent_name=name, agent_version=version):
        key = "version:" + fingerprint({"agent_name": name, "agent_version": version})
        if record_native_absence(ledger, native):
            return
        require(key in data.get("delete_intents", []) and
                native.inventory("versions", name) == [] and native.inventory("sessions", name) == [],
                "OWNERSHIP_UNKNOWN")
        remove_once(ledger, native, "agent", {"agent_name": name})
        data["native_absent"] = True
        ledger.state("NATIVE_ABSENT_IMAGES_IDENTITIES_RETAINED")
        return
    reconcile(ledger, native)
    sessions = native.inventory("sessions", name)
    require(len(sessions) <= data.get("invoke_intents", 0), "SESSION_UNKNOWN")
    ids = [session.agent_session_id for session in sessions]
    require(len(set(ids)) == len(ids) and all(isinstance(item, str) and item for item in ids), "SESSION_UNKNOWN")
    for session_id in ids:
        session = native.call("get_session", agent_name=name, session_id=session_id)
        require(session.agent_session_id == session_id and session.version_indicator is not None and
                session.version_indicator.type == "version_ref" and
                session.version_indicator.get("agent_version") == version, "SESSION_UNKNOWN")
    previous = data.get("sessions")
    require(previous is None or set(ids) <= set(previous), "SESSION_CHANGED")
    data["sessions"] = ids if previous is None else previous
    ledger.save()
    for session_id in ids:
        remove_once(ledger, native, "session", {"agent_name": name, "session_id": session_id})
    require(native.inventory("sessions", name) == [], "SESSION_UNKNOWN")
    reconcile(ledger, native)
    remove_once(ledger, native, "version", {"agent_name": name, "agent_version": version})
    if record_native_absence(ledger, native):
        return
    require(native.inventory("versions", name) == [] and native.inventory("sessions", name) == [], "OWNERSHIP_CHANGED")
    remove_once(ledger, native, "agent", {"agent_name": name})
    data["native_absent"] = True
    ledger.state("NATIVE_ABSENT_IMAGES_IDENTITIES_RETAINED")


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    env = dict(os.environ if env is None else env)
    ledger = None
    try:
        require(argv in (["check"], ["init"], ["cleanup"], ["configure-routing"], ["before-invoke"], ["grants"]) or
                len(argv) == 3 and argv[0] == "deploy", "ARGUMENTS")
        path = root(env)
        a = approval(env, None if argv[0] in ("check", "init") else common.private_read(path / "approval.json"))
        if argv == ["check"]:
            print("HOSTED_CI_LIFECYCLE=PASS CONFIG_ONLY")
            return 0
        if argv == ["init"]:
            path.mkdir(mode=0o700)
            common.write(path / "approval.json", a)
            common.write(path / "receipt.json", {
                "context": {k: a[k] for k in ("skill", "sha", "run_id", "run_attempt")},
                "approval": a, "approval_sha256": fingerprint(a),
                "state": "PREPARED",
            })
        require(path.is_dir() and stat.S_IMODE(path.stat().st_mode) == 0o700, "PATH")
        with exclusive(path):
            ledger = Ledger(path, a, env)
            if argv == ["init"]:
                ledger.save()
            else:
                native = Native(env, a)
                if argv[0] == "deploy":
                    deploy(ledger, native, common.Arm(env), Path(argv[1]), argv[2])
                elif argv == ["configure-routing"]:
                    configure_routing(ledger, native)
                elif argv == ["before-invoke"]:
                    before_invoke(ledger, native)
                elif argv == ["grants"]:
                    grant_roles(ledger, native, common.Arm(env))
                else:
                    failures = []
                    # Independent disposition: a native error does not silently
                    # lose exact run-owned role revocation, or vice versa.
                    for action in (lambda: cleanup_native(ledger, native),
                                   lambda: cleanup_roles(ledger, common.Arm(env))):
                        try:
                            action()
                        except Error as error:
                            failures.append(str(error))
                    ledger.data["cleanup_errors"] = failures
                    ledger.save()
                    require(not failures, "CLEANUP_RESIDUAL")
                    ledger.state("NATIVE_AND_TEMPORARY_ROLES_ABSENT_IMAGES_IDENTITIES_RETAINED")
            print("HOSTED_CI_LIFECYCLE=PASS " + ledger.data["state"])
        return 0
    except (Error, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError,
            subprocess.TimeoutExpired) as error:
        code = str(error) if isinstance(error, Error) else "INPUT_OR_EXECUTION"
        print("HOSTED_CI_LIFECYCLE=FAIL " + code)
        if ledger is not None:
            try:
                with exclusive(ledger.path):
                    ledger = Ledger(ledger.path, ledger.a, ledger.env)
                    ledger.data["last_error"] = code
                    ledger.save()
            except (Error, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                print("HOSTED_CI_LIFECYCLE=FAIL CUSTODY")
        return 1


if __name__ == "__main__":
    def deadline(_signal, _frame):
        raise Error("DEADLINE")
    signal.signal(signal.SIGALRM, deadline)
    signal.signal(signal.SIGTERM, deadline)
    signal.signal(signal.SIGINT, deadline)
    signal.alarm(280 if sys.argv[1:] == ["cleanup"] else 3000)
    try:
        sys.exit(main())
    finally:
        signal.alarm(0)
