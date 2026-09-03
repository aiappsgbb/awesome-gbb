#!/usr/bin/env python3
"""Deterministic live-Azure harness for the foundry-mcp-aca-jobs fixture."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = ROOT / "skills" / "foundry-mcp-aca-jobs"
TEMPLATE_ROOT = SKILL_ROOT / "templates"
REFERENCE_APP = SKILL_ROOT / "references" / "python" / "app"
HOSTED_REFERENCES = ROOT / "skills" / "foundry-hosted-agents" / "references"
STATE_NAME = "state.env"
APP_COMMAND = ["python", "-m", "app.mcp_server"]
JOB_COMMAND = ["python", "-m", "app.job_worker"]
PROVIDER_ACTIONS = {
    "Microsoft.App/jobs/read",
    "Microsoft.App/jobs/start/action",
    "Microsoft.App/jobs/execution/read",
    "Microsoft.App/jobs/executions/read",
    "Microsoft.App/jobs/stop/execution/action",
}
CALLBACK_FIELDS = {"taskId", "acaExecutionId", "status", "resultUrl"}
TERMINAL_STATES = {"Succeeded", "Failed", "Cancelled"}


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 900,
    capture: bool = True,
) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=capture,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"{command[0]} failed ({completed.returncode}): {detail[-4000:]}")
    return (completed.stdout or "").strip()


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f'{key}="{value}"\n' for key, value in sorted(values.items())),
        encoding="utf-8",
    )


def _write_state(project_dir: Path, values: dict[str, str]) -> None:
    path = project_dir / STATE_NAME
    current = _load_state(project_dir) if path.exists() else {}
    current.update(values)
    path.write_text(
        "".join(f"{key}={shlex.quote(value)}\n" for key, value in sorted(current.items())),
        encoding="utf-8",
    )


def _load_state(project_dir: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for line in (project_dir / STATE_NAME).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        state[key] = shlex.split(value)[0] if value else ""
    return state


def _copy_templates(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=False)
    for name in ("azure.yaml", "Dockerfile", "pyproject.toml", "uv.lock"):
        shutil.copy2(TEMPLATE_ROOT / name, project_dir / name)
    shutil.copytree(TEMPLATE_ROOT / "infra", project_dir / "infra")
    shutil.copytree(REFERENCE_APP, project_dir / "app")


def _validate_brownfield_url(url: str, name: str, suffix: str) -> None:
    parsed = urlsplit(url)
    expected_host = f"{name}.{suffix}"
    if (
        parsed.scheme != "https"
        or parsed.hostname != expected_host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(f"brownfield URL/name mismatch: expected https://{expected_host}")


def _set_cosmos_account_mode(project_dir: Path, use_existing: bool) -> None:
    parameters_path = project_dir / "infra" / "main.parameters.json"
    parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
    parameters["parameters"]["cosmosUseExistingAccount"]["value"] = use_existing
    parameters_path.write_text(json.dumps(parameters, indent=2) + "\n", encoding="utf-8")


def _scaffold(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _validate_brownfield_url(
        args.storage_account_url,
        args.storage_account_name,
        "blob.core.windows.net",
    )
    _validate_brownfield_url(
        args.cosmos_endpoint,
        args.cosmos_account_name,
        "documents.azure.com",
    )
    if not args.cosmos_use_existing_account:
        raise ValueError("live CI scaffold requires the explicit brownfield Cosmos mode")

    _copy_templates(project_dir)
    _set_cosmos_account_mode(project_dir, args.cosmos_use_existing_account)
    azd_values = {
        "AZURE_ENV_NAME": args.env_name,
        "AZURE_LOCATION": args.location,
        "AZURE_RESOURCE_GROUP": args.resource_group,
        "AZURE_SUBSCRIPTION_ID": args.azure_subscription_id,
        "AZURE_TENANT_ID": args.azure_tenant_id,
        "AZURE_CLIENT_ID": args.azure_client_id,
        "ACR_NAME": args.acr_name,
        "ACR_LOGIN_SERVER": args.acr_login_server,
        "MCP_ACA_JOBS_ENVIRONMENT_NAME": args.environment_name,
        "MCP_ACA_JOBS_APP_NAME": args.app_name,
        "MCP_ACA_JOBS_JOB_NAME": args.job_name,
        "MCP_APP_NAME": args.app_name,
        "ACA_JOB_NAME": args.job_name,
        "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": args.storage_account_url.rstrip("/"),
        "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME": args.storage_account_name,
        "MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME": args.output_container_name,
        "MCP_ACA_JOBS_COSMOS_ENDPOINT": args.cosmos_endpoint.rstrip("/"),
        "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME": args.cosmos_account_name,
        "MCP_ACA_JOBS_COSMOS_DATABASE": args.cosmos_database_name,
        "MCP_ACA_JOBS_COSMOS_CONTAINER": args.cosmos_container_name,
        "MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT": "true",
        "MCP_AUTH_APP_CLIENT_ID": args.mcp_auth_app_client_id,
        "FOUNDRY_PROJECT_ENDPOINT": args.foundry_project_endpoint,
        "AZURE_AI_PROJECT_ID": args.azure_ai_project_id,
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": args.model_deployment,
        "AZURE_CONTAINER_REGISTRY_ENDPOINT": args.acr_login_server,
        "SERVICE_MCP_IMAGE_NAME": args.service_mcp_image_name,
    }
    _write_env_file(project_dir / ".azure" / args.env_name / ".env", azd_values)
    (project_dir / ".azure" / "config.json").write_text(
        json.dumps({"defaultEnvironment": args.env_name}) + "\n",
        encoding="utf-8",
    )
    _write_state(
        project_dir,
        {
            "PROJECT_DIR": str(project_dir),
            "AZD_ENV_NAME": args.env_name,
            "RESOURCE_GROUP": args.resource_group,
            "ENVIRONMENT_NAME": args.environment_name,
            "APP_NAME": args.app_name,
            "JOB_NAME": args.job_name,
            "APP_IDENTITY_NAME": f"{args.app_name}-uami",
            "JOB_IDENTITY_NAME": f"{args.job_name}-uami",
            "STORAGE_ACCOUNT_URL": args.storage_account_url.rstrip("/"),
            "STORAGE_ACCOUNT_NAME": args.storage_account_name,
            "OUTPUT_CONTAINER_NAME": args.output_container_name,
            "COSMOS_ENDPOINT": args.cosmos_endpoint.rstrip("/"),
            "COSMOS_ACCOUNT_NAME": args.cosmos_account_name,
            "COSMOS_DATABASE_NAME": args.cosmos_database_name,
            "COSMOS_CONTAINER_NAME": args.cosmos_container_name,
            "ACR_NAME": args.acr_name,
            "ACR_LOGIN_SERVER": args.acr_login_server,
            "SERVICE_MCP_IMAGE_NAME": args.service_mcp_image_name,
            "FOUNDRY_PROJECT_ENDPOINT": args.foundry_project_endpoint,
            "AZURE_AI_PROJECT_ID": args.azure_ai_project_id,
            "MODEL_DEPLOYMENT": args.model_deployment,
            "MCP_AUTH_APP_CLIENT_ID": args.mcp_auth_app_client_id,
        },
    )
    print("SCAFFOLD_READY")


def _provider(_: argparse.Namespace) -> None:
    payload = json.loads(
        _run(
            [
                "az",
                "provider",
                "operation",
                "show",
                "--namespace",
                "Microsoft.App",
                "--output",
                "json",
            ],
            timeout=180,
        )
    )
    available: set[str] = set()

    def collect_names(value: Any) -> None:
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str):
                available.add(name)
            for child in value.values():
                collect_names(child)
        elif isinstance(value, list):
            for child in value:
                collect_names(child)

    collect_names(payload)
    missing = PROVIDER_ACTIONS - available
    if missing:
        raise RuntimeError(f"Microsoft.App provider is missing exact actions: {sorted(missing)}")
    print("RBAC_PROVIDER_ACTIONS_MATCH")


def _parse_azd_values(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = shlex.split(value)[0] if value else ""
    return values


def _deployed_container(resource_group: str, name: str, *, job: bool) -> dict[str, Any]:
    command = ["az", "containerapp"]
    if job:
        command.append("job")
    command.extend(["show", "--resource-group", resource_group, "--name", name, "--output", "json"])
    payload = json.loads(_run(command, timeout=180))
    return payload["properties"]["template"]["containers"][0]


def _deploy(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    state = _load_state(project_dir)
    run_env = os.environ.copy()
    run_env["AZURE_ENV_NAME"] = args.env_name
    _run(["azd", "up", "--no-prompt"], cwd=project_dir, env=run_env, timeout=1800, capture=False)

    app = _deployed_container(state["RESOURCE_GROUP"], state["APP_NAME"], job=False)
    job = _deployed_container(state["RESOURCE_GROUP"], state["JOB_NAME"], job=True)
    expected_image = str(app.get("image", ""))
    expected_prefix = f"{state['ACR_LOGIN_SERVER']}/"
    if not expected_image.startswith(expected_prefix) or "@sha256:" not in expected_image:
        raise RuntimeError("deployed app image is not an immutable digest in the expected ACR")
    if app.get("image") != expected_image or job.get("image") != expected_image:
        raise RuntimeError("app and job do not use the exact immutable shared-image digest")
    if app.get("command") != APP_COMMAND or job.get("command") != JOB_COMMAND:
        raise RuntimeError("deployed app/job command arrays do not match the contract")

    env_values = _parse_azd_values(
        _run(["azd", "env", "get-values"], cwd=project_dir, env=run_env)
    )
    verify_env = os.environ.copy()
    verify_env.update(env_values)
    verify_env["AZURE_RESOURCE_GROUP"] = state["RESOURCE_GROUP"]
    verify_env["MCP_ACA_JOBS_APP_NAME"] = state["APP_NAME"]
    verify_env["MCP_ACA_JOBS_JOB_NAME"] = state["JOB_NAME"]
    verify_env["EXPECTED_IMAGE_DIGEST"] = expected_image
    _run(
        [sys.executable, "infra/scripts/verify_deployment.py"],
        cwd=project_dir,
        env=verify_env,
        timeout=300,
        capture=False,
    )

    fqdn = _run(
        [
            "az",
            "containerapp",
            "show",
            "--resource-group",
            state["RESOURCE_GROUP"],
            "--name",
            state["APP_NAME"],
            "--query",
            "properties.configuration.ingress.fqdn",
            "--output",
            "tsv",
        ],
        timeout=180,
    )
    if not fqdn:
        raise RuntimeError("deployed MCP app has no ingress FQDN")
    _write_state(
        project_dir,
        {
            "IMAGE_DIGEST": expected_image.split("@", 1)[1],
            "MCP_URL": f"https://{fqdn}/mcp",
            "CALLBACK_CONTAINER_URL": (
                f"{state['STORAGE_ACCOUNT_URL']}/"
                f"{state['OUTPUT_CONTAINER_NAME']}-callbacks"
            ),
        },
    )
    print("SHARED_IMAGE_DIGEST_MATCH")
    print("ENTRYPOINTS_MATCH")


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value


def _tool_payload(result: Any) -> dict[str, Any]:
    data = getattr(result, "data", None)
    data = _model_dump(data)
    if isinstance(data, dict):
        return data
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    dumped = _model_dump(result)
    if isinstance(dumped, dict):
        for key in ("structuredContent", "structured_content", "data"):
            if isinstance(dumped.get(key), dict):
                return dumped[key]
        for item in dumped.get("content", []):
            text = item.get("text") if isinstance(item, dict) else None
            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
    raise RuntimeError(f"tool response did not contain structured data: {type(result).__name__}")


def _assert_result_url(payload: dict[str, Any], storage_host: str) -> str:
    if set(payload) != {"status", "resultUrl"} or payload.get("status") != "Succeeded":
        raise RuntimeError(f"task result must be the exact reference-only shape: {payload}")
    result_url = payload["resultUrl"]
    parsed = urlsplit(result_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != storage_host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("task result URL is not an allowlisted credential-free blob URL")
    return result_url


async def _wait_callback(
    callback_container_url: str,
    task_id: str,
    credential: Any,
) -> dict[str, Any]:
    from azure.core.exceptions import ResourceNotFoundError
    from azure.storage.blob import BlobClient

    blob_url = f"{callback_container_url}/callbacks/{task_id}.json"
    blob = BlobClient.from_blob_url(blob_url, credential=credential)
    try:
        for _ in range(60):
            try:
                payload = json.loads(blob.download_blob().readall())
                if set(payload) != CALLBACK_FIELDS:
                    raise RuntimeError(f"callback fields differ from exact allowlist: {sorted(payload)}")
                return payload
            except ResourceNotFoundError:
                await asyncio.sleep(5)
    finally:
        blob.close()
    raise TimeoutError("callback blob did not arrive within 300 seconds")


async def _tasks(args: argparse.Namespace) -> None:
    from azure.identity import DefaultAzureCredential
    from fastmcp import Client
    from fastmcp_tasks.client import TasksClientExtension
    from fastmcp_tasks.client import call_tool_task

    project_dir = Path(args.project_dir).resolve()
    state = _load_state(project_dir)
    mcp_url = state["MCP_URL"]
    storage_host = urlsplit(state["STORAGE_ACCOUNT_URL"]).hostname or ""
    input_ref = f"{state['STORAGE_ACCOUNT_URL']}/{state['OUTPUT_CONTAINER_NAME']}/inputs/{state['AZD_ENV_NAME']}.json"
    credential = DefaultAzureCredential()
    access_token = credential.get_token(
        f"api://{args.mcp_auth_app_client_id}/.default"
    ).token
    request = {
        "jobType": "short-job",
        "idempotencyKey": f"direct-{state['AZD_ENV_NAME']}",
        "inputRef": input_ref,
        "callbackAlias": "ops",
    }

    async with Client(
        mcp_url,
        extensions=[TasksClientExtension()],
        auth=access_token,
        timeout=90,
    ) as client:
        task = await call_tool_task(client, "start_aca_job", request, timeout=90)
        initial = await task.status()
        if _model_dump(initial).get("status") not in {"working", "completed"}:
            raise RuntimeError(f"unexpected initial MCP task state: {_model_dump(initial)}")
        terminal = await task.wait(timeout=600)
        if _model_dump(terminal).get("status") != "completed":
            raise RuntimeError(f"direct MCP task did not complete: {_model_dump(terminal)}")
        direct_payload = _tool_payload(await task.result())
        direct_result_url = _assert_result_url(direct_payload, storage_host)

        duplicate = await call_tool_task(client, "start_aca_job", request, timeout=90)
        duplicate_terminal = await duplicate.wait(timeout=120)
        if _model_dump(duplicate_terminal).get("status") != "completed":
            raise RuntimeError("duplicate task did not resolve to the completed terminal state")
        duplicate_payload = _tool_payload(await duplicate.result())
        if duplicate.task_id != task.task_id or duplicate_payload != direct_payload:
            raise RuntimeError("duplicate idempotency key changed task identity or result")

        cancel_request = dict(request)
        cancel_request["idempotencyKey"] = f"cancel-{state['AZD_ENV_NAME']}"
        cancel_task = await call_tool_task(client, "start_aca_job", cancel_request, timeout=90)
        await cancel_task.cancel()
        cancel_terminal = await cancel_task.wait(timeout=300)
        if _model_dump(cancel_terminal).get("status") not in {"cancelled", "completed"}:
            raise RuntimeError(f"task cancellation never reached a terminal state: {_model_dump(cancel_terminal)}")

    fallback_request = dict(request)
    fallback_request["idempotencyKey"] = f"fallback-{state['AZD_ENV_NAME']}"
    async with Client(
        mcp_url,
        mode="legacy",
        extensions=[],
        auth=access_token,
        timeout=90,
    ) as plain_client:
        fallback_start = _tool_payload(
            await plain_client.call_tool("start_aca_job", fallback_request)
        )
        if "resultType" in fallback_start or not fallback_start.get("taskId") or not fallback_start.get("status"):
            raise RuntimeError("fallback start must return immediate identifiers/status without a task wrapper")
        fallback_task_id = fallback_start["taskId"]
        fallback_status = _tool_payload(
            await plain_client.call_tool(
                "get_aca_job_status", {"taskId": fallback_task_id}
            )
        )
        if fallback_status.get("taskId") != fallback_task_id or "resultType" in fallback_status:
            raise RuntimeError("fallback status returned the wrong identifier or a task wrapper")
        fallback_cancel = _tool_payload(
            await plain_client.call_tool(
                "cancel_aca_job", {"taskId": fallback_task_id}
            )
        )
        if fallback_cancel.get("taskId") != fallback_task_id or "resultType" in fallback_cancel:
            raise RuntimeError("fallback cancellation returned the wrong identifier or a task wrapper")
        last_status = fallback_cancel
        for _ in range(30):
            if last_status.get("status") in TERMINAL_STATES:
                break
            await asyncio.sleep(5)
            last_status = _tool_payload(
                await plain_client.call_tool(
                    "get_aca_job_status", {"taskId": fallback_task_id}
                )
            )
        if last_status.get("status") not in TERMINAL_STATES:
            raise TimeoutError("fallback cancellation did not reach a terminal status")

    callback = await _wait_callback(
        state["CALLBACK_CONTAINER_URL"],
        task.task_id,
        credential,
    )
    callback_url = _assert_result_url(
        {"status": callback["status"], "resultUrl": callback["resultUrl"]},
        storage_host,
    )
    if (
        callback["taskId"] != task.task_id
        or not callback["acaExecutionId"]
        or callback_url != direct_result_url
    ):
        raise RuntimeError("callback identity/result does not match the completed direct task")
    credential.close()

    print("MCP_TASKS_COMPLETED")
    print("FALLBACK_TOOLS_COMPLETED")
    print("IDEMPOTENCY_DUPLICATE_SAME_TASK")
    print("CALLBACK_PAYLOAD_VALID")
    print("CANCELLATION_TERMINAL")


def _response_dump(response: Any) -> str:
    if hasattr(response, "model_dump_json"):
        return response.model_dump_json()
    return json.dumps(_model_dump(response), default=str)


def _invoke_agent_reference(project: Any, name: str, prompt: str) -> Any:
    openai = project.get_openai_client()
    conversation = openai.conversations.create()
    last_error: Exception | None = None
    for _ in range(12):
        try:
            return openai.responses.create(
                conversation=conversation.id,
                extra_body={
                    "agent_reference": {
                        "name": name,
                        "type": "agent_reference",
                    }
                },
                input=prompt,
            )
        except Exception as exc:  # bounded provisioning/cold-start retry
            last_error = exc
            time.sleep(10)
    raise RuntimeError(f"prompt-agent invoke did not succeed: {last_error}")


def _prompt_agent(args: argparse.Namespace) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import MCPTool, PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    project_dir = Path(args.project_dir).resolve()
    state = _load_state(project_dir)
    credential = DefaultAzureCredential()
    access_token = credential.get_token(
        f"api://{args.mcp_auth_app_client_id}/.default"
    ).token
    project = AIProjectClient(endpoint=args.project_endpoint, credential=credential)
    name = f"ci-mcp-jobs-prompt-{state['AZD_ENV_NAME'][-8:]}"
    version: Any | None = None
    try:
        version = project.agents.create_version(
            agent_name=name,
            definition=PromptAgentDefinition(
                model=state["MODEL_DEPLOYMENT"],
                instructions=(
                    "You must call start_aca_job once, then call get_aca_job_status "
                    "with its taskId. Report PROMPT_AGENT_MCP_PASS only after both calls."
                ),
                tools=[
                    MCPTool(
                        server_label="aca_jobs",
                        server_url=state["MCP_URL"],
                        headers={"Authorization": f"Bearer {access_token}"},
                        require_approval="never",
                    )
                ],
            ),
        )
        response = _invoke_agent_reference(
            project,
            name,
            (
                "Call start_aca_job with jobType short-job, idempotencyKey "
                f"prompt-{state['AZD_ENV_NAME']}, inputRef "
                f"{state['STORAGE_ACCOUNT_URL']}/{state['OUTPUT_CONTAINER_NAME']}/inputs/prompt.json, "
                "and callbackAlias ops. Then call get_aca_job_status with the returned taskId. "
                "Finish with PROMPT_AGENT_MCP_PASS."
            ),
        )
        evidence = _response_dump(response)
        if (
            "start_aca_job" not in evidence
            or "get_aca_job_status" not in evidence
            or "PROMPT_AGENT_MCP_PASS" not in evidence
        ):
            raise RuntimeError("prompt agent did not execute both fallback MCP tools")
        print("PROMPT_AGENT_MCP_PASS")
    finally:
        if version is not None:
            try:
                project.agents.delete_version(name, str(version.version))
            except Exception as exc:
                print(f"NOTE prompt-agent cleanup best effort: {type(exc).__name__}")
        project.close()
        credential.close()


def _copy_hosted_agent_scaffold(
    hosted_dir: Path,
    *,
    name: str,
    project_endpoint: str,
    project_id: str,
    model: str,
    acr_login_server: str,
    mcp_url: str,
    access_token: str,
    env_name: str,
    subscription_id: str,
) -> None:
    hosted_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(HOSTED_REFERENCES / "docker" / "Dockerfile", hosted_dir / "Dockerfile")
    shutil.copy2(
        HOSTED_REFERENCES / "python" / "pyproject.toml",
        hosted_dir / "pyproject.toml",
    )
    (hosted_dir / "copilot-instructions.md").write_text(
        "Use the ACA Jobs MCP tools exactly as instructed.\n",
        encoding="utf-8",
    )
    (hosted_dir / "container.py").write_text(
        """import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity.aio import DefaultAzureCredential

