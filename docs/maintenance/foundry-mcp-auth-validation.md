# Foundry MCP auth validation notes

**UNRELEASED - THREE LIVE DELEGATED PATHS VERIFIED.** Proposed skill 1.1.0 /
catalog 4.32.0. Not a four-path or multi-user release certification.
This record is not approval to deploy or publish. No real environment identifiers,
tokens, consent links, secrets or user data are stored here.

This is the single detailed test/triage record. Reusable instructions remain
in [SKILL.md](../../skills/foundry-mcp-auth/SKILL.md), connection setup in
[connection-contract.md](../../skills/foundry-mcp-auth/references/connection-contract.md),
and repeatable operations in
[demo-runbook.md](../../skills/foundry-mcp-auth/references/demo-runbook.md).
Moving this history out of the skill does not change the tested code or
convert any unproven acceptance row into PASS.

## Source and evidence binding

The original 1.0.0 checkpoint binding below remains historical. The 1.1.0
opt-in token-proof revision changes only the server implementation; its
fresh source binding and live result are recorded in the next section.

The manual run's source manifest was recorded on **2026-09-11 at 08:59:40 UTC**
while the source was uncommitted, on base
`2db28d1f52bf288f2d0fd40b7c8beb913ceeee09`. The seven canonical Python modules
below were subsequently verified byte-for-byte against that manifest and
checkpoint commit **`a6c8cb8bacf17e2d6ad266aba292312a7e495424`**. They also
match the follow-up triage snapshot **`50085721ed3c5c8add8fb61d6d705ca28b48b40c`**.
Documentation-only consolidation does not constitute another live run.

Paths below are relative to `skills/foundry-mcp-auth/references/python/`.

| Canonical file | SHA-256 recorded with live evidence |
|---|---|
| `authorization.py` | `c42f0908cfccd8761eb58020856b61ea1699b18287df53eb184b7d7e32ce5093` |
| `configure_foundry.py` | `c347b7beca103a8c615dfc4d66cb72477b5bc97c19d2189b73c8dc3197d76a85` |
| `delegated_server.py` | `6557b220cd94a4f7c2686316a371676a48ebf03a329979e8fa7d5d7e7279fcc3` |
| `hosted_agent.py` | `c6aab10bbc5196ab88c0f98dc1b2082e00caa199025f6378606aa91323a40410` |
| `invoke_agent.py` | `2cd4d94ade5b33c401ea8f52e5f3e66171eb26806628ab5156f44bc8483c2adf` |
| `provision_connection.py` | `7c9aff8f0d10edcd227b72eb740708fa0c55e413a9cfe19192575c4c72e89345` |
| `stage_hosted.py` | `ec54dbcf842fe87ff0aa8c64d82ae142f78a1ebdade327c751212a41162c2321` |

Exact resource/agent versions, image digests, response IDs and receipt-to-audit
correlations remain in private evidence. These source hashes bind canonical
code, not the entire final image or an assertion that every negative test ran
live. No raw transcripts or private configuration are published.

## Fresh inbound bearer proof - 1.1.0

On **2026-09-11 at 12:11 UTC**, a new user-authenticated API run verified the
actual bearer received by the MCP, without using a subject label as identity
evidence. One new MCP image was built/deployed through `azd`; the existing
app's opt-in `MCP_IDENTITY_PROOF_ENABLED=true` setting was enabled without
changing OAuth connections, permissions, other infrastructure or Hosted code.
The operator deployment configuration retains that explicit setting.

The deployed server source SHA-256 is
`63f81351ec898d11c1d1b09175fee07e0bd2aee2d8ac61232db6a58218ebf94b`.
Exact image digest/revision, real IDs, response IDs and token fingerprints
remain in private evidence, not this document.

