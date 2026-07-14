#!/usr/bin/env python3
"""Resolve the configured Foundry project endpoint to one ARM resource ID."""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlparse


def resolve_foundry_project(
    *,
    account_endpoint: str,
    project_endpoint: str,
    subscription_id: str,
    resources: object,
) -> str:
    """Return the sole ARM ID matching the configured account and project."""
    account_url = urlparse(account_endpoint)
    account_host = (account_url.hostname or "").casefold()
    account_suffix = ".cognitiveservices.azure.com"
    if (
        account_url.scheme.casefold() != "https"
        or not account_host.endswith(account_suffix)
        or account_host == account_suffix.removeprefix(".")
        or account_url.path not in ("", "/")
        or account_url.query
        or account_url.fragment
    ):
        raise ValueError("invalid Azure AI account endpoint")
    account_name = account_host[: -len(account_suffix)]

    project_url = urlparse(project_endpoint)
    project_match = re.fullmatch(r"/api/projects/([^/]+)/?", project_url.path)
    if (
        project_url.scheme.casefold() != "https"
        or (project_url.hostname or "").casefold()
        != f"{account_name}.services.ai.azure.com"
        or project_match is None
        or project_url.query
        or project_url.fragment
    ):
        raise ValueError(
            "configured Foundry project endpoint does not match the account"
        )
    project_name = project_match.group(1)

    subscription_id = subscription_id.strip()
    if not subscription_id or "/" in subscription_id:
        raise ValueError("invalid Azure subscription ID")
    if not isinstance(resources, list):
        raise ValueError("Azure project resource inventory must be a JSON list")

    subscription_prefix = f"/subscriptions/{subscription_id}/".casefold()
    project_suffix = (
        "/providers/Microsoft.CognitiveServices/accounts/"
        f"{account_name}/projects/{project_name}"
    ).casefold()
    matches = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        resource_id = resource.get("id")
        if not isinstance(resource_id, str):
            continue
        folded_id = resource_id.casefold()
        if folded_id.startswith(subscription_prefix) and folded_id.endswith(
            project_suffix
        ):
            matches.append(resource_id)

    if len(matches) != 1:
        raise ValueError(
            "expected exactly one ARM ID for the configured Foundry project; "
            f"found {len(matches)}"
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-endpoint", required=True)
    parser.add_argument("--project-endpoint", required=True)
    parser.add_argument("--subscription-id", required=True)
    args = parser.parse_args()

    try:
        resources = json.load(sys.stdin)
        project_id = resolve_foundry_project(
            account_endpoint=args.account_endpoint,
            project_endpoint=args.project_endpoint,
            subscription_id=args.subscription_id,
            resources=resources,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(project_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
