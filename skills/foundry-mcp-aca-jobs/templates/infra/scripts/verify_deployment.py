"""Canonical deployment verification helper for foundry-mcp-aca-jobs."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from typing import Any, TextIO
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from converge_image import (
    _as_list,
    _container_command,
    _container_image,
    _default_credential,
    _field,
    _find_container,
    _identity_ids,
    _container_apps_client,
    load_azd_env_values,
)


def _env_map(resource: Any, container_name: str) -> dict[str, str]:
    container = _find_container(resource, container_name)
    env_map: dict[str, str] = {}
    for item in _as_list(_field(container, "env", default=[])):
        name = _field(item, "name")
        value = _field(item, "value", default="")
        if name is not None:
            env_map[str(name)] = "" if value is None else str(value)
    return env_map


def _auth_config(client: Any, resource_group: str, app_name: str) -> Any:
    auth_configs = _field(client, "container_apps_auth_configs")
    if auth_configs is None:
        raise RuntimeError("container_apps_auth_configs operation group is missing")
    getter = _field(auth_configs, "get")
    if getter is None:
        raise RuntimeError("container_apps_auth_configs.get is missing")
    try:
        return getter(resource_group, app_name, "current")
    except TypeError:
        return getter(resource_group, app_name)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _assert_easy_auth_contract(auth_config: Any) -> None:
    properties = _field(auth_config, "properties")
    platform = _field(properties, "platform")
    validation = _field(_field(_field(properties, "identityProviders"), "azureActiveDirectory"), "validation")
    registration = _field(_field(_field(properties, "identityProviders"), "azureActiveDirectory"), "registration")

    _ensure(_field(platform, "enabled") is True, "easy auth platform must be enabled")
    _ensure(_field(_field(properties, "globalValidation"), "unauthenticatedClientAction") == "Return401", "easy auth must return 401 for anonymous callers")
    _ensure(_field(_field(_field(properties, "identityProviders"), "azureActiveDirectory"), "enabled") is True, "AAD auth must be enabled")

    client_id = _field(registration, "clientId")
    allowed = {str(item) for item in _as_list(_field(validation, "allowedAudiences", default=[]))}
    _ensure(bool(client_id), "AAD client id is missing")
    _ensure(f"api://{client_id}" in allowed, "AAD audience contract is missing the api:// audience")
    _ensure(str(client_id) in allowed, "AAD audience contract is missing the bare client id")


def _assert_env_contracts(app: Any, job: Any) -> None:
    app_env = _env_map(app, "mcp")
    job_env = _env_map(job, "job")

    _ensure(app_env.get("MCP_ACA_JOBS_AUTH_MODE") == "aca-easy-auth", "app easy-auth mode missing")
    _ensure("MCP_ACA_JOBS_CALLBACK_CONTAINER_URL" in app_env, "app callback storage url missing")
    _ensure("MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID" in app_env, "app callback principal id missing")
    _ensure("MCP_ACA_JOBS_OUTPUT_CONTAINER_URL" in job_env, "job output storage url missing")
    _ensure("MCP_ACA_JOBS_INPUT_HOSTS" in job_env, "job input host allowlist missing")
    _ensure("MCP_ACA_JOBS_RESULT_HOSTS" in job_env, "job result host allowlist missing")
    _ensure("MCP_ACA_JOBS_JOB_TYPE" in job_env, "job type missing")
    _ensure("MCP_ACA_JOBS_CALLBACK_AUTH_MODE" in job_env, "job callback auth mode missing")
    _ensure("MCP_ACA_JOBS_AUTH_MODE" not in job_env, "job must not inherit app easy-auth mode")
    _ensure(app_env["MCP_ACA_JOBS_CALLBACK_CONTAINER_URL"] != job_env["MCP_ACA_JOBS_OUTPUT_CONTAINER_URL"], "storage scopes must be distinct")
    _ensure(app_env["MCP_ACA_JOBS_AUTH_MODE"] == "aca-easy-auth", "app easy-auth contract failed")
    _ensure(job_env["MCP_ACA_JOBS_CALLBACK_AUTH_MODE"] in {"managed_identity", "key_vault"}, "job callback auth mode invalid")


def verify_deployment(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    credential_factory: Callable[[], Any] = _default_credential,
    client_factory: Callable[[Any, str], Any] = _container_apps_client,
    stdout: TextIO | None = None,
) -> None:
    env = load_azd_env_values(run=run)
    expected_image = env.get("EXPECTED_IMAGE_DIGEST")
    if not expected_image:
        raise RuntimeError("EXPECTED_IMAGE_DIGEST is required")
    if "@sha256:" not in expected_image:
        raise RuntimeError("EXPECTED_IMAGE_DIGEST must be an immutable digest reference")

    credential = credential_factory()
    client = client_factory(credential, env["AZURE_SUBSCRIPTION_ID"])

    app = client.container_apps.get(env["AZURE_RESOURCE_GROUP"], env["MCP_APP_NAME"])
    job = client.jobs.get(env["AZURE_RESOURCE_GROUP"], env["ACA_JOB_NAME"])
    auth_config = _auth_config(client, env["AZURE_RESOURCE_GROUP"], env["MCP_APP_NAME"])

    app_container = _find_container(app, "mcp")
    job_container = _find_container(job, "job")

    app_image = _container_image(app_container)
    job_image = _container_image(job_container)
    _ensure(app_image == job_image == expected_image, "shared image digest mismatch")
    _ensure("@sha256:" in app_image, "app image must use an immutable digest")
    _ensure(_container_command(app_container) == ["python", "-m", "app.mcp_server"], "app entrypoint mismatch")
    _ensure(_container_command(job_container) == ["python", "-m", "app.job_worker"], "job entrypoint mismatch")
    _ensure(_identity_ids(app) != _identity_ids(job), "app and job must use distinct UAMI IDs")
    _assert_easy_auth_contract(auth_config)
    _assert_env_contracts(app, job)

    output = sys.stdout if stdout is None else stdout
    print("SHARED_IMAGE_DIGEST_MATCH", file=output)
    print("ENTRYPOINTS_MATCH", file=output)
    output.flush()


def main() -> int:
    try:
        verify_deployment()
        return 0
    except Exception as exc:  # pragma: no cover - CLI guard.
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