| Independent check | Fresh result |
|---|---|
| Expected caller | Existing isolated CLI user; independently verified the Foundry access token's RS256 signature with Entra JWKS, permitted issuer/audience, lifetime and delegated scope. No Graph call or model input supplied the expected identity. |
| MCP inbound bearer | Existing strict signature/issuer/custom-audience/lifetime/scope validation unchanged. `who_am_i.verified_token` reads the request's authenticated principal and hashes that request's actual bearer. |
| Identity match | Actual `oid` and `tid` received by MCP equal the independently validated user's object/tenant IDs on all three paths. |
| OAuth boundary | Custom API audience, `demo.read`, expected OAuth client `azp`, unexpired token. The Foundry token and MCP token have different digests and audiences, as required; this proves the same user, not byte-for-byte replay of a Microsoft-audience token. |
| Tool and server evidence | Prompt/direct, Prompt/Toolbox and Hosted/Toolbox each returned actual tool output; all three receipt correlations and token digests matched `delegated_token_proof` server audit events. |
| Privacy/auth regressions | Nine HTTP/MCP tests passed: default-off privacy, opt-in claims from two locally signed users' actual tokens, and anonymous/invalid/app-only rejection. Full candidate local suite: 40 tests. Synthetic test tokens remain distinct from this live Entra proof. |

The ARM update response initially showed stale configuration; a fresh read
confirmed the setting. The driver waited for the new revision to be ready,
without issuing a duplicate configuration write. No raw JWT, consent URL or
real identity claim was added to normal server logs. Opt-in real IDs are
returned only to the authenticated caller and retained only in private evidence.

**Scope:** fresh API execution as the real user, not yet Playground
follow-through, second-user Entra isolation or native Hosted/direct success.
Synthetic business items remain explicitly synthetic; they are not used to
prove token propagation. No Graph, additional grants or downstream OBO
exchange were introduced.

## Limited live evidence

### September 11: successful user-delegated execution

The same GA `2026-05-01` connection request succeeded. Callback registration,
Prompt agent and Toolbox creation completed; the user completed a fresh OAuth
consent link. Both **Prompt -> direct MCP** and **Hosted -> Toolbox -> MCP**
then executed `who_am_i` and `list_my_demo_items` with the real user over
private networking. Actual tool outputs—not assistant claims—contained the
custom API audience, `demo.read`, `auth_kind: delegated`, `subject_label:
user-a` and server-selected synthetic items. Four receipt correlations from
the final two-path run matched MCP server audit.

The successful sequence required an approved Basic project capability host
with platform-managed backing stores, propagation, the correct agent-bound
Hosted endpoint, a writable Hosted session home, standard-only FastMCP
metadata and a refreshed Toolbox/Hosted binding. The project host was added,
not recreated; no public MCP fallback or service identity substitution was used.

After the user requested permanent demo retention, resource expiry tags and
automatic cleanup were removed. The temporary client credential was replaced
with tenant-accepted long validity, without overlapping active keys. Both
delegated paths passed again after rotation. Access-token expiry/refresh and
late-consent revocation remain independent unproven cases.

The canonical reproduction procedure is
[demo-runbook.md](../../skills/foundry-mcp-auth/references/demo-runbook.md).
Exact IDs, digests, response IDs, safe receipts and server correlations are
stored privately with the working-tree source hashes. A draft checkpoint PR
was subsequently authorized; publication as a fully accepted skill remains
separate. Management uses the canonical GA ARM helper.

Prompt/Toolbox also passed using a native `UserEntraToken` connection to the
first-party Toolbox (audience `https://ai.azure.com`) and the same inner
custom OAuth2 MCP connection. No static bearer was stored in the agent.
The separately deployed native Hosted/direct variant returned HTTP success
with completed/empty output and no tool receipts: it does not pass E2E.
Its logs confirm the call was made; no conclusion of universal platform
non-support is drawn from this particular pinned stack.

The final consolidated evidence contains **six actual tool receipts** across
the three paths, all matched to server `tool_allowed` audit events. Expected
safe fields were `subject_label=user-a`, `auth_kind=delegated`, `demo.read`,
custom-audience match and server-selected item ownership. This is real Entra
user-token evidence, not the locally signed tokens used by unit tests.

### Observed failures and corrections

