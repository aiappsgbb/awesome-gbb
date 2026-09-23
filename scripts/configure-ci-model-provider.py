#!/usr/bin/env python3
"""Select the CI driver provider without changing fixture/project endpoints."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Mapping
from urllib.parse import urlsplit


def configure(env: Mapping[str, str]) -> dict[str, str]:
    requested = env.get("CI_MODEL_PROVIDER", "foundry")
    if requested not in {"foundry", "citadel"}:
        raise ValueError("CI_MODEL_PROVIDER must be foundry or citadel")
    exemption = env.get("CI_MODEL_PROVIDER_EXEMPTION", "")
    if exemption not in {"", "agentops"}:
        raise ValueError("Unknown CI model provider exemption")
    provider = "foundry" if exemption == "agentops" else requested
    key = env.get("CITADEL_CI_API_KEY", "") if provider == "citadel" else ""
    bearer = env.get("COPILOT_PROVIDER_BEARER_TOKEN", "") if provider == "foundry" else ""
    if provider == "citadel" and not key:
        raise ValueError("Citadel routing requires CITADEL_CI_API_KEY")
    if provider == "foundry" and not bearer:
        raise ValueError("Foundry routing requires the minted provider bearer token")
    endpoint_name = "CITADEL_CI_GATEWAY_URL" if provider == "citadel" else "FOUNDRY_PROJECT_ENDPOINT"
    endpoint = env.get(endpoint_name, "")
    if any(character in endpoint for character in "\r\n"):
        raise ValueError(f"{endpoint_name} must be a single-line URL")
    try:
        url = urlsplit(endpoint)
        port = url.port
    except ValueError:
        raise ValueError(f"{endpoint_name} is not a valid URL") from None
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or port not in (None, 443)):
        raise ValueError(f"{endpoint_name} must be an HTTPS URL without credentials, query or fragment")
    if provider == "citadel":
        if not url.hostname.endswith(".azure-api.net") or url.path not in {"", "/"}:
            raise ValueError("CITADEL_CI_GATEWAY_URL must be the APIM host, without an API path")
    elif not url.hostname.endswith(".services.ai.azure.com") or not re.fullmatch(r"/api/projects/[^/]+/?", url.path):
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT must identify a Foundry project")
    model = "gpt-6-luna" if provider == "citadel" else "gpt-5.4-mini"
    values = {
        "CI_EFFECTIVE_MODEL_PROVIDER": provider,
        "COPILOT_PROVIDER_TYPE": "azure",
        "COPILOT_PROVIDER_BASE_URL": endpoint.rstrip("/"),
        "COPILOT_PROVIDER_MODEL_ID": model,
        "COPILOT_PROVIDER_WIRE_MODEL": model,
        "COPILOT_PROVIDER_WIRE_API": "responses",
        "COPILOT_PROVIDER_AZURE_API_VERSION": "2025-04-01-preview" if provider == "citadel" else "",
        "COPILOT_PROVIDER_API_KEY": key,
        "COPILOT_PROVIDER_BEARER_TOKEN": bearer,
        "COPILOT_PROVIDER_API_KEY_COMMAND": "",
        "COPILOT_PROVIDER_HEADERS": "",
    }
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ValueError("Provider values must be single-line; refusing environment-file injection")
    return values


def main() -> None:
    values = configure(os.environ)
    destination = os.environ.get("GITHUB_ENV")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not destination:
        raise ValueError("This writer requires GitHub Actions and GITHUB_ENV")
    for field in ("COPILOT_PROVIDER_API_KEY", "COPILOT_PROVIDER_BEARER_TOKEN"):
        if values[field]:
            print(f"::add-mask::{values[field]}")
    with Path(destination).open("a", encoding="utf-8") as output:
        output.writelines(f"{key}={value}\n" for key, value in values.items())
    print(f"CI driver provider: {values['CI_EFFECTIVE_MODEL_PROVIDER']}; model: {values['COPILOT_PROVIDER_MODEL_ID']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"::error::CI provider configuration failed: {error}", file=sys.stderr)
        raise SystemExit(1)