credential = DefaultAzureCredential()
client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=credential,
)
mcp_tool = client.get_mcp_tool(
    name="ACA Jobs",
    url=os.environ["MCP_SERVER_URL"],
    headers={"Authorization": f"Bearer {os.environ['MCP_BEARER_TOKEN']}"},
    approval_mode="never_require",
)
agent = Agent(
    client=client,
    instructions=(
        "Call start_aca_job once and then get_aca_job_status with the returned "
        "taskId. Emit HOSTED_AGENT_MCP_PASS only after both calls."
    ),
    tools=[mcp_tool],
    default_options={"store": False},
)
server = ResponsesHostServer(agent)
server.run()
""",
        encoding="utf-8",
    )
    (hosted_dir / "azure.yaml").write_text(
        f"""name: {name}
requiredVersions:
  extensions:
    azure.ai.agents: '>=1.0.0-beta.4'
services:
  ai-project:
    host: azure.ai.project
    endpoint: ${{FOUNDRY_PROJECT_ENDPOINT}}
  {name}:
    host: azure.ai.agent
    project: .
    language: docker
    uses:
      - ai-project
    kind: hosted
    name: {name}
    protocols:
      - protocol: responses
        version: 2.0.0
    environmentVariables:
      - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
        value: ${{AZURE_AI_MODEL_DEPLOYMENT_NAME}}
      - name: MCP_SERVER_URL
        value: ${{MCP_SERVER_URL}}
      - name: MCP_BEARER_TOKEN
        value: ${{MCP_BEARER_TOKEN}}
    container:
      resources:
        cpu: "1"
        memory: 2Gi
