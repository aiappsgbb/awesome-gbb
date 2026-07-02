"""Hardened FastMCP server for ACA — Easy Auth perimeter + defense in depth.

Source of truth for the prose example in `../../SKILL.md § Securing your MCP
server`. This is the hardened sibling of `server.py`; keep `server.py` minimal
and copy the hardening patterns from here.

Layers demonstrated (full threat model in SKILL.md):
    L1  whoami() reads the ACA-injected X-MS-CLIENT-PRINCIPAL header SERVER-SIDE
        via get_http_headers() — NEVER as a tool argument the MCP client could
        forge. ACA sets the header only AFTER validating the JWT at the platform
        edge (and strips any client-supplied copy), so the identity is
        trustworthy and cannot be forged by the client.
    L2  DefaultAzureCredential uses the container's managed identity for
        downstream Azure — NEVER the caller's inbound token (confused deputy).
    L3  secret_status() returns secret METADATA, never the value.
        safe_lookup() rejects path-traversal / injection characters.
    L5  audit_event() emits one structured line per call; ACA ships stdout to
        Log Analytics for a foundry-observability scheduled-query alert.

NEVER call one @mcp.tool()-decorated function from inside another — @mcp.tool()
wraps it in a FunctionTool that is not plain-callable. Extract shared logic into
a private _helper() (here: _lookup_backend) and call THAT from both tools.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP("secure-tools")

logging.basicConfig(level=logging.INFO, format="%(message)s")
_audit = logging.getLogger("mcp.audit")

# One credential for the process lifetime — resolves `az login` locally and the
# user-assigned managed identity in ACA. No secrets in code (Layer 2).
_credential = DefaultAzureCredential()

# Characters that must never appear in a tool argument used as a key or path.
_UNSAFE = ("..", "/", "\\", ";", "|", "`", "$(")


def audit_event(caller: str, tool: str, decision: str, detail: str = "") -> None:
    """Emit one structured audit line (Layer 5). ACA -> Log Analytics captures
    stdout; a foundry-observability scheduled query alerts on spikes / denials."""
    _audit.info(
        json.dumps(
            {
                "event": "mcp.tool.call",
                "caller": caller,
                "tool": tool,
                "decision": decision,
                "detail": detail,
            }
        )
    )


def caller_identity() -> str:
    """Return the caller id from the ACA-injected X-MS-CLIENT-PRINCIPAL header.

    Read the header SERVER-SIDE via FastMCP's get_http_headers() — never accept
    it as a tool argument, which the MCP client controls and can forge. ACA's
    auth sidecar validates the JWT and sets this header (stripping any
    client-supplied copy) only after Layer 1 passes, so the claims are
    trustworthy. Header keys arrive lowercased. No header (local stdio / dev)
    -> "anonymous"; behind Easy Auth with Return401 an unauthenticated request
    never reaches the app."""
    client_principal_b64 = (get_http_headers() or {}).get("x-ms-client-principal")
    if not client_principal_b64:
        return "anonymous"
    try:
        raw = base64.b64decode(client_principal_b64)
        claims = json.loads(raw).get("claims", [])
    except (binascii.Error, json.JSONDecodeError, ValueError):
        return "unknown"
    wanted = {"preferred_username", "upn", "appid", "azp", "sub"}
    for claim in claims:
        if claim.get("typ") in wanted and claim.get("val"):
            return str(claim["val"])
    return "unknown"


def _reject_unsafe(value: str) -> None:
    """Layer 3 input deny-list: raise on traversal / injection characters."""
    if any(token in value for token in _UNSAFE):
        raise ValueError(f"rejected unsafe input: {value!r}")


def _lookup_backend(key: str) -> dict:
    """Plain helper — both tools call THIS, never each other (see module docstring)."""
    return {"key": key, "status": "ok"}


@mcp.tool()
async def whoami() -> dict:
    """Return the validated caller identity from the Easy Auth header (Layer 1)."""
    who = caller_identity()
    audit_event(who, "whoami", "allowed")
    return {"caller": who}


@mcp.tool()
async def safe_lookup(key: str) -> dict:
    """Look up a record by key, rejecting traversal / injection first (Layer 3)."""
    who = caller_identity()
    try:
        _reject_unsafe(key)
    except ValueError as exc:
        audit_event(who, "safe_lookup", "denied", str(exc))
        raise
    audit_event(who, "safe_lookup", "allowed", key)
    return _lookup_backend(key)


@mcp.tool()
async def secret_status(name: str) -> dict:
    """Return secret METADATA (never the value) via the server's MI (Layers 2+3)."""
    who = caller_identity()
    try:
        _reject_unsafe(name)
    except ValueError as exc:
        audit_event(who, "secret_status", "denied", str(exc))
        raise
    vault_url = os.environ["KEY_VAULT_URL"]
    client = SecretClient(vault_url=vault_url, credential=_credential)
    props = client.get_secret(name).properties
    audit_event(who, "secret_status", "allowed", name)
    return {
        "name": props.name,
        "enabled": props.enabled,
        "version": props.version,
        "not_before": str(props.not_before),
        "expires_on": str(props.expires_on),
        # NOTE: the secret VALUE is deliberately never returned.
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
