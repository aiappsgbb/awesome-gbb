# Native CI standing-prerequisite gate

**Partial remediation of [#488](https://github.com/aiappsgbb/awesome-gbb/issues/488)
and [#492](https://github.com/aiappsgbb/awesome-gbb/issues/492), not live acceptance.**
The `native-preflight` step in `skill-test.yml` runs immediately after matrix
checkout, before Azure login, tool installation or Copilot/native execution.
It selects exactly `foundry-mcp-auth` and `foundry-mcp-aca-jobs`; other legs
retain their existing path.

The stdlib-only [`scripts/native-ci-preflight.py`](../../scripts/native-ci-preflight.py)
reads these existing fixture inputs from explicit same-name secret bindings:

| Leg | Required input | Offline check |
|---|---|---|
| `foundry-mcp-auth` | `MCP_AUTH_NETWORK_SMOKE_APPROVED` | Exact literal `yes`; no inferred or default approval |
| `foundry-mcp-auth` | `MCP_AUTH_SMOKE_ENDPOINT` | HTTPS, valid host/port, path ending in `/mcp`, no userinfo/query/fragment |
| `foundry-mcp-aca-jobs` | `MCP_AUTH_APP_CLIENT_ID` | Canonical hyphenated UUID, not an audience URI or consent flag |
| `foundry-mcp-aca-jobs` | `MCP_ACA_JOBS_COSMOS_ENDPOINT` | HTTPS account origin, optional trailing `/` and valid port |
| `foundry-mcp-aca-jobs` | `MCP_ACA_JOBS_STORAGE_ACCOUNT_URL` | HTTPS account origin, optional trailing `/` and valid port |

Empty and whitespace-only inputs fail. URLs with whitespace, control characters,
backslashes or encoded control characters fail; no values are normalized or
repaired. Host validation is syntactic only, with no DNS or service lookup.
The approved auth inputs are forwarded only to that leg, identically in the
initial and retry consumer steps. The Jobs bindings are unchanged. Shared
workflow identity/project prerequisites retain their existing gates; this
step deliberately checks only the five skill-specific standing inputs.

## Interpreting a run

Failure returns exit 1 and exactly one sanitized classification:
`NATIVE_CI_PREFLIGHT=FAIL <code> <field>`. Codes are `MISSING_ENV`,
`UNAPPROVED`, `INVALID_ENDPOINT` or `INVALID_IDENTIFIER`; malformed CLI
arguments produce `NATIVE_CI_PREFLIGHT=FAIL ARGUMENTS`. Output contains only
fixed tokens and variable names, never supplied values, private hosts,
credentials or parser exceptions.

This mandatory step has no `continue-on-error`: a failure prevents both the
initial consumer launch and its retry. Do not retry missing or unapproved
configuration to chase a green result. The existing unconditional audit can
also report a missing transcript, and artifact upload can report no files;
the earlier prerequisite classification is the actionable cause. Audit,
aggregate and required-check semantics have not changed.

`NATIVE_CI_PREFLIGHT=PASS CONFIG_ONLY` means the supplied configuration passed
offline checks, **not** that a smoke ran. The preflight never writes a
`SMOKE_RESULT` marker. Only the unchanged real fixture may produce its native
result. No resources, approvals, secrets or RBAC are created, retrieved or
renewed by this script.

## Remaining operator and live-proof gates

Supplying a syntactically valid endpoint does not authorize it. The explicit
approval must come from the owner for the intended target/runner; this boolean
does not encode approval lifetime or independently bind tenant/scope.
No approved CI inputs are created by this change. The Jobs app client ID is
an app-only caller prerequisite, **not delegated user consent**. Existing
Cosmos/storage resources and documented pre-granted permissions, including
Storage Blob Data Contributor, still require separately authorized live proof.

The auth fixture's scoped PRM HTTP 200 with exact resource/tenant/scope and
anonymous MCP initialize HTTP 401 with the correct challenge remain real
network assertions. A canonical deterministic HTTP probe and its live runner
execution are unresolved in #492. Offline preflight tests do not replace
those assertions or the separate
[delegated/Playground validation record](foundry-mcp-auth-validation.md).
Selection/dependency fanout, main/scheduled canaries and quarantine remain
unchanged. AgentOps approval lifecycle [#491](https://github.com/aiappsgbb/awesome-gbb/issues/491)
is explicitly out of scope; no approval is renewed.

Offline regression command:

```bash
python3 -m unittest scripts.tests.test_native_ci_preflight -v
```
