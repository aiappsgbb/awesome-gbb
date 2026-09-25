"""Canonical validation-only, app-only ACA policy with explicit caller ACL.

Source of truth for `../../SKILL.md § Layer 1 — Identity perimeter: ACA built-in auth`.
No Azure calls or credentials; API audience is never inferred as caller identity.
"""

import argparse
import json
import uuid


def guid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value.lower():
        raise ValueError("An exact GUID is required")
    return value.lower()


def build(tenant, audience, callers):
    tenant, audience = guid(tenant), guid(audience)
    if not isinstance(callers, list) or not callers:
        raise ValueError("Explicit nonempty caller client-ID allowlist required")
    callers = [guid(caller) for caller in callers]
    if len(set(callers)) != len(callers) or audience in callers:
        raise ValueError("Caller IDs must be distinct and cannot be the resource audience")
    return {"properties": {
        "platform": {"enabled": True},
        "globalValidation": {"unauthenticatedClientAction": "Return401"},
        "identityProviders": {"azureActiveDirectory": {
            "enabled": True,
            "registration": {"clientId": audience, "openIdIssuer": f"https://login.microsoftonline.com/{tenant}/v2.0"},
            "validation": {
                "allowedAudiences": [f"api://{audience}", audience],
                "defaultAuthorizationPolicy": {"allowedApplications": callers},
            },
        }},
    }}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--caller", required=True, action="append")
    args = parser.parse_args()
    print(json.dumps(build(args.tenant, args.audience, args.caller)))