| Phase / symptom | Correction and observation | Evidence limit |
|---|---|---|
| Initial consent callback: `Code ... not found` despite an Entra permission grant | A fresh Hosted consent request was completed manually; subsequent delegated calls worked. | Grant presence alone did not prove Foundry credential storage. Denial/revocation is not certified. |
| Runtime could not resolve private MCP while operator DNS worked | Added the approved Basic project capability host after baseline/what-if; immediate retry still failed, later no-auth control reached MCP/401, then delegated calls passed. | Propagation and before/after behavior were observed; missing host alone was not isolated as a universal root cause. |
| Hosted rejected at project Responses endpoint | Canonical helper uses `get_openai_client(agent_name=...)`; Prompt retains project `agent_reference`. | A completed/empty response is still not PASS. |
| Hosted `session_not_ready`, permission denied under `/home/session/.sessions` | Removed fixed UID 65532 from Hosted Dockerfile; retained the independent ACA server's non-root identity. | Applies to the tested Hosted session mount, not general permission relaxation. |
| `Invalid MCP _meta key name: '_fastmcp'` | Set `include_fastmcp_meta=False`; published fresh Toolbox version and Hosted binding after clean discovery. | Disabled vendor metadata only, never auth. |
| Hosted azd service path contained `..` | Staged canonical inputs inside a standalone deployment root. | No duplicated implementation or global workspace modification. |
| Shared OpenAI/httpx transport closed after first call | `http_client_factory` now supplies a fresh transport per invocation/consent continuation. | Real local two-turn transport regression plus subsequent live use on all three successful paths. |
| Standalone app-only negative probe could not reach MCP after the operator tunnel closed | Recorded NOT DEMONSTRATED; no cloud remediation in this notes-only phase. | No live 403 claim; local signed app-only token rejection is a separate test. |

The recorded deployment toolchain used **azd 1.33.0** with
**`azure.ai.agents` 1.0.0-beta.14**. Actual registry inventory showed seven
build runs; an image-override option was not treated as proof of no remote
build. No build was started by this documentation consolidation.

### September 10: historical platform failure

An explicitly approved bounded cycle on 2026-09-10 provisioned an internal
MCP environment, private DNS, narrow image-pull roles and the two dedicated
Entra registrations. Two native azd remote server builds succeeded. Private
DNS/TLS, health/PRM 200 and anonymous initialize 401 were observed. SDK and
azd management reads used the private tunnel; none of these prove delegated
end-user calls.

Native custom OAuth connection creation failed with HTTP 400 / UserError /
`ConnectorNamespaceCustomConnectorDirectInvokeRequiresApiDefinitionV3`.
ConnectorGateway requires OpenAPI 3.0 for DirectInvoke. No connection was
present on readback; no Prompt/Hosted agent invocation or OAuth consent was
performed. No shared namespace mode, public MCP fallback or extra grant was
used. Sanitized request shape and correlation evidence remain private.

The failure reproduced through azd/connection CLI on ARM
`2025-04-01-preview`, and the standard ARM SDK on GA `2026-05-01` and newest
registered preview `2026-05-15-preview`. The same
`ConnectorNamespaceCustomConnectorDirectInvokeRequiresApiDefinitionV3` code
was returned each time. No documented per-connection definition selector was
established. Unused run-created credentials were revoked after diagnosis;
zero active demo client secrets remained. This is an actionable service
escalation, not evidence that the original customer incident had this cause.

The operator subsequently authorized initial backend tests with their existing
isolated Azure CLI user credentials, with Playground verification later.
That ordering change does not waive downstream OAuth consent or any final
acceptance row. Credential rotation is not a fix for this service error.

## Local evidence boundary

Local working-tree execution on 2026-09-10 and 2026-09-11 (not CI or a release attestation):

| Local check | Result |
|---|---|
| New candidate suites | 39 passed: policy, HTTP/MCP, provisioning/routing, Hosted staging, metadata, real transport lifetime and lifecycle-boundary regressions |
| Private network module contracts | 2 passed; the bounded composition was also provisioned live |
| Related existing suites | 71 passed; combined focused run 112 passed including the two private-network module tests |
| Exact new pin validation script | Passed all three import markers and dependency checks in separate environments |
| Real local server process | Health/PRM returned 200; anonymous MCP initialize returned 401; process stopped afterward |
| Templates/catalog | Bicep compiled locally; both azd manifests matched the official schema; catalog lint and site link checks passed |
| Container images | MCP and Hosted images built through native azd; actual ACR runs and immutable digests recorded privately |

Tests exercised synthetic concurrent users, not interactive Entra users.
Upstream Authlib deprecation notices remain in the old server cohort.

The candidate has local signed-token policy tests, in-process HTTP/MCP
handshake and concurrent identity tests, SDK serialization/write-opt-in tests,
and released-wrapper import/header-context tests in separate environments.
Signing keys and principals in the tests are synthetic. Wrapper context is
simulated, not a trusted Foundry request. Local imports cannot prove the
credential chain, endpoint reachability, consent or real platform delegation.