infra:
  provider: microsoft.foundry
""",
        encoding="utf-8",
    )
    _write_env_file(
        hosted_dir / ".azure" / env_name / ".env",
        {
            "AZURE_ENV_NAME": env_name,
            "AZURE_SUBSCRIPTION_ID": subscription_id,
            "FOUNDRY_PROJECT_ENDPOINT": project_endpoint,
            "AZURE_AI_PROJECT_ID": project_id,
            "AZURE_CONTAINER_REGISTRY_ENDPOINT": acr_login_server,
            "AZURE_AI_MODEL_DEPLOYMENT_NAME": model,
            "MCP_SERVER_URL": mcp_url,
            "MCP_BEARER_TOKEN": access_token,
        },
    )
    (hosted_dir / ".azure" / "config.json").write_text(
        json.dumps({"defaultEnvironment": env_name}) + "\n",
        encoding="utf-8",
    )


def _hosted_agent(args: argparse.Namespace) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        AgentEndpointConfig,
        FixedRatioVersionSelectionRule,
        ProtocolConfiguration,
        ResponsesProtocolConfiguration,
        VersionSelector,
    )
    from azure.identity import DefaultAzureCredential

    project_dir = Path(args.project_dir).resolve()
    state = _load_state(project_dir)
    credential = DefaultAzureCredential()
    access_token = credential.get_token(
        f"api://{args.mcp_auth_app_client_id}/.default"
    ).token
    name = f"ci-mcp-jobs-hosted-{state['AZD_ENV_NAME'][-8:]}"
    hosted_dir = project_dir / "hosted-agent"
    _copy_hosted_agent_scaffold(
        hosted_dir,
        name=name,
        project_endpoint=args.project_endpoint,
        project_id=state["AZURE_AI_PROJECT_ID"],
        model=state["MODEL_DEPLOYMENT"],
        acr_login_server=state["ACR_LOGIN_SERVER"],
        mcp_url=state["MCP_URL"],
        access_token=access_token,
        env_name=state["AZD_ENV_NAME"],
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
    )
    run_env = os.environ.copy()
    run_env["AZURE_ENV_NAME"] = state["AZD_ENV_NAME"]
    _run(
        ["azd", "deploy", name, "--no-prompt"],
        cwd=hosted_dir,
        env=run_env,
        timeout=1800,
        capture=False,
    )
    project = AIProjectClient(endpoint=args.project_endpoint, credential=credential)
    version: Any | None = None
    try:
        for _ in range(24):
            version = project.agents.get_version(
                agent_name=name,
                agent_version="1",
            )
            status = version.get("status") if isinstance(version, dict) else version.status
            if status == "active":
                break
            if status == "failed":
                raise RuntimeError(f"hosted agent version failed: {_model_dump(version)}")
            time.sleep(10)
        else:
            raise TimeoutError("hosted agent version did not become active in 240 seconds")

        project.agents.update_details(
            agent_name=name,
            agent_endpoint=AgentEndpointConfig(
                version_selector=VersionSelector(
                    version_selection_rules=[
                        FixedRatioVersionSelectionRule(
                            agent_version="1",
                            traffic_percentage=100,
                        )
                    ]
                ),
                protocol_configuration=ProtocolConfiguration(
                    responses=ResponsesProtocolConfiguration()
                ),
            ),
        )
        openai = project.get_openai_client(agent_name=name)
        response: Any | None = None
        last_error: Exception | None = None
        for _ in range(12):
            try:
                response = openai.responses.create(
                    input=(
                        "Call start_aca_job with jobType short-job, idempotencyKey "
                        f"hosted-{state['AZD_ENV_NAME']}, inputRef "
                        f"{state['STORAGE_ACCOUNT_URL']}/{state['OUTPUT_CONTAINER_NAME']}/inputs/hosted.json, "
                        "and callbackAlias ops. Then call get_aca_job_status with the "
                        "returned taskId. Finish with HOSTED_AGENT_MCP_PASS."
                    ),
                    stream=False,
                )
                break
            except Exception as exc:  # bounded cold-start retry
                last_error = exc
                time.sleep(10)
        if response is None:
            raise RuntimeError(f"hosted-agent invoke did not succeed: {last_error}")
        evidence = _response_dump(response)
        if (
            "start_aca_job" not in evidence
            or "get_aca_job_status" not in evidence
            or "HOSTED_AGENT_MCP_PASS" not in evidence
        ):
            raise RuntimeError("hosted agent did not execute both fallback MCP tools")
        _write_state(project_dir, {"HOSTED_AGENT_NAME": name})
        print("HOSTED_AGENT_MCP_PASS")
    finally:
        project.close()
        credential.close()


def _best_effort(command: list[str], *, timeout: int = 180) -> None:
    try:
        _run(command, timeout=timeout)
    except Exception as exc:
        print(f"NOTE cleanup best effort ({command[0]}): {type(exc).__name__}")


def _cleanup(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    state = _load_state(project_dir)
    deadline = time.monotonic() + 300

    hosted_name = state.get("HOSTED_AGENT_NAME")
    if hosted_name:
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential

            with DefaultAzureCredential() as credential, AIProjectClient(
                endpoint=state["FOUNDRY_PROJECT_ENDPOINT"],
                credential=credential,
            ) as project:
                project.agents.delete(agent_name=hosted_name, force=True)
        except Exception as exc:
            print(f"NOTE hosted-agent cleanup best effort: {type(exc).__name__}")
        _best_effort(
            [
                "az",
                "acr",
                "repository",
                "delete",
                "--name",
                state["ACR_NAME"],
                "--repository",
                hosted_name,
                "--yes",
            ]
        )

    for command in (
        [
            "az",
            "containerapp",
            "delete",
            "--resource-group",
            state["RESOURCE_GROUP"],
            "--name",
            state["APP_NAME"],
            "--yes",
        ],
        [
            "az",
            "containerapp",
            "job",
            "delete",
            "--resource-group",
            state["RESOURCE_GROUP"],
            "--name",
            state["JOB_NAME"],
            "--yes",
        ],
        [
            "az",
            "cosmosdb",
            "sql",
            "database",
            "delete",
            "--resource-group",
            state["RESOURCE_GROUP"],
            "--account-name",
            state["COSMOS_ACCOUNT_NAME"],
            "--name",
            state["COSMOS_DATABASE_NAME"],
            "--yes",
        ],
    ):
        if time.monotonic() >= deadline:
            print("NOTE cleanup stopped at five-minute budget")
            break
        _best_effort(command)

    for identity in (state["APP_IDENTITY_NAME"], state["JOB_IDENTITY_NAME"]):
        _best_effort(
            [
                "az",
                "identity",
                "delete",
                "--resource-group",
                state["RESOURCE_GROUP"],
                "--name",
                identity,
            ]
        )
    for container in (
        state["OUTPUT_CONTAINER_NAME"],
        f"{state['OUTPUT_CONTAINER_NAME']}-callbacks",
    ):
        _best_effort(
            [
                "az",
                "storage",
                "container",
                "delete",
                "--account-name",
                state["STORAGE_ACCOUNT_NAME"],
                "--name",
                container,
                "--auth-mode",
                "login",
            ]
        )
    image_tag = state["SERVICE_MCP_IMAGE_NAME"].rsplit(":", 1)[-1]
    _best_effort(
        [
            "az",
            "acr",
            "repository",
            "delete",
            "--name",
            state["ACR_NAME"],
            "--image",
            f"mcp/service:{image_tag}",
            "--yes",
        ]
    )
    print("CLEANUP_BEST_EFFORT_COMPLETE")


def _add_scaffold_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("scaffold")
    for flag in (
        "project-dir",
        "env-name",
        "resource-group",
        "location",
        "environment-name",
        "app-name",
        "job-name",
        "storage-account-url",
        "storage-account-name",
        "output-container-name",
        "cosmos-endpoint",
        "cosmos-account-name",
        "cosmos-database-name",
        "cosmos-container-name",
        "service-mcp-image-name",
        "acr-name",
        "acr-login-server",
        "azure-client-id",
        "azure-tenant-id",
        "azure-subscription-id",
        "mcp-auth-app-client-id",
        "foundry-project-endpoint",
        "azure-ai-project-id",
        "model-deployment",
    ):
        parser.add_argument(f"--{flag}", required=True)
    parser.add_argument("--cosmos-use-existing-account", action="store_true")
    parser.set_defaults(func=_scaffold)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_scaffold_parser(subparsers)

    provider = subparsers.add_parser("provider")
    provider.add_argument("--project-dir", required=True)
    provider.set_defaults(func=_provider)

    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("--project-dir", required=True)
    deploy.add_argument("--env-name", required=True)
    deploy.set_defaults(func=_deploy)

    tasks = subparsers.add_parser("tasks")
    tasks.add_argument("--project-dir", required=True)
    tasks.add_argument("--mcp-auth-app-client-id", required=True)
    tasks.set_defaults(func=lambda args: asyncio.run(_tasks(args)))

    prompt = subparsers.add_parser("prompt-agent")
    prompt.add_argument("--project-dir", required=True)
    prompt.add_argument("--project-endpoint", required=True)
    prompt.add_argument("--mcp-auth-app-client-id", required=True)
    prompt.set_defaults(func=_prompt_agent)

    hosted = subparsers.add_parser("hosted-agent")
    hosted.add_argument("--project-dir", required=True)
    hosted.add_argument("--project-endpoint", required=True)
    hosted.add_argument("--mcp-auth-app-client-id", required=True)
    hosted.set_defaults(func=_hosted_agent)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--project-dir", required=True)
    cleanup.set_defaults(func=_cleanup)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
