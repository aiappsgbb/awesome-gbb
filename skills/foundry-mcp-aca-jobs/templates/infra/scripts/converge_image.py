"""Canonical image convergence helper for foundry-mcp-aca-jobs.

Source of truth for the prose example in ../../../SKILL.md § Deploy with azd.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

_REQUIRED_ENV_KEYS = (
    "SERVICE_MCP_IMAGE_NAME",
    "MCP_APP_NAME",
    "ACA_JOB_NAME",
    "AZURE_RESOURCE_GROUP",
    "AZURE_SUBSCRIPTION_ID",
    "ACR_NAME",
    "ACR_LOGIN_SERVER",
    "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL",
    "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME",
    "MCP_ACA_JOBS_COSMOS_ENDPOINT",
    "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME",
    "MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT",
)
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _field(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return list(value)


def _raise(message: str) -> None:
    raise RuntimeError(message)


def load_azd_env_values(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, str]:
    result = run(
        ["azd", "env", "get-values", "--output", "json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (getattr(result, "stderr", "") or "").strip()
        _raise(f"azd env get-values failed: {stderr or result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive.
        raise RuntimeError("azd env get-values did not return valid JSON") from exc

    env: dict[str, str] = {}
    if isinstance(payload, Mapping) and set(payload.keys()) == {"values"}:
        candidate = payload["values"]
    else:
        candidate = payload
    if isinstance(candidate, Mapping):
        for key, value in candidate.items():
            env[str(key)] = "" if value is None else str(value)
    elif isinstance(candidate, list):
        for item in candidate:
            if not isinstance(item, Mapping):
                continue
            name = item.get("name") or item.get("Name") or item.get("key") or item.get("Key")
            value = item.get("value") if "value" in item else item.get("Value")
            if name is not None:
                env[str(name)] = "" if value is None else str(value)
    else:  # pragma: no cover - defensive.
        raise RuntimeError("azd env get-values returned an unsupported JSON shape")

    missing = [key for key in _REQUIRED_ENV_KEYS if not env.get(key)]
    if missing:
        _raise("missing required azd env values: " + ", ".join(missing))
    return env


def parse_image_reference(image_name: str, acr_login_server: str) -> tuple[str, str, str]:
    if "/" not in image_name:
        raise ValueError(f"invalid image reference: {image_name!r}")
    host, remainder = image_name.split("/", 1)
    if host != acr_login_server:
        raise ValueError(
            f"image host must exactly match ACR_LOGIN_SERVER: {host!r} != {acr_login_server!r}"
        )
    if ":" not in remainder or "@" in remainder:
        raise ValueError(f"image reference must be repo:tag without digest: {image_name!r}")
    repository, tag = remainder.rsplit(":", 1)
    if not repository or not tag:
        raise ValueError(f"invalid image reference: {image_name!r}")
    return host, repository, tag


def resolve_image_digest(
    image_name: str,
    *,
    acr_name: str,
    acr_login_server: str,
    check_output: Callable[..., str] = subprocess.check_output,
) -> str:
    _, repository, tag = parse_image_reference(image_name, acr_login_server)
    digest = str(
        check_output(
            [
                "az",
                "acr",
                "manifest",
                "show-metadata",
                "--registry",
                acr_name,
                "--name",
                f"{repository}:{tag}",
                "--query",
                "digest",
                "-o",
                "tsv",
            ],
            text=True,
        )
    ).strip()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"invalid manifest digest: {digest!r}")
    return f"{acr_login_server}/{repository}@{digest}"


def _default_credential():
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def _container_apps_client(credential: Any, subscription_id: str):
    from azure.mgmt.appcontainers import ContainerAppsAPIClient

    return ContainerAppsAPIClient(credential, subscription_id)


def _container_list(resource: Any) -> list[Any]:
    template = _field(_field(resource, "properties"), "template")
    containers = _field(template, "containers", default=[])
    return _as_list(containers)


def _find_container(resource: Any, container_name: str) -> Any:
    matches = [container for container in _container_list(resource) if _field(container, "name") == container_name]
    if not matches:
        _raise(f"missing required container {container_name!r}")
    return matches[0]


def _container_image(container: Any) -> str:
    image = _field(container, "image")
    if not image:
        _raise("container image is missing")
    return str(image)


def _set_container_image(resource: Any, container_name: str, image: str) -> None:
    container = _find_container(resource, container_name)
    if isinstance(container, Mapping):
        container["image"] = image
    else:
        setattr(container, "image", image)


def _clear_revision_suffix(resource: Any) -> None:
    template = _field(_field(resource, "properties"), "template")
    if isinstance(template, Mapping):
        template.pop("revisionSuffix", None)
        template.pop("revision_suffix", None)
        return
    for name in ("revision_suffix", "revisionSuffix"):
        if hasattr(template, name):
            setattr(template, name, None)


def _container_command(container: Any) -> list[str]:
    command = _field(container, "command", default=[])
    return [str(part) for part in _as_list(command)]


def _identity_ids(resource: Any) -> tuple[str, ...]:
    identity = _field(resource, "identity")
    ids = _field(identity, "userAssignedIdentities", "user_assigned_identities")
    if ids is None:
        _raise("resource identity is missing user-assigned identities")
    if isinstance(ids, Mapping):
        keys = tuple(sorted(str(key) for key in ids.keys()))
    else:
        keys = tuple(sorted(str(item) for item in _as_list(ids)))
    if not keys:
        _raise("resource identity is missing user-assigned identities")
    return keys


def _resource_changed(resource: Any, container_name: str, image: str) -> bool:
    return _container_image(_find_container(resource, container_name)) != image


def _resource_contract(resource: Any, *, container_name: str, expected_command: list[str], label: str) -> None:
    container = _find_container(resource, container_name)
    if _container_command(container) != expected_command:
        _raise(f"{label} command mismatch")


def _wait_for_result(poller: Any) -> None:
    result = _field(poller, "result")
    if callable(result):
        result()


def converge_image(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    check_output: Callable[..., str] = subprocess.check_output,
    credential_factory: Callable[[], Any] = _default_credential,
    client_factory: Callable[[Any, str], Any] = _container_apps_client,
) -> str:
    env = load_azd_env_values(run=run)

    credential = credential_factory()
    client = client_factory(credential, env["AZURE_SUBSCRIPTION_ID"])

    app = client.container_apps.get(env["AZURE_RESOURCE_GROUP"], env["MCP_APP_NAME"])
    job = client.jobs.get(env["AZURE_RESOURCE_GROUP"], env["ACA_JOB_NAME"])

    if _identity_ids(app) == _identity_ids(job):
        _raise("app and job must use distinct UAMI IDs")

    _resource_contract(app, container_name="mcp", expected_command=["python", "-m", "app.mcp_server"], label="app")
    _resource_contract(job, container_name="job", expected_command=["python", "-m", "app.job_worker"], label="job")

    desired_image = resolve_image_digest(
        env["SERVICE_MCP_IMAGE_NAME"],
        acr_name=env["ACR_NAME"],
        acr_login_server=env["ACR_LOGIN_SERVER"],
        check_output=check_output,
    )

    if not _resource_changed(app, "mcp", desired_image) and not _resource_changed(job, "job", desired_image):
        return desired_image

    if _resource_changed(app, "mcp", desired_image):
        app_copy = deepcopy(app)
        _set_container_image(app_copy, "mcp", desired_image)
        _clear_revision_suffix(app_copy)
        app_poller = client.container_apps.begin_create_or_update(env["AZURE_RESOURCE_GROUP"], env["MCP_APP_NAME"], app_copy)
        _wait_for_result(app_poller)

    if _resource_changed(job, "job", desired_image):
        job_copy = deepcopy(job)
        _set_container_image(job_copy, "job", desired_image)
        job_poller = client.jobs.begin_create_or_update(env["AZURE_RESOURCE_GROUP"], env["ACA_JOB_NAME"], job_copy)
        _wait_for_result(job_poller)

    return desired_image


def main() -> int:
    try:
        print(converge_image())
        return 0
    except Exception as exc:  # pragma: no cover - CLI guard.
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
