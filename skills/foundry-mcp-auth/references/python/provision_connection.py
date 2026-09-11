"""Canonical GA ARM custom OAuth contract proven by the live demo.

Source of truth for `../../SKILL.md § Connection setup`.
Caller supplies an isolated user credential and owns any secret lifecycle.
Never log the properties dictionary or enable HTTP body logging.
"""

import re
from urllib.parse import urlsplit
from uuid import UUID

from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource.resources.models import GenericResource


API_VERSION = "2026-05-01"

def build_toolbox_bridge_properties(project_endpoint: str, toolbox_name: str, version: str) -> dict:
    endpoint = urlsplit(project_endpoint)
    if (
        endpoint.scheme != "https" or not endpoint.hostname
        or not endpoint.hostname.endswith(".services.ai.azure.com")
        or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
        or not re.fullmatch(r"/api/projects/[^/]+/?", endpoint.path)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", toolbox_name)
        or not version.isdigit()
    ):
        raise ValueError("Use a first-party Foundry project endpoint and explicit Toolbox version")
    return {
        "authType": "UserEntraToken", "category": "RemoteTool",
        "target": f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1",
        "audience": "https://ai.azure.com",
    }


def build_oauth_properties(
    mcp_url: str, tenant_id: str, api_app_id: str, client_id: str,
    client_secret: str, permission: str = "demo.read",
) -> dict:
    for value in (tenant_id, api_app_id, client_id):
        if str(UUID(value)) != value:
            raise ValueError("Use canonical tenant/API/client application IDs")
    parsed = urlsplit(mcp_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTPS MCP URL without credentials, query or fragment")
    if not client_secret or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", permission):
        raise ValueError("A client credential and one exposed permission are required")
    authority = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"
    return {
        "authType": "OAuth2", "category": "RemoteTool", "target": mcp_url,
        "authorizationUrl": authority + "/authorize",
        "tokenUrl": authority + "/token", "refreshUrl": authority + "/token",
        "scopes": [f"api://{api_app_id}/{permission}", "offline_access"],
        "credentials": {"clientId": client_id, "clientSecret": client_secret},
    }


def provision_connection(
    arm_client, resource_id: str, properties: dict, *,
    approved: bool = False, replace_existing: bool = False,
) -> dict:
    """Create, or explicitly replace, one operator-owned project connection."""
    if approved is not True:
        raise PermissionError("Cloud-change approval and isolated tenant/subscription preflight required")
    auth_type = properties.get("authType")
    if auth_type not in ("OAuth2", "UserEntraToken"):
        raise ValueError("Only custom OAuth or the verified first-party Toolbox bridge is supported")
    if auth_type == "UserEntraToken":
        target = urlsplit(properties.get("target", ""))
        if (
            target.scheme != "https" or not target.hostname
            or not target.hostname.endswith(".services.ai.azure.com")
            or target.username or target.password or target.fragment
            or not re.fullmatch(r"/api/projects/[^/]+/toolboxes/[^/]+/versions/[0-9]+/mcp", target.path)
            or target.query != "api-version=v1" or properties.get("audience") != "https://ai.azure.com"
            or "credentials" in properties
        ):
            raise ValueError("UserEntraToken bridge must target the first-party Foundry Toolbox only")
    if not re.fullmatch(
        r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft.CognitiveServices/"
        r"accounts/[^/]+/projects/[^/]+/connections/[^/]+", resource_id, re.IGNORECASE,
    ):
        raise ValueError("Use the exact project connection ARM resource ID")
    try:
        existing = arm_client.resources.get_by_id(resource_id, API_VERSION)
    except ResourceNotFoundError:
        existing = None
    if existing is not None:
        if not replace_existing:
            raise ValueError("Connection exists; no implicit overwrite")
        if existing.properties.get("authType") != auth_type or existing.properties.get("target") != properties.get("target"):
            raise ValueError("Refusing to replace a different connection target/authentication type")
    arm_client.resources.begin_create_or_update_by_id(
        resource_id, API_VERSION, GenericResource(properties=properties),
    ).result()
    result = arm_client.resources.get_by_id(resource_id, API_VERSION)
    if result.properties.get("authType") != auth_type or result.properties.get("target") != properties["target"]:
        raise RuntimeError("Connection readback differs from the requested contract")
    return {
        "id": result.id,
        "auth_type": result.properties["authType"],
        "target": result.properties["target"],
        "redirect_url": result.properties.get("redirectUrl"),
    }
