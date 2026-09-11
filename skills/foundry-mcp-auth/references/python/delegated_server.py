"""Canonical delegated-only MCP server with PRM and request-local identity.

Source of truth for `../../SKILL.md § Resource-server authorization`.
Entra is the authorization server; this process is only a resource server.
"""

import asyncio
import json
import logging
import os
import secrets
from urllib.parse import urlsplit

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from jwt import PyJWKClient, PyJWKClientError, PyJWKClientConnectionError, InvalidTokenError
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from .authorization import EntraPolicy, InvalidAccessToken, InsufficientPermission, Principal


audit = logging.getLogger("mcp.auth")


class EntraVerifier(TokenVerifier):
    def __init__(self, policy: EntraPolicy, key_resolver=None):
        super().__init__(required_scopes=[policy.oauth_scope])
        self.policy = policy
        if key_resolver is None:
            jwks = PyJWKClient(
                f"https://login.microsoftonline.com/{policy.tenant_id}/discovery/v2.0/keys",
                cache_jwk_set=True, lifespan=300, timeout=10,
            )
            key_resolver = lambda token: jwks.get_signing_key_from_jwt(token).key
        self.key_resolver = key_resolver

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            key = await asyncio.to_thread(self.key_resolver, token)
            principal = self.policy.authenticate(token, key)
        except PyJWKClientConnectionError:
            audit.error('{"event":"auth_dependency_unavailable"}')
            raise
        except (InvalidAccessToken, InvalidTokenError, PyJWKClientError):
            audit.warning('{"event":"auth_denied","reason":"invalid_access_token"}')
            return None
        try:
            self.policy.authorize(principal)
        except InsufficientPermission:
            # Valid token, insufficient rights: framework emits 403, not a fake user.
            audit.warning('{"event":"auth_denied","reason":"delegated_permission_required"}')
            return AccessToken(
                token=token, client_id=principal.client_id,
                scopes=[], expires_at=principal.expires_at,
            )
        return AccessToken(
            token=token, client_id=principal.client_id,
            scopes=[self.policy.oauth_scope], expires_at=principal.expires_at,
            claims={"principal": principal},
        )


def build_server(policy: EntraPolicy, base_url: str, key_resolver=None) -> FastMCP:
    url = urlsplit(base_url)
    local = url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        not url.hostname or not (url.scheme == "https" or local)
        or url.username or url.password or url.query or url.fragment
        or url.path not in ("", "/")
    ):
        raise ValueError("MCP_BASE_URL must be an HTTPS origin (loopback HTTP is local-only)")
    verifier = EntraVerifier(policy, key_resolver)
    auth = RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(policy.issuer)],
        base_url=base_url.rstrip("/"),
        resource_name="Delegated demo MCP",
    )
    server = FastMCP("delegated-demo", auth=auth, include_fastmcp_meta=False)

    def current_principal() -> Principal:
        access = get_access_token()
        if access is None or "principal" not in access.claims:
            raise InsufficientPermission("authenticated_delegated_context_required")
        principal = access.claims["principal"]
        policy.authorize(principal)
        return principal

    def record(tool: str, receipt: dict) -> None:
        audit.info(json.dumps({"event": "tool_allowed", "tool": tool, **receipt}))

    @server.tool()
    def who_am_i() -> dict:
        """Return a safe receipt for the authenticated user; never a token."""
        receipt = policy.receipt(current_principal())
        record("who_am_i", receipt)
        return receipt

    @server.tool()
    def list_my_demo_items() -> dict:
        """Return only server-selected synthetic items belonging to the authenticated user."""
        principal = current_principal()
        receipt = policy.receipt(principal)
        record("list_my_demo_items", receipt)
        return {**policy.items(principal), "receipt": receipt}

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Demo pseudonyms are stable for this process only, not a persisted identity store.
    policy = EntraPolicy(
        os.environ["MCP_TENANT_ID"], os.environ["MCP_API_CLIENT_ID"],
        os.environ.get("MCP_PERMISSION", "demo.read"), secrets.token_bytes(32),
        subject_labels=json.loads(os.environ.get("MCP_SUBJECT_LABELS_JSON", "{}")),
    )
    server = build_server(policy, os.environ["MCP_BASE_URL"])
    server.run(
        transport="streamable-http", host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")), stateless_http=True,
    )


if __name__ == "__main__":
    main()
