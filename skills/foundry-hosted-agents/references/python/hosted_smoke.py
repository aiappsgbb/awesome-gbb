"""Canonical native SDK model/session readback oracle and private BASIC smoke.

Source of truth for `../../SKILL.md § Private BASIC consumer`.
The CLI performs live GETs and ONE model request only with --execute.
It never deploys, grants roles, updates routing or cleans up. Output stays private.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentSessionResource, AgentVersionDetails
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential
import httpx
from openai import APIError
from openai.types.responses import Response

from deploy_preflight import check_setup, fresh, same_id, unique_keys


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def model_result(response: Response) -> dict:
    demand(response.status == "completed" and response.error is None
           and response.incomplete_details is None, "Response did not complete successfully")
    demand(bool(response.id) and bool(response.output_text.strip()), "Empty model response")
    messages = []
    for item in response.output:
        demand(item.type in {"reasoning", "message"}, "Tool/consent output is not a no-tools BASIC completion")
        if item.type == "message":
            demand(item.role == "assistant" and item.status == "completed", "Incomplete assistant message")
            demand(all(c.type == "output_text" for c in item.content), "Refusal/non-text message")
            messages.append((item.id, tuple(c.text for c in item.content)))
    demand(bool(messages), "Missing completed assistant message")
    extra = response.model_extra or {}
    demand(isinstance(extra.get("agent_session_id"), str) and bool(extra["agent_session_id"]),
           "Missing native response session ID")
    return {"id": response.id, "session_id": extra["agent_session_id"], "messages": messages}


def verify_model_readback(response: Response, readback: Response, session: AgentSessionResource,
                          *, agent_name: str, agent_version: str) -> dict:
    first = model_result(response)
    demand(first == model_result(readback), "Independent response readback mismatch")
    # Version routing is proved by the native session GET; optional response
    # agent_reference is checked when emitted, not invented when absent.
    for item in (response, readback):
        reference = (item.model_extra or {}).get("agent_reference")
        if reference is not None:
            demand(isinstance(reference, dict) and reference.get("name") == agent_name
                   and reference.get("version") == agent_version, "Response agent/version mismatch")
    demand(session.agent_session_id == first["session_id"], "Independent session ID mismatch")
    demand(session.status in {"active", "idle"}, "Session is not usable")
    demand(session.expires_at is not None and session.expires_at > datetime.now(timezone.utc),
           "Session has expired")
    indicator = session.version_indicator
    demand(indicator is not None and indicator.type == "version_ref"
           and indicator.get("agent_version") == agent_version,
           "Session version mismatch")
    return {
        "response_id": first["id"], "session_id": first["session_id"],
        "agent_name": agent_name, "agent_version": agent_version,
        "output_sha256": hashlib.sha256(response.output_text.encode()).hexdigest(),
    }


def version_binding(version: AgentVersionDetails, *, name: str, number: str,
                    image: str, model: str) -> dict:
    demand(version.name == name and version.version == number, "Direct version identity mismatch")
    demand(not version.get("error") and version.status not in {"failed", "deleting", "deleted"},
           "Direct version GET reports failure")
    definition = version.definition
    demand(definition is not None and definition.kind == "hosted", "Not a Hosted container")
    container = definition.get("container_configuration")
    environment = definition.get("environment_variables")
    protocols = definition.get("protocol_versions")
    demand(isinstance(container, Mapping) and container.get("image") == image, "Version image mismatch")
    demand(isinstance(environment, Mapping) and environment.get("AZURE_AI_MODEL_DEPLOYMENT_NAME") == model,
           "Version model binding mismatch")
    demand(isinstance(protocols, list) and any(
        isinstance(p, Mapping) and p.get("protocol") == "responses" and p.get("version") == "2.0.0"
        for p in protocols), "Wrong native Responses protocol")
    demand(isinstance(version.metadata, Mapping) and version.metadata.get("enableVnextExperience") == "true",
           "Native creation metadata missing")
    identity = version.instance_identity
    demand(identity is not None and bool(identity.principal_id) and bool(identity.client_id),
           "Actual hosted instance identity missing")
    return {"version": number, "image": image, "principal_id": identity.principal_id,
            "client_id": identity.client_id}


def private_setup(data: dict) -> dict:
    result = check_setup(data)
    demand(result["status"] == "READY_FOR_REGISTRATION",
           "Setup blocked: " + (result["issues"][0]["code"] if result["issues"] else "unknown"))
    target = data["target"]
    demand(target["mode"] == "basic-private" and target["registry_network"] == "private",
           "This consumer requires private BASIC and private ACR, never public fallback")
    demand(target["tool_endpoints"] == [], "No-tools bootstrap cannot certify tool authentication")
    demand(data["account"]["properties"].get("disableLocalAuth") is True
           and data["registry"]["properties"].get("adminUserEnabled") is False,
           "Preserve keyless account and admin-disabled registry")
    return target


def check_context(data: dict) -> None:
    """Verify paired caches and exact native context before an authorized invoke."""
    target = data["target"]
    for env, default in (("AZURE_CONFIG_DIR", ".azure"), ("AZD_CONFIG_DIR", ".azd")):
        path = os.environ.get(env, "")
        demand(bool(path) and Path(path).is_absolute() and Path(path).is_dir()
               and Path(path).resolve() != (Path.home() / default).resolve(),
               f"Use existing isolated {env}, never the global cache")
    demand(Path(os.environ["AZURE_CONFIG_DIR"]).resolve() != Path(os.environ["AZD_CONFIG_DIR"]).resolve(),
           "Azure CLI and azd require separate paired caches")
    tenant = target.get("tenant_id")
    subscription = target["project_id"].split("/")[2]
    demand(isinstance(tenant, str) and bool(tenant), "Approved tenant_id required")
    expected = {
        "AZURE_TENANT_ID": tenant, "AZURE_SUBSCRIPTION_ID": subscription,
        "AZURE_AI_PROJECT_ID": target["project_id"],
        "FOUNDRY_PROJECT_ENDPOINT": target["project_endpoint"],
        "AZURE_CONTAINER_REGISTRY_ENDPOINT": data["registry"]["properties"]["loginServer"],
        "AZURE_CONTAINER_REGISTRY_RESOURCE_ID": target["registry_id"],
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": target["model_id"].rsplit("/", 1)[1],
    }
    account = json.loads(subprocess.run(
        ["az", "account", "show", "--query", "{id:id,tenantId:tenantId}", "--output", "json"],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout)
    demand(same_id(account.get("id"), subscription) and same_id(account.get("tenantId"), tenant),
           "Isolated Azure CLI tenant/subscription mismatch")
    for key, value in expected.items():
        demand(os.environ.get(key) == value, f"Shell context mismatch: {key}")
        actual = subprocess.run(["azd", "env", "get-value", key], check=True,
                                capture_output=True, text=True, timeout=30).stdout.strip()
        demand(actual == value, f"Isolated azd environment mismatch: {key}")


def execute(project: AIProjectClient, data: dict, name: str, number: str,
            record, *, attempts: int = 60, sleep=time.sleep) -> dict:
    target = private_setup(data)
    demand(2 <= attempts <= 90, "Readiness polling budget must be 2-90 attempts")
    binding = None
    active = 0
    for attempt in range(attempts):
        demand(fresh(data["observed_at"], datetime.now(timezone.utc)), "Setup evidence expired during readiness")
        record("version-get-start", {"agent": name, "version": number, "attempt": attempt + 1})
        version = project.agents.get_version(agent_name=name, agent_version=number)
        current = version_binding(
            version, name=name, number=number, image=target["image"],
            model=target["model_id"].rsplit("/", 1)[1],
        )
        demand(binding is None or current == binding, "Hosted binding changed between direct GETs")
        binding = current
        record("direct-version-get", {**binding, "status": version.status})
        active = active + 1 if version.status == "active" else 0
        if active == 2:
            break
        sleep(10)
    demand(active == 2, "Timed out waiting for two consecutive active direct version GETs")
    # No routing mutation. A returned session on another version is a hard mismatch.
    with project.get_openai_client(agent_name=name, max_retries=0,
                                   timeout=httpx.Timeout(180, connect=10)) as client:
        record("invoke-start", {"agent": name, "version": number})
        response = client.responses.create(input="Say hello in one short sentence.", stream=False)
        result = model_result(response)
        record("model-completed", {"response_id": result["id"], "session_id": result["session_id"]})
        record("response-readback-start", {"response_id": result["id"]})
        readback = client.responses.retrieve(
            result["id"], extra_headers={"x-agent-session-id": result["session_id"]},
        )
        record("session-readback-start", {"session_id": result["session_id"]})
        session = project.agents.get_session(agent_name=name, session_id=result["session_id"])
        proof = verify_model_readback(response, readback, session, agent_name=name, agent_version=number)
    demand(fresh(data["observed_at"], datetime.now(timezone.utc)), "Setup evidence expired during invoke/readback")
    record("final-version-get-start", {"agent": name, "version": number})
    latest = project.agents.get_version(agent_name=name, agent_version=number)
    demand(latest.status == "active" and binding == version_binding(
        latest, name=name, number=number, image=target["image"],
        model=target["model_id"].rsplit("/", 1)[1]), "Version changed after model readback")
    record("model-readback", {**binding, **proof})
    return {"status": "PRIVATE_BASIC_MODEL_PASS", **proof, **binding,
            "business_execution": "NOT_TESTED", "native_mount_write": "NOT_INDEPENDENTLY_TESTED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Owner-authorized live GETs plus one plain model request")
    args = parser.parse_args()
    stage = "authorization"
    created_evidence = False
    try:
        demand(args.execute, "Live execution requires --execute and current owner authorization")
        demand(re.fullmatch(r"[a-z][a-z0-9-]{2,62}", args.agent) is not None
               and re.fullmatch(r"[0-9]+", args.version) is not None, "Invalid exact agent/version")
        data = json.loads(args.setup.read_text(), object_pairs_hook=unique_keys)
        stage = "setup"
        target = private_setup(data)
        stage = "context"
        check_context(data)
        # Exclusive creation protects earlier failed/successful evidence; never overwrite.
        fd = os.open(args.evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created_evidence = True
        with os.fdopen(fd, "w") as output:
            def record(step, value):
                nonlocal stage
                stage = step
                output.write(json.dumps({"stage": step, "observed_at": datetime.now(timezone.utc).isoformat(),
                                         **value}) + "\n")
                output.flush()
            record("context", {"project_id": target["project_id"], "registry_id": target["registry_id"],
                               "setup_sha256": hashlib.sha256(args.setup.read_bytes()).hexdigest()})
            with AzureCliCredential(tenant_id=target["tenant_id"]) as credential, AIProjectClient(
                endpoint=target["project_endpoint"], credential=credential,
                retry_total=0, connection_timeout=10, read_timeout=30,
            ) as project:
                result = execute(project, data, args.agent, args.version, record)
                record("result", result)
    except (ValueError, OSError, subprocess.SubprocessError, AzureError, APIError) as error:
        # Never print raw SDK errors, signed operation URLs or credential-bearing bodies.
        result = {"status": "BLOCKED", "stage": stage, "error_type": type(error).__name__,
                  "status_code": getattr(error, "status_code", None),
                  "error_code": getattr(getattr(error, "error", None), "code", None),
                  "request_id": getattr(error, "request_id", None),
                  "reason": str(error) if type(error) is ValueError else "Retain private operator diagnostics"}
        if created_evidence:
            with args.evidence.open("a", encoding="utf-8") as output:
                output.write(json.dumps(result) + "\n")
        print(json.dumps(result))
        return 1
    print(json.dumps({"status": result["status"], "business_execution": "NOT_TESTED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
