#!/usr/bin/env python3
"""Bounded anonymous auth-boundary probe; never delegated E2E or consent."""

from __future__ import annotations

import importlib.util
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import signal
import socket
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MARKER = Path("/tmp/foundry-mcp-auth-smoke-result")
MAX_BYTES = 65536
TIMEOUT_SECONDS = 15
SKILL = "foundry-mcp-auth"
spec = importlib.util.spec_from_file_location(
    "native_ci_preflight", Path(__file__).with_name("native-ci-preflight.py"),
)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class ProbeError(Exception):
    """Finite public error code, never a response, header or private URL."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError("REDIRECT")


def request(method, url, body=None):
    # No proxy, cookie jar, auth handler or inherited bearer-token source.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    headers = {"Accept": "application/json, text/event-stream"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        try:
            response = opener.open(req, timeout=TIMEOUT_SECONDS)
        except HTTPError as error:
            response = error
        with response:
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ProbeError("RESPONSE_TOO_LARGE")
            return response.code, response.headers, content
    except (URLError, TimeoutError, socket.timeout, ssl.SSLError, OSError, HTTPException):
        raise ProbeError("NETWORK") from None


def metadata_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProbeError("PRM_JSON")
            result[key] = value
        return result

    def constant(_):
        raise ProbeError("PRM_JSON")

    try:
        document = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeError("PRM_JSON") from None
    if not isinstance(document, dict):
        raise ProbeError("PRM_JSON")
    return document


def check_challenge(headers, metadata_url):
    values = headers.get_all("WWW-Authenticate", [])
    if len(values) != 1 or len(values[0]) > MAX_BYTES:
        raise ProbeError("CHALLENGE")
    match = re.fullmatch(r"(?i:Bearer)[ \t]+(.+)", values[0])
    if not match:
        raise ProbeError("CHALLENGE")
    remaining = match[1]
    parameters = {}
    while remaining:
        match = re.match(
            r'([A-Za-z][A-Za-z0-9_-]*)="([^"\\\x00-\x1f\x7f]*)"(?:,[ \t]*|$)',
            remaining,
        )
        if not match or match[1].lower() in parameters:
            raise ProbeError("CHALLENGE")
        parameters[match[1].lower()] = match[2]
        remaining = remaining[match.end():]
        if match[0].rstrip().endswith(",") and not remaining:
            raise ProbeError("CHALLENGE")
    if parameters.get("resource_metadata") != metadata_url:
        raise ProbeError("CHALLENGE")


def probe(environ, transport=request):
    preflight.validate(SKILL, environ)
    endpoint = environ["MCP_AUTH_SMOKE_ENDPOINT"]
    url = urlsplit(endpoint)
    metadata_url = f"{url.scheme}://{url.netloc}/.well-known/oauth-protected-resource{url.path}"
    status, _, body = transport("GET", metadata_url)
    if status != 200:
        raise ProbeError("PRM_STATUS")
    if len(body) > MAX_BYTES:
        raise ProbeError("RESPONSE_TOO_LARGE")
    document = metadata_json(body)
    for key, expected in (
        ("resource", endpoint),
        ("authorization_servers", [environ["MCP_AUTH_SMOKE_ISSUER"]]),
        ("scopes_supported", [environ["MCP_AUTH_SMOKE_SCOPE"]]),
    ):
        if document.get(key) != expected:
            raise ProbeError("PRM_BINDING")
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "ci-auth-boundary", "version": "1.0.0"},
        },
    }).encode("utf-8")
    status, headers, _ = transport("POST", endpoint, body)
    if status != 401:
        raise ProbeError("INITIALIZE_STATUS")
    check_challenge(headers, metadata_url)


def main(environ=None, *, transport=request, marker=MARKER):
    # Replace stale success before any validation or request can fail.
    marker.write_text("SMOKE_RESULT=FAIL probe incomplete\n", encoding="ascii")
    try:
        probe(dict(os.environ) if environ is None else environ, transport)
    except preflight.PrerequisiteError as error:
        code = str(error)
    except ProbeError as error:
        code = str(error)
    else:
        marker.write_text("SMOKE_RESULT=PASS\n", encoding="ascii")
        print("MCP_AUTH_NETWORK_SMOKE=PASS NETWORK_AUTH_BOUNDARY_ONLY")
        return 0
    marker.write_text(f"SMOKE_RESULT=FAIL {code}\n", encoding="ascii")
    print(f"MCP_AUTH_NETWORK_SMOKE=FAIL {code}")
    return 1


if __name__ == "__main__":
    def deadline(_signum, _frame):
        raise ProbeError("TIMEOUT")

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(40)
    try:
        sys.exit(main())
    finally:
        signal.alarm(0)
