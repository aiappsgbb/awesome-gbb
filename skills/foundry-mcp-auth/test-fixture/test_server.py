"""Local HTTP/MCP tests with locally signed tokens, NOT delegated Azure E2E."""

import asyncio
import hashlib
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
        token = self.token(upn="alice@example.test", preferred_username="alias@example.test", name="Example User")
        with self.assertLogs("mcp.auth", level="INFO") as logs:
            receipt = await self.call("who_am_i", token)
        self.assertNotIn("verified_token", receipt)
        for secret in (token, TENANT, USER_A, "alice@example.test", "alias@example.test", "Example User"):
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

    async def test_opt_in_proof_uses_the_actual_validated_bearer(self):
        self.server = build_server(
            self.policy, "https://mcp.example.com", lambda _: self.key.public_key(),
            expose_identity_proof=True,
        )
        self.app = self.server.http_app(path="/mcp", stateless_http=True, json_response=True)
        await self._check_identity_proof()

    @with_server
    async def _check_identity_proof(self):
        display = {USER_A: {"upn": "alice@example.test"}, USER_B: {"preferred_username": "bob@example.test"}}
        tokens = {user: self.token(user, **display[user]) for user in (USER_A, USER_B)}
        with self.assertLogs("mcp.auth", level="INFO") as logs:
            receipts = await asyncio.gather(*(
                self.call("who_am_i", tokens[user]) for user in (USER_A, USER_B)
            ))
        for user, receipt in zip((USER_A, USER_B), receipts):
            proof = receipt
            self.assertEqual(proof["oid"], user)
            self.assertEqual(proof["tid"], TENANT)
            self.assertEqual(proof["azp"], CLIENT)
            self.assertEqual(proof["aud"], API)
            self.assertEqual(proof["iss"], self.policy.issuer)
            self.assertEqual(proof["scp"], "demo.read")
            for misleading in ("subject", "subject_label", "tenant", "verified_token"):
                self.assertNotIn(misleading, proof)
            self.assertNotIn("user-a", json.dumps(proof))
            self.assertNotIn("user-b", json.dumps(proof))
            for key, value in display[user].items():
                self.assertEqual(proof[key], value)
                self.assertNotIn(value, str(logs.output))
            if user == USER_B:
                self.assertNotIn("upn", proof)
            self.assertEqual(proof["source"], "validated_inbound_bearer")
            self.assertEqual(proof["token_sha256"], hashlib.sha256(tokens[user].encode()).hexdigest())
            self.assertIn(receipt["correlation_id"], str(logs.output))
            self.assertIn(proof["token_sha256"], str(logs.output))
            for private_value in (tokens[user], user, TENANT, CLIENT):
                self.assertNotIn(private_value, str(logs.output))
            self.assertNotIn(tokens[user], json.dumps(receipt))
        for token, status in (
            (None, 401), (self.token(aud="https://ai.azure.com"), 401),
            (self.token(exp=1), 401), (self.token(scp=""), 403),
            (self.token(idtyp="app"), 403),
        ):
            response = await self.rpc("tools/call", token, {"name": "who_am_i", "arguments": {}})
            self.assertEqual(response.status_code, status)
            self.assertNotIn("verified_token", response.text)


if __name__ == "__main__":
    unittest.main()
