"""Local, signed-token regressions; never an Entra or Foundry E2E claim."""

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "skills/foundry-mcp-auth/references/python/authorization.py"
TENANT, API, CLIENT, USER_A, USER_B = (str(UUID(int=i)) for i in range(1, 6))


class DelegatedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), "Canonical delegated authorization module is missing")
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        spec = importlib.util.spec_from_file_location("mcp_auth_policy", SOURCE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.module, self.jwt = module, jwt
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.policy = module.EntraPolicy(TENANT, API, "demo.read", b"x" * 32)
        now = int(time.time())
        self.claims = {
            "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "aud": API, "tid": TENANT, "oid": USER_A, "sub": "opaque-user-a",
            "azp": CLIENT, "ver": "2.0", "scp": "demo.read profile.read",
            "iat": now - 10, "nbf": now - 10, "exp": now + 300,
        }

    def authenticate(self, claims=None, key=None):
        token = self.jwt.encode(
            self.claims if claims is None else claims,
            key or self.key, algorithm="RS256", headers={"kid": "test-key"},
        )
        return self.policy.authenticate(token, self.key.public_key()), token

    def test_signed_user_is_authorized_without_exposing_identity_or_token(self):
        principal, token = self.authenticate()
        self.policy.authorize(principal)
        receipt = self.policy.receipt(principal)
        self.assertEqual(receipt["auth_kind"], "delegated")
        self.assertEqual(receipt["audience"], API)
        self.assertIn("demo.read", receipt["scopes"])
        for secret in (token, USER_A, TENANT, "opaque-user-a"):
            self.assertNotIn(secret, json.dumps(receipt))

    def test_invalid_audience_issuer_tenant_version_and_lifetime_are_rejected(self):
        for name, value in (
            ("aud", "https://graph.microsoft.com"), ("iss", "https://attacker.invalid"),
            ("tid", USER_B), ("ver", "1.0"), ("exp", 1),
            ("nbf", int(time.time()) + 600), ("iat", int(time.time()) + 600),
            ("exp", "9999999999"), ("exp", True), ("exp", []),
            ("exp", float("inf")), ("oid", ""),
        ):
            with self.subTest(claim=name, value=value):
                claims = {**self.claims, name: value}
                with self.assertRaises(self.module.InvalidAccessToken):
                    self.authenticate(claims)

    def test_required_claims_cannot_be_omitted(self):
        for claim in ("exp", "iat", "iss", "aud", "tid", "oid", "sub", "azp", "ver"):
            with self.subTest(claim=claim):
                claims = self.claims.copy()
                del claims[claim]
                with self.assertRaises(self.module.InvalidAccessToken):
                    self.authenticate(claims)

    def test_wrong_signature_and_algorithm_are_rejected(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(self.module.InvalidAccessToken):
            self.authenticate(key=wrong)
        token = self.jwt.encode(self.claims, "not-an-rsa-key", algorithm="HS256")
        with self.assertRaises(self.module.InvalidAccessToken):
            self.policy.authenticate(token, self.key.public_key())

    def test_application_and_insufficient_scopes_are_forbidden(self):
        for replacement in (
            {"scp": "", "roles": ["demo.read"]},
            {"scp": "profile.read"},
            {"scp": "api://" + API + "/demo.read"},
            {"scp": "demo.read", "idtyp": "app"},
            {"scp": "", "scope": "demo.read"},
        ):
            with self.subTest(replacement=replacement):
                principal, _ = self.authenticate({**self.claims, **replacement})
                with self.assertRaises(self.module.InsufficientPermission):
                    self.policy.authorize(principal)

    def test_two_users_get_disjoint_server_selected_items(self):
        a, _ = self.authenticate()
        b, _ = self.authenticate({**self.claims, "oid": USER_B, "sub": "opaque-user-b"})
        first, second = self.policy.items(a), self.policy.items(b)
        self.assertNotEqual(first["owner_subject"], second["owner_subject"])
        self.assertTrue({x["id"] for x in first["items"]}.isdisjoint(
            x["id"] for x in second["items"]
        ))
        self.assertEqual(first, self.policy.items(a))

    def test_pseudonyms_are_tenant_scoped_and_receipts_are_per_call(self):
        principal, _ = self.authenticate()
        self.assertNotEqual(
            self.policy.receipt(principal)["correlation_id"],
            self.policy.receipt(principal)["correlation_id"],
        )
        other_policy = self.module.EntraPolicy(USER_B, API, "demo.read", b"x" * 32)
        other_claims = {**self.claims, "tid": USER_B, "iss": other_policy.issuer}
        token = self.jwt.encode(other_claims, self.key, algorithm="RS256")
        other = other_policy.authenticate(token, self.key.public_key())
        self.assertNotEqual(
            self.policy.receipt(principal)["subject"],
            other_policy.receipt(other)["subject"],
        )

    def test_configuration_is_explicit_and_key_is_not_printable(self):
        self.assertEqual(self.policy.oauth_scope, f"api://{API}/demo.read")
        self.assertNotIn("xxxxxxxx", repr(self.policy))
        for tenant, audience, scope, key in (
            ("common", API, "demo.read", b"x" * 32),
            (TENANT, "https://ai.azure.com", "demo.read", b"x" * 32),
            (TENANT, API, "", b"x" * 32),
            (TENANT, API, "demo.read other", b"x" * 32),
            (TENANT, API, "demo.read", b"short"),
        ):
            with self.assertRaises(ValueError):
                self.module.EntraPolicy(tenant, audience, scope, key)

    def test_server_configured_labels_bind_receipts_without_exposing_object_ids(self):
        policy = self.module.EntraPolicy(
            TENANT, API, "demo.read", b"x" * 32,
            subject_labels={USER_A: "user-a", USER_B: "user-b"},
        )
        a, _ = self.authenticate()
        b, _ = self.authenticate({**self.claims, "oid": USER_B, "sub": "opaque-user-b"})
        self.assertEqual(policy.receipt(a)["subject_label"], "user-a")
        self.assertEqual(policy.receipt(b)["subject_label"], "user-b")
        self.assertEqual(self.policy.receipt(a)["subject_label"], "unmapped")
        self.assertNotIn(USER_A, json.dumps(policy.receipt(a)))
        self.assertNotIn(USER_A, repr(policy))

    def test_subject_labels_require_distinct_non_identifying_operator_labels(self):
        for labels in (
            {USER_A: "same", USER_B: "same"},
            {"not-an-object-id": "user-a"},
            {USER_A: "person@example.com"},
            {USER_A: "unmapped"},
        ):
            with self.assertRaises(ValueError):
                self.module.EntraPolicy(TENANT, API, "demo.read", b"x" * 32, subject_labels=labels)

    def test_optional_display_claims_preserve_verified_names_without_identity_inference(self):
        values = {"upn": "alice@example.test", "preferred_username": "alias@example.test", "name": "Example User"}
        principal, _ = self.authenticate({**self.claims, **values})
        self.assertEqual(dict(principal.display_claims), values)
        for value in values.values():
            self.assertNotIn(value, repr(principal))
            self.assertNotIn(value, json.dumps(self.policy.receipt(principal)))
        with self.assertRaises(TypeError):
            principal.display_claims["upn"] = "changed@example.test"
        preferred, _ = self.authenticate({**self.claims, "preferred_username": "alias@example.test"})
        self.assertNotIn("upn", preferred.display_claims)
        absent, _ = self.authenticate()
        self.assertEqual(dict(absent.display_claims), {})
        for field in values:
            with self.subTest(field=field):
                with self.assertRaises(self.module.InvalidAccessToken):
                    self.authenticate({**self.claims, field: {"untrusted": "value"}})


if __name__ == "__main__":
    unittest.main()
