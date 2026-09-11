# Delegated auth resource-server reachability smoke - NOT delegated E2E

This fixture does NOT certify user identity, interactive consent, late consent,
refresh, or any of the four Playground acceptance rows. Those require
`playground.md` and sanitized operator evidence.

**Gate B required.** CI inputs for this new candidate have not been provisioned.
Do not deploy infrastructure, register apps, create connections, grant roles,
request personal tokens or open/approve consent. Missing inputs are a failure,
not a reason to install tools, discover another subscription or use public
fallbacks. The runner must already have approved network reachability.

**CRITICAL - never invoke `copilot` recursively.** You are the running CLI.
Do not overwrite the transcript or treat this as a repository audit.

1. Acknowledge `skills/foundry-mcp-auth/SKILL.md`. Read its support boundary.
2. Require `MCP_AUTH_NETWORK_SMOKE_APPROVED=yes` and an approved HTTPS
   `MCP_AUTH_SMOKE_ENDPOINT` ending in `/mcp`, with no userinfo, query or
   fragment. If absent, write the failure marker below and stop.
3. With no Authorization header, request the endpoint's scoped PRM URL
   `/.well-known/oauth-protected-resource/mcp`. Require HTTP 200, `resource`
   exactly matching the approved endpoint, a tenant-specific Entra
   authorization server and the intended custom scope.
4. POST MCP initialize anonymously with proper JSON and
   `Accept: application/json, text/event-stream`. Require HTTP 401 and a
   `WWW-Authenticate` resource-metadata challenge. A 200 is FAIL, not reachability
   success. Never print cookies or entire headers; record only status and
   `NETWORK_AUTH_BOUNDARY_ONLY`.
5. Only after these checks, write exactly
   `printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-auth-smoke-result`.
   On any missing prerequisite/error write
   `printf 'SMOKE_RESULT=FAIL network/auth prerequisite or probe failed\n' > /tmp/foundry-mcp-auth-smoke-result`.

The marker proves only this narrow network/anonymous-auth boundary. It does
not waive `playground.md`, supply missing user identities, or permit release.
