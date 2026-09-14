#!/usr/bin/env python3
"""Offline standing-prerequisite gate for two native CI legs, not live proof.

The fixtures remain the source of truth for execution and smoke markers.
This gate reads only explicit inputs: no discovery, I/O beyond status output,
credential lookup, approval renewal, provisioning or native execution.
"""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from urllib.parse import urlsplit
import uuid


SKILLS = ("foundry-mcp-auth", "foundry-mcp-aca-jobs")


class PrerequisiteError(Exception):
    """Contains only fixed code/field tokens, never supplied values."""


def required(environ: dict[str, str], name: str) -> str:
    value = environ.get(name, "")
    if not value.strip():
        raise PrerequisiteError(f"MISSING_ENV {name}")
    return value


def https_endpoint(value: str, name: str, *, mcp: bool = False) -> None:
    # urlsplit silently strips some whitespace/control characters; reject first.
    if (
        any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
        or any(char in value for char in ("\\", "?", "#"))
        or re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", value, re.IGNORECASE)
    ):
        raise PrerequisiteError(f"INVALID_ENDPOINT {name}")
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        port = url.port
        if ":" in host:
            ipaddress.IPv6Address(host)
            valid_host = "%" not in host
        else:
            valid_host = bool(re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?",
                host,
            )) and len(host) <= 253
        valid = (
            url.scheme == "https"
            and valid_host
            and url.username is None
            and url.password is None
            and not url.netloc.endswith(":")
            and (port is None or 1 <= port <= 65535)
            and (url.path.endswith("/mcp") if mcp else url.path in ("", "/"))
        )
    except ValueError:
        raise PrerequisiteError(f"INVALID_ENDPOINT {name}") from None
    if not valid:
        raise PrerequisiteError(f"INVALID_ENDPOINT {name}")


def validate(skill: str, environ: dict[str, str]) -> None:
    if skill == "foundry-mcp-auth":
        approval = required(environ, "MCP_AUTH_NETWORK_SMOKE_APPROVED")
        if approval != "yes":
            raise PrerequisiteError("UNAPPROVED MCP_AUTH_NETWORK_SMOKE_APPROVED")
        https_endpoint(
            required(environ, "MCP_AUTH_SMOKE_ENDPOINT"), "MCP_AUTH_SMOKE_ENDPOINT",
            mcp=True,
        )
    else:
        name = "MCP_AUTH_APP_CLIENT_ID"
        value = required(environ, name)
        try:
            valid_id = str(uuid.UUID(value)) == value.lower()
        except ValueError:
            valid_id = False
        if not valid_id:
            raise PrerequisiteError(f"INVALID_IDENTIFIER {name}")
        for name in ("MCP_ACA_JOBS_COSMOS_ENDPOINT", "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"):
            https_endpoint(required(environ, name), name)


def main(argv: list[str], environ: dict[str, str]) -> int:
    try:
        if len(argv) != 1 or argv[0] not in SKILLS:
            raise PrerequisiteError("ARGUMENTS")
        validate(argv[0], environ)
    except PrerequisiteError as error:
        print(f"NATIVE_CI_PREFLIGHT=FAIL {error}")
        return 1
    print("NATIVE_CI_PREFLIGHT=PASS CONFIG_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], dict(os.environ)))