The final canonical invocation helper was subsequently run against all three
working live paths, not only mocked: their six tool-result receipts matched
server audit. An independent review found that a shared caller-supplied HTTP
client was closed after one turn. The helper now takes a fresh transport
factory, with a real OpenAI/httpx two-turn continuation regression and a
completed/empty-output guard.

### Isolated environment cohorts

Local environments were inspected on 2026-09-11: macOS, Python **3.14.5**.
CI uses Ubuntu/Python **3.12** and must be reported independently. These are
resolved local versions, not a claim of a captured container `pip freeze`.
Bounded installation constraints remain in the three canonical manifests.

| Environment | Resolved packages relevant to the contract |
|---|---|
| Resource server | FastMCP 2.14.7; MCP 1.29.1; PyJWT 2.10.1; httpx 0.28.1 |
| Management | azure-ai-projects 2.6.0; azure-identity 1.25.3; azure-mgmt-resource 23.1.1; httpx 0.28.1; PySocks 1.7.1 |
| Hosted | agent-framework-core 1.16.0; agent-framework-openai 1.14.1; agent-framework-foundry 1.10.4; agent-framework-foundry-hosting 1.0.0b260730; azure-ai-projects 2.3.0; azure-identity 1.25.3; MCP 1.29.1 |
| Hosted server adapters | azure-ai-agentserver-core 2.0.0b7; azure-ai-agentserver-responses 1.0.0b8; azure-ai-agentserver-invocations 1.0.0b6 |

The Foundry provider requires Projects `<2.4`; management 2.6 therefore has
its own environment. OpenAI provider 1.10 satisfied a declared lower bound
but lacked `_feature_usage`; provider 1.14 resolved that import. Do not
override the dependency bounds or combine the independent jobs MCP 2 cohort
with this Hosted MCP 1 cohort.

### Repeatable local commands

From repository root, the following use equivalent new local venv paths;
the recorded runs used pre-existing private venvs with the same manifests.
No Azure identity, endpoint, account lookup or grant is needed.

```bash
python3 -m venv .scratch/mcp-auth-server
.scratch/mcp-auth-server/bin/pip install ./skills/foundry-mcp-auth/templates
python3 -m venv .scratch/mcp-auth-management
.scratch/mcp-auth-management/bin/pip install ./skills/foundry-mcp-auth/templates/management
python3 -m venv .scratch/mcp-auth-hosted
.scratch/mcp-auth-hosted/bin/pip install ./skills/foundry-mcp-auth/templates/hosted

.scratch/mcp-auth-server/bin/python -m unittest \
  scripts.tests.test_foundry_mcp_auth_policy \
  scripts.tests.test_foundry_mcp_auth_contract \
  scripts.tests.test_foundry_mcp_auth_staging
PYTHONPATH=skills/foundry-mcp-auth .scratch/mcp-auth-server/bin/python \
  -m unittest discover -s skills/foundry-mcp-auth/test-fixture -p test_server.py
PYTHONPATH=skills/foundry-mcp-auth .scratch/mcp-auth-management/bin/python \
  -m unittest discover -s skills/foundry-mcp-auth/test-fixture -p test_management.py
PYTHONPATH=skills/foundry-mcp-auth .scratch/mcp-auth-hosted/bin/python \
  -m unittest discover -s skills/foundry-mcp-auth/test-fixture -p test_hosted.py
.scratch/mcp-auth-server/bin/pip check
.scratch/mcp-auth-management/bin/pip check
.scratch/mcp-auth-hosted/bin/pip check
```

