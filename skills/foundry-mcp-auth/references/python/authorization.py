"""Canonical strict Entra v2 resource-server policy.

Source of truth for `../../SKILL.md § Resource-server authorization`.
This module validates access tokens; it never acquires or exchanges them.
"""

from dataclasses import dataclass, field
from collections.abc import Mapping
import hashlib
import hmac
import re
import time
from types import MappingProxyType
from uuid import UUID, uuid4

import jwt


class InvalidAccessToken(ValueError):
    """Authentication failed (HTTP 401); do not expose the underlying JWT."""


class InsufficientPermission(ValueError):
    """Authenticated caller lacks delegated permission (HTTP 403)."""


@dataclass(frozen=True)
class Principal:
    tenant: str
    object_id: str
    client_id: str
    scopes: frozenset[str]
    delegated: bool
    expires_at: int


@dataclass(frozen=True)
class EntraPolicy:
    tenant_id: str
    audience: str
    permission: str
    pseudonym_key: bytes = field(repr=False)
    subject_labels: Mapping[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        for value in (self.tenant_id, self.audience):
            if str(UUID(value)) != value:
                raise ValueError("Use a canonical tenant/API application ID")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", self.permission):
            raise ValueError("Use one exposed API permission name, not a scope URL")
        if len(self.pseudonym_key) < 32:
            raise ValueError("A pseudonym key needs at least 32 bytes")
        labels = dict(self.subject_labels)
        for object_id, label in labels.items():
            if not isinstance(object_id, str) or str(UUID(object_id)) != object_id:
                raise ValueError("Subject label keys must be canonical object IDs")
            if not isinstance(label, str) or label == "unmapped" or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", label):
                raise ValueError("Use short non-identifying subject labels, never emails")
        if len(set(labels.values())) != len(labels):
            raise ValueError("Each approved subject needs a distinct label")
        object.__setattr__(self, "subject_labels", MappingProxyType(labels))

    @property
    def issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def oauth_scope(self) -> str:
        return f"api://{self.audience}/{self.permission}"

    def authenticate(self, token: str, signing_key) -> Principal:
        try:
            claims = jwt.decode(
                token, signing_key, algorithms=["RS256"],
                audience=self.audience, issuer=self.issuer,
                options={
                    "strict_aud": True,
                    "require": ["iss", "aud", "exp", "iat", "tid", "oid", "sub", "azp", "ver"],
                    # Validate dates below without PyJWT's permissive int coercion.
                    "verify_exp": False, "verify_iat": False, "verify_nbf": False,
                },
            )
        except jwt.InvalidTokenError:
            raise InvalidAccessToken("invalid_access_token") from None
        if claims["tid"] != self.tenant_id or claims["ver"] != "2.0":
            raise InvalidAccessToken("invalid_access_token")
        for name in ("exp", "iat", "nbf"):
            if name in claims and type(claims[name]) is not int:
                raise InvalidAccessToken("invalid_access_token")
        now = time.time()
        if claims["exp"] <= now or claims["iat"] > now or claims.get("nbf", 0) > now:
            raise InvalidAccessToken("invalid_access_token")
        for name in ("oid", "azp"):
            value = claims[name]
            if not isinstance(value, str):
                raise InvalidAccessToken("invalid_access_token")
            try:
                valid = str(UUID(value)) == value
            except ValueError:
                valid = False
            if not valid:
                raise InvalidAccessToken("invalid_access_token")
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise InvalidAccessToken("invalid_access_token")
        scope = claims.get("scp", "")
        if not isinstance(scope, str):
            raise InvalidAccessToken("invalid_access_token")
        scopes = frozenset(scope.split())
        return Principal(
            tenant=self.tenant_id, object_id=claims["oid"], client_id=claims["azp"],
            scopes=scopes, delegated=bool(scopes) and claims.get("idtyp") in (None, "user"),
            expires_at=claims["exp"],
        )

    def authorize(self, principal: Principal) -> None:
        if (
            principal.tenant != self.tenant_id or not principal.delegated
            or self.permission not in principal.scopes
        ):
            raise InsufficientPermission("delegated_permission_required")

    def _pseudonym(self, value: str) -> str:
        return hmac.new(self.pseudonym_key, value.encode(), hashlib.sha256).hexdigest()

    def receipt(self, principal: Principal) -> dict:
        self.authorize(principal)
        return {
            "subject": self._pseudonym(f"user:{principal.tenant}:{principal.object_id}"),
            "subject_label": self.subject_labels.get(principal.object_id, "unmapped"),
            "tenant": self._pseudonym(f"tenant:{principal.tenant}"),
            "audience": self.audience,
            "scopes": sorted(principal.scopes),
            "auth_kind": "delegated",
            "correlation_id": uuid4().hex,
        }

    def items(self, principal: Principal) -> dict:
        owner = self.receipt(principal)["subject"]
        return {
            "owner_subject": owner,
            "items": [
                {"id": f"{owner[:24]}-{i}", "title": f"Synthetic item {i}", "status": "read-only"}
                for i in (1, 2)
            ],
        }
