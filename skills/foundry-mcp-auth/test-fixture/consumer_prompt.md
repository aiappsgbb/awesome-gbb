# Execute delegated-auth reachability smoke now - NOT delegated E2E

You are the running test consumer, **not a repository editor or reviewer**.
Your first action MUST execute the complete Bash block below verbatim. Do not
inspect, edit or repair this fixture, SKILL.md, tests, workflow or dependency
map. Do not substitute a source audit for HTTP execution.
**CRITICAL - never invoke `copilot` recursively.** The existing workflow owns
the runner and transcript.

**Gate B required.** The existing approval must be exactly
`MCP_AUTH_NETWORK_SMOKE_APPROVED=yes`; the existing approved
`MCP_AUTH_SMOKE_ENDPOINT` must be HTTPS and end in `/mcp`. Missing inputs fail
closed. No deployment, app registration, connection creation, token acquisition,
consent, role grant, network change, public fallback or alternate endpoint.
Use the independently declared `MCP_AUTH_SMOKE_ISSUER` and
`MCP_AUTH_SMOKE_SCOPE` exactly. Validate the tenant-specific Entra v2 issuer
against the supplied `AZURE_TENANT_ID` and the custom API scope shape before
network access. Missing or malformed expected bindings fail closed. Never
derive them from the response, the Jobs `MCP_AUTH_APP_CLIENT_ID`, or a sample
permission name. Do not log supplied issuer/scope values.

This probe sends **no Authorization header** and makes only two requests:
scoped PRM GET must be 200, anonymous MCP initialize must be 401 with the exact
resource-metadata challenge. HTTP 200 on initialize is FAIL. Redirects fail
without following them. It does not certify user identity, consent, refresh
or Playground acceptance; those remain separate.

## Run the canonical probe

```bash
echo "skills/foundry-mcp-auth/SKILL.md"
python3 - <<'PY'
import importlib.util
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ProbeFailure(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def require(condition, code):
    if not condition:
        raise ProbeFailure(code)


def expected_bindings(environ):
    values = {}
    for name in ("MCP_AUTH_SMOKE_ISSUER", "MCP_AUTH_SMOKE_SCOPE", "AZURE_TENANT_ID"):
        value = environ.get(name, "")
        require(isinstance(value, str) and bool(value.strip()), f"MISSING_ENV {name}")
        values[name] = value
    guid = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
    match = re.fullmatch(rf"https://login\.microsoftonline\.com/({guid})/v2\.0",
                         values["MCP_AUTH_SMOKE_ISSUER"])
    require(match is not None, "INVALID_ISSUER MCP_AUTH_SMOKE_ISSUER")
    require(re.fullmatch(guid, values["AZURE_TENANT_ID"]) is not None,
            "INVALID_IDENTIFIER AZURE_TENANT_ID")
    require(match.group(1).lower() == values["AZURE_TENANT_ID"].lower(),
            "ISSUER_TENANT_MISMATCH MCP_AUTH_SMOKE_ISSUER")
    require(re.fullmatch(rf"api://{guid}/[A-Za-z][A-Za-z0-9_.-]*",
                         values["MCP_AUTH_SMOKE_SCOPE"]) is not None,
            "INVALID_SCOPE MCP_AUTH_SMOKE_SCOPE")
    return values["MCP_AUTH_SMOKE_ISSUER"], values["MCP_AUTH_SMOKE_SCOPE"]


def exchange(opener, request):
    try:
        response = opener.open(request, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        return response.code, response.headers, response.read(65537)


def main(environ, opener, marker):
    marker.write_text("SMOKE_RESULT=FAIL probe not completed\n", encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location("native_preflight", "scripts/native-ci-preflight.py")
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)
        try:
            preflight.validate("foundry-mcp-auth", environ)
        except preflight.PrerequisiteError as error:
            raise ProbeFailure(str(error)) from None
        endpoint = environ["MCP_AUTH_SMOKE_ENDPOINT"]
        expected_issuer, expected_scope = expected_bindings(environ)
        parts = urlsplit(endpoint)
        metadata_url = urlunsplit((parts.scheme, parts.netloc,
                                  "/.well-known/oauth-protected-resource" + parts.path, "", ""))
        status, _, body = exchange(opener, Request(metadata_url, headers={"Accept": "application/json"}))
        print(f"PRM_STATUS={status}")
        require(status == 200, "PRM_NOT_200")
        require(len(body) <= 65536, "PRM_TOO_LARGE")
        metadata = json.loads(body)
        require(isinstance(metadata, dict), "PRM_NOT_OBJECT")
        require(metadata.get("resource") == endpoint, "PRM_RESOURCE_MISMATCH")
        require(metadata.get("authorization_servers") == [expected_issuer], "PRM_ISSUER_MISMATCH")
        require(metadata.get("scopes_supported") == [expected_scope], "PRM_SCOPE_MISMATCH")
        payload = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "anonymous-ci-probe", "version": "1.0"}},
        }).encode("utf-8")
        status, headers, _ = exchange(opener, Request(
            endpoint, data=payload, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
        ))
        print(f"INITIALIZE_STATUS={status}")
        require(status == 401, "INITIALIZE_NOT_401")
        challenge = headers.get("WWW-Authenticate", "")
        require(re.match(r"(?i)^Bearer\s", challenge) is not None, "CHALLENGE_NOT_BEARER")
        references = re.findall(r'(?i)\bresource_metadata="([^"]+)"', challenge)
        require(references == [metadata_url], "CHALLENGE_METADATA_MISMATCH")
    except (ProbeFailure, OSError, URLError, json.JSONDecodeError, UnicodeError) as error:
        code = str(error) if isinstance(error, ProbeFailure) else type(error).__name__
        marker.write_text(f"SMOKE_RESULT=FAIL {code}\n", encoding="utf-8")
        print(f"NETWORK_AUTH_PROBE=FAIL {code}")
        return 1
    print("NETWORK_AUTH_BOUNDARY_ONLY")
    marker.write_text("SMOKE_RESULT=PASS\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dict(os.environ), build_opener(NoRedirect()),
                          Path("/tmp/foundry-mcp-auth-smoke-result")))
PY
```

The block writes the deterministic marker itself and returns nonzero on failure.
Do not overwrite it with a prose verdict. If the Bash tool denies execution,
report that denial and stop; do not alter paths, permissions, source or approval.
After execution, report only the sanitized outcome. No further probe, repair,
token request or retry is authorized by this fixture.
