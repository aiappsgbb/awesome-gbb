"""Local HTTP/MCP tests with locally signed tokens, NOT delegated Azure E2E."""

import asyncio
from functools import wraps
import json
import time
import unittest
from uuid import UUID

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from references.python.authorization import EntraPolicy
from references.python.delegated_server import build_server


TENANT, API, CLIENT, USER_A, USER_B = (str(UUID(int=i)) for i in range(1, 6))


def with_server(test):
    @wraps(test)
    async def run(self):
        # AnyIO's cancel scope must enter and exit in the same task.
        async with self.app.router.lifespan_context(self.app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(self.app), base_url="https://mcp.example.com",
            ) as self.client:
                await test(self)
    return run


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.policy = EntraPolicy(
            TENANT, API, "demo.read", b"x" * 32,
            subject_labels={USER_A: "user-a", USER_B: "user-b"},
        )
        self.server = build_server(
            self.policy, "https://mcp.example.com", lambda _: self.key.public_key(),
        )
        self.app = self.server.http_app(path="/mcp", stateless_http=True, json_response=True)

    def token(self, user=USER_A, **overrides):
        now = int(time.time())
        return jwt.encode({
            "iss": self.policy.issuer, "aud": API, "tid": TENANT,
            "oid": user, "sub": user, "azp": CLIENT, "ver": "2.0",
            "scp": "demo.read", "exp": now + 300, "iat": now - 10,
            **overrides,
        }, self.key, algorithm="RS256", headers={"kid": "test-key"})

    async def rpc(self, method, token=None, params=None):
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await self.client.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
        })

    async def call(self, name, token, arguments=None):
        response = await self.rpc("tools/call", token, {"name": name, "arguments": arguments or {}})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertFalse(result.get("isError"), result)
        return json.loads(result["content"][0]["text"])

    @with_server
    async def test_anonymous_initialize_and_tool_listing_are_401(self):
        for method in ("initialize", "tools/list", "tools/call"):
            response = await self.rpc(method)
            self.assertEqual(response.status_code, 401)
            self.assertIn("resource_metadata", response.headers["www-authenticate"])

    @with_server
    async def test_prm_advertises_full_scope_not_short_jwt_permission(self):
        response = await self.client.get("/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(response.status_code, 200)
        prm = response.json()
        self.assertEqual(prm["resource"], "https://mcp.example.com/mcp")
        self.assertEqual(prm["scopes_supported"], [self.policy.oauth_scope])
        self.assertEqual(prm["authorization_servers"], [self.policy.issuer])

    @with_server
    async def test_authorized_handshake_and_discovery(self):
        response = await self.rpc("initialize", self.token(), {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "local-contract-test", "version": "1.0"},
        })
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.rpc("tools/list", self.token())
        tools = response.json()["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"who_am_i", "list_my_demo_items"})
        for tool in tools:
            self.assertEqual(tool["inputSchema"].get("properties", {}), {})
            self.assertNotIn("_fastmcp", tool.get("_meta", {}),
                             "Hosted Toolbox rejects the FastMCP-private metadata key")

    @with_server
    async def test_wrong_audience_and_expired_tokens_fail_authentication(self):
        for token in (self.token(aud="https://ai.azure.com"), self.token(exp=1), "not.a.valid.jwt"):
            response = await self.rpc("tools/list", token)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn(token, response.text)

    @with_server
    async def test_app_only_and_missing_permission_are_403(self):
        for token in (self.token(scp="", roles=["demo.read"]), self.token(idtyp="app"), self.token(scp="other.read")):
            response = await self.rpc("tools/list", token)
            self.assertEqual(response.status_code, 403)

    @with_server
    async def test_user_identity_is_request_local_under_concurrency(self):
        async def invoke(user):
            return await self.call("list_my_demo_items", self.token(user))
        results = await asyncio.gather(*(invoke(USER_A if i % 2 == 0 else USER_B) for i in range(20)))
        first, second = results[0]["owner_subject"], results[1]["owner_subject"]
        self.assertNotEqual(first, second)
        for i, result in enumerate(results):
            self.assertEqual(result["owner_subject"], first if i % 2 == 0 else second)
            self.assertEqual(result["receipt"]["subject"], result["owner_subject"])
            self.assertEqual(result["receipt"]["subject_label"], "user-a" if i % 2 == 0 else "user-b")
        self.assertEqual(len({r["receipt"]["correlation_id"] for r in results}), 20)

    @with_server
    async def test_receipt_is_sanitized_and_argument_cannot_select_another_user(self):
        token = self.token()
        with self.assertLogs("mcp.auth", level="INFO") as logs:
            receipt = await self.call("who_am_i", token)
        for secret in (token, TENANT, USER_A):
            self.assertNotIn(secret, json.dumps(receipt) + str(logs.output))
        response = await self.rpc("tools/call", token, {
            "name": "who_am_i", "arguments": {"user_id": USER_B},
        })
        result = response.json()["result"]
        if not result.get("isError"):
            self.assertEqual(json.loads(result["content"][0]["text"])["subject"], receipt["subject"])

    @with_server
    async def test_health_does_not_disclose_identity(self):
        response = await self.client.get("/health")
        self.assertEqual(response.json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