Catalog-wide unit discovery additionally needs the dependencies and local
tooling declared in `.github/workflows/skill-test.yml`'s `unit-tests` job.
Do not install those into the Hosted venv:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
python3 scripts/build-site.py --out docs/ --validate
git diff --check
```

The separate pin runner executes `references/upstream-pin.md`'s exact
`validation.script` in isolated temporary directories and asserts its three
`expected_output` import markers. None of those markers certifies Entra
delegation. Live invocation follows the canonical runbook and helper against
operator-approved configuration; private driver commands/identifiers remain
private rather than being relabeled as generic public test output.

## Final acceptance remains unchanged

| Path / behavior | Current status |
|---|---|
| Prompt -> direct custom MCP | LIVE PASS, one real user via API; actual tool receipts matched server audit |
| Hosted -> Toolbox -> custom MCP | LIVE PASS, one real user via API; actual tool receipts matched server audit |
| Prompt -> Toolbox -> custom MCP | LIVE PASS using the native first-party user-token bridge and inner custom OAuth |
| Hosted -> direct custom MCP | Native variant deployed and invoked, but completed with empty output; NOT DEMONSTRATED |
| First user consent | User completed fresh consent successfully; denial and Playground follow-through NOT DEMONSTRATED |
| Late consent / revoked or expired refresh credentials on a shared host | NOT DEMONSTRATED; known host conversion limitation |
| Two independent Entra users, concurrent calls | NOT DEMONSTRATED; synthetic local isolation is a separate result |
| Anonymous MCP rejection | LIVE 401 observed; also covered locally |
| App-only / insufficient-scope and invalid-token matrix | Local signed-token checks passed; standalone live app-only probe was blocked by operator network reachability, not a verified 403 |
| Private runtime paths and consent/Entra egress | Exercised by the three passing delegated API paths; other endpoint combinations remain unproven |
| Literal Entra OBO A->B exchange | NOT IMPLEMENTED; separate optional approved delta |

The live stage was explicitly authorized, including the later project-host
remediation and permanent environment retention. This public record does not
grant permission to modify another environment. CI's unattended reachability
fixture remains distinct from user-delegated evidence. A missing prerequisite
must not be skipped or reported as PASS.

After approved execution, add sanitized evidence linked to the exact candidate
SHA and the [interactive protocol](../../skills/foundry-mcp-auth/test-fixture/playground.md).
Do not substitute a service principal, copied portal token, static bearer
bridge or restarted-per-user host for the final acceptance criteria.

## Checkpoint and CI boundary

This draft is a reviewable checkpoint for the three demonstrated paths, not
permission to merge with the remaining acceptance rows unchecked. Live evidence
was collected manually against the exact canonical source files and mapped to
the candidate in the PR; CI execution is reported separately, never inferred
from the manual result.

The new unattended fixture requires an approved private-reachable endpoint and
`MCP_AUTH_NETWORK_SMOKE_APPROVED=yes`. These inputs are not yet provisioned in
the shared runner configuration; without them, it deliberately fails rather
than inventing a public fallback or declaring delegated success. Its future
PASS would prove only PRM/reachability/anonymous rejection, not interactive
OAuth. The credential-free local job covers three isolated dependency sets.
No required checks or live-testing policy are waived by draft status.

### Checkpoint review and catalog CI regression

The independent review of immutable snapshot `50085721` found the catalog/unit
regression described below; it did not identify another functional auth/helper
blocker. That is bounded review evidence, not completion of the deferred live
cases.

[Unit job 103225903885](https://github.com/aiappsgbb/awesome-gbb/actions/runs/34587797481/job/103225903885)
ran **1064 tests, 11 failures, 3 skips** on the earlier checkpoint. Failures
were catalog-coupled: stale exact skill/plugin versions and totals, README's
old count and interrupted ACA/jobs row adjacency, missing proposed 4.32 notes,
and an assertion allowing only one draft candidate. Reconciliation retains
exact version/count checks, jobs adjacency, explicit candidate scope and all
behavioral gates. History assertions now inspect this file rather than force
run-specific diary text into SKILL.md.

The first local affected-module run during reconciliation ran **179 tests**
and exposed two failures: the next inventory assertion still advertised 1046
instead of 1064 tests, and the unchanged jobs Docker build hit a dependency
download `tls handshake eof`. The latter is local package-network evidence,
not an auth regression; no test skip or network-error allow-list was added.
Final local rerun: **1064 tests in 88.639 seconds; 1031 passed, 32 skipped,
one failed**. All catalog assertions that failed in the earlier CI job now
pass. The sole remaining failure is the unchanged jobs Docker test downloading
`authlib==1.7.2` with `tls handshake eof`; the complete suite is therefore
**not green locally**. The runner's existing environment-dependent skips
remain unchanged, not converted into passes or newly added by this PR.

The three auth cohorts separately passed **39 tests** (16 policy/contract/
staging, 8 HTTP/MCP, 13 management, 2 Hosted), with all three `pip check`
commands reporting no broken requirements. T0 validated 38 skills, 34 pins
and 201 references; plugin structure and generated-site checks passed
(47 HTML files, zero broken root-relative links). Seven published source
hashes were checked against the current canonical modules. Fresh PR CI remains
separate; an earlier CI failure is not retroactively overwritten by these
local results.

### Targeted PR matrix selection

The earlier workflow-path rule started all **24** Azure fixture legs even
though the workflow edits only added independent local auth tests and a
unit-test dependency. The shared Azure job/global configuration was unchanged.
The three outstanding overbroad runs for this PR were cancelled to stop
further fixture work; this does not imply deletion of resources already
created by a started fixture.

The selector now compares base/HEAD workflow structure, retaining full
coverage for shared/global changes, unknown jobs or ambiguous input.
Independent named local test-job edits retain normal skill/dependency fanout.
This PR selects **11 legs** for **six directly changed skills**, not 24.
The **44 matrix regression tests passed**, including changed runner/auth/
retry/global settings still forcing full and local-only changes selecting no
Azure legs. Required checks, local tests and main/scheduled full canaries
remain unchanged. Cancelled old runs are historical; new-head CI evidence
must be reported separately.

## Hosted/direct triage at the checkpoint

**Unresolved, not classified as impossible.** Bounded public issue/release
research identified a known defect in the pinned hosting package, but did not
establish it as the cause of this live direct-MCP failure.

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| [microsoft/agent-framework#7658](https://github.com/microsoft/agent-framework/issues/7658) and [microsoft/agent-framework#7725](https://github.com/microsoft/agent-framework/issues/7725), both closed | Reports using hosting `1.0.0b260730` describe mid-run `oauth_consent_request` content being dropped, yielding completed/empty output. | Those reproductions observed the nested consent content; the direct-MCP demo's logs do not show its nested response items. |
| [Pinned hosting output converter](https://github.com/microsoft/agent-framework/blob/python-1.13.0/python/packages/foundry_hosting/agent_framework_foundry_hosting/_responses.py#L1966-L2083) | The release source associated with the pin has no OAuth-consent output branch. | Release-source inspection alone is not a byte-for-byte reproduction inside the deployed container. |
| [Later output converter](https://github.com/microsoft/agent-framework/blob/python-1.17.0/python/packages/foundry_hosting/agent_framework_foundry_hosting/_responses.py#L1375-L1403) | A newer implementation emits OAuth consent output explicitly. | It does not prove that upgrading fixes the direct route's outer-user identity propagation. |
| [Azure/azure-sdk-for-python#46696](https://github.com/Azure/azure-sdk-for-python/issues/46696), open when checked | Closely matching native `FoundryChatClient.get_mcp_tool()` architecture fails when Hosted while working locally with a user credential; the reporter confirms the Toolbox path works. | Its reported symptom is an explicit ARA OBO BadRequest, not this demo's nested HTTP 200 and empty outer output. |

No exact public issue matching the entire observed direct-path signature was
found. A swallowed consent request is a plausible explanation **only if**
the nested response contained consent content. Successful Prompt and Hosted
Toolbox controls with the same user/connection/server narrow the investigation
without proving that premise.

The next product-group evidence should include the exact pinned versions and
image digest, request timestamp/correlation, inbound context-presence flags,
nested response/SSE **item types/status/errors**, host dispatch warnings, and
the successful controls. Exclude tokens, consent URLs and private inventory
from public reports. Ask which caller-context contract is supported for
Hosted/direct and whether the nested service returned consent content.
No new ticket, speculative adapter or dependency upgrade is part of this
checkpoint.

### Final bounded check of the persisted direct-path evidence

The original private log and exact probe entrypoint were re-read without
redeployment. The probe registers native
`FoundryChatClient.get_mcp_tool(project_connection_id=...)` with the two
allowed tools, `ManagedIdentityCredential` for its platform client and
`ResponsesHostServer`; it adds no custom user/header transport. Logs show
incoming user/call-context presence, successful MI acquisition, nested
Responses HTTP 200 and outer `completed` with `output_count=0`. They do
**not** expose nested output/SSE items or a consent-content dispatch warning.
An Azure Monitor connection-string warning is also present; this is not
evidence that it caused the empty response.

**Classification: insufficient evidence to establish the root cause.**
The consent-drop defect is a compatible hypothesis, not a confirmed match;
the ARA OBO issue remains related but symptomatically different. Inbound
context flags do not establish delegated context on the nested request.
No fresh cloud invocation, build, version upgrade or consent was performed
in this final check. The outstanding discriminator is still the sanitized
nested item/status/error and dispatch trace described above. Do not label
the path globally unsupported or attribute the failure solely to its version.
