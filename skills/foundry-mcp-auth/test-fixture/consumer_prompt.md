# Delegated auth resource-server reachability smoke - NOT delegated E2E

This fixture does NOT certify user identity, interactive consent, late consent,
refresh, or any of the four Playground acceptance rows. Those require
`playground.md` and sanitized operator evidence.

**Gate B required.** A configured input is not proof of owner authorization.
Do not deploy infrastructure, register apps, create connections, grant roles,
request personal tokens or open/approve consent. Missing inputs are a failure,
not a reason to install tools, discover another subscription or use public
fallbacks. The runner must already have approved network reachability.

**CRITICAL - never invoke `copilot` recursively.** You are the running CLI.
Do not overwrite the transcript or treat this as a repository audit.

## Step 1 - execute the canonical probe (MANDATORY first and final Bash action)

This is an execution task, not a request to inspect, review or edit repository
files. Do not reimplement HTTP checks, write a success marker yourself, or
return a prose-only review. Execute exactly this block from the checkout:

```bash
set -euo pipefail
echo "skills/foundry-mcp-auth/SKILL.md"
printf 'SMOKE_RESULT=FAIL probe did not complete\n' > /tmp/foundry-mcp-auth-smoke-result
python3 -I scripts/mcp-auth-network-smoke.py
```

The canonical probe requires `MCP_AUTH_NETWORK_SMOKE_APPROVED=yes`,
`MCP_AUTH_SMOKE_ENDPOINT`, `MCP_AUTH_SMOKE_ISSUER` (tenant-specific Entra v2),
and `MCP_AUTH_SMOKE_SCOPE` (the exact exposed custom API scope). The owner must
approve this tuple and the runner's reachability before configuration.
The endpoint is the exact expected resource; no target discovery or substitution.

It requests only the scoped PRM URL and an anonymous MCP initialize, without
credentials, redirects or cookies. PRM must return HTTP 200 with the exact
resource, sole issuer and sole scope. Initialize must return HTTP 401 with
the exact scoped resource-metadata Bearer challenge. HTTP 200 on initialize,
missing or invalid inputs, malformed metadata/challenges, and network errors
all remain FAIL. Each request has a 15-second timeout and a 64-KiB body bound.
The helper writes the byte-exact success marker only after both assertions.
Public output contains sanitized codes, never endpoint/issuer/scope values,
response bodies, headers or credentials.

The marker proves only this narrow network/anonymous-auth boundary. It does
not waive `playground.md`, supply missing user identities, or permit release.
