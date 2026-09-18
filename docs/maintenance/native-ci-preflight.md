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
| `foundry-mcp-auth` | `MCP_AUTH_SMOKE_ISSUER` | Exact tenant-specific Entra v2 issuer with canonical tenant ID; no `common` or inferred tenant |
| `foundry-mcp-auth` | `MCP_AUTH_SMOKE_SCOPE` | Exact `api://<application-id>/<permission>` with canonical application ID |
| `foundry-mcp-aca-jobs` | `MCP_AUTH_APP_CLIENT_ID` | Canonical hyphenated UUID, not an audience URI or consent flag |
| `foundry-mcp-aca-jobs` | `MCP_ACA_JOBS_COSMOS_ENDPOINT` | HTTPS account origin, optional trailing `/` and valid port |
| `foundry-mcp-aca-jobs` | `MCP_ACA_JOBS_STORAGE_ACCOUNT_URL` | HTTPS account origin, optional trailing `/` and valid port |
| `foundry-mcp-aca-jobs` | Eight standing scope inputs listed below | Presence; exact values validated by the lifecycle gate before producers |

Empty and whitespace-only inputs fail. URLs with whitespace, control characters,
backslashes or encoded control characters fail; no values are normalized or
repaired. Host validation is syntactic only, with no DNS or service lookup.
The approved auth inputs are forwarded only to that leg, identically in the
initial and retry consumer steps. Jobs standing scope is validated and exported
by its runner-owned setup. Shared
workflow identity/project prerequisites retain their existing gates; this
step deliberately checks only skill-specific standing inputs.

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
`SMOKE_RESULT` marker. Only the real fixture's canonical probe may produce its native
result. No resources, approvals, secrets or RBAC are created, retrieved or
renewed by this script.

## Remaining operator and live-proof gates

Supplying a syntactically valid endpoint does not authorize it. The explicit
approval must come from the owner for the intended target/runner; this boolean
does not encode approval lifetime or independently bind tenant/scope.
No approved CI inputs are created by this change. The Jobs app client ID is
the Easy Auth resource application/audience, **not the CI caller's principal
ID and not delegated user consent**. Existing
Cosmos/storage resources and documented pre-granted permissions, including
Storage Blob Data Contributor, still require separately authorized live proof.

The auth fixture now invokes
[`scripts/mcp-auth-network-smoke.py`](../../scripts/mcp-auth-network-smoke.py)
directly, rather than asking the agent to reconstruct its HTTP assertions.
It requires scoped PRM HTTP 200 with exact resource/sole issuer/sole scope and
anonymous MCP initialize HTTP 401 with the exact Bearer resource-metadata
challenge. Redirects, proxies, cookies and credential headers are not used.
Responses are bounded to 64 KiB and each request to 15 seconds; the CLI has a
40-second overall deadline, including slow response reads. Status output and
failure markers contain fixed codes only, never response content or input values.
The deterministic helper does not constitute live runner proof: correctly
approved target/runner execution remains unresolved in #492. Offline tests do not replace
those assertions or the separate
[delegated/Playground validation record](foundry-mcp-auth-validation.md).

An owner may approve a **separate synthetic-only public protocol test
instance** of the canonical delegated server, with its own API registration
and pull-only identity. Such an instance exercises only the anonymous PRM/401
contract. It has no Foundry connection, OAuth client/consent, real user data or
identity-proof output. It must not expose or modify a retained private service.
Its result is not private-network reachability, delegated E2E, candidate
private Gate B, Playground or publication acceptance. None of those gates or
the consumer template acquires a public fallback from this CI test posture.
Dependency-only PR fanout omits the separately approved MCP-auth network
probe with a visible `MCP_AUTH_SELECTION=DEPENDENCY_ONLY_EXCLUDED` notice:
it is not operational acceptance of the upstream skill and is never reported
as a successful auth smoke. Direct skill/helper changes, shared input-contract
changes and full main/scheduled canaries still select real fail-closed
acceptance. Quarantine is unchanged. AgentOps approval lifecycle is documented separately in its
[owner runbook](../../skills/foundry-agentops/references/day2-runbook.md#owner-renewal-and-main-schedule-authorization);
no approval is renewed by these changes.

Offline regression command:

```bash
python3 -m unittest scripts.tests.test_native_ci_preflight scripts.tests.test_mcp_auth_network_smoke -v
```

## Exact MCP ACA lifecycle boundary

The `foundry-mcp-aca` fixture no longer runs broad `azd down` in the standing
CI resource group. Its deterministic scaffold creates one Container App;
the resource group, managed environment, identity, registry and locked Log
Analytics workspace are pre-existing and are never cleanup-owned.
[`scripts/mcp-aca-ci-lifecycle.py`](../../scripts/mcp-aca-ci-lifecycle.py)
wraps the fixture's **single** `azd up`, not a new deployment implementation.

Before login or paid execution, the runner requires a separate private
`MCP_ACA_CI_LIFECYCLE_APPROVAL_JSON` record. Schema version 1 has exactly:

| Fields | Owner contract |
|---|---|
| `repository`, `sha`, `run_id`, `run_attempt` | Exact GitHub repository, checkout SHA and known run/attempt; all strings |
| `resource_group_id`, `environment_id`, `identity_id`, `acr_server` | Exact standing scope and resources used by the canonical scaffold |
| `tenant_id`, `client_id` | Exact CI service-principal route; subscription must match the resource group |
| `expires_at` | Strict UTC timestamp; future, at most 24 hours from validation |
| `owner`, `purpose` | Named accountable operator and bounded test purpose |
| `delete_exact_created_app` | Literal `true`; authorizes only the corroborated run-created app, not shared infrastructure |
| `retain_images`, `image_retain_until` | Literal `true` and explicit image custody deadline, no earlier than approval expiry and at most seven days away |
| `age_recipient` | Owner-held age X25519 recipient; no private decryption key on the runner |
| `schema_version` | Integer `1` |

This is a known-run approval, not a standing auto-renewal. A missing record
fails before creation. The owner must separately authorize a known run and
attempt before its execution or rerun; knowing the run ID is not permission
to rerun it. Approval must remain valid through cleanup, not merely through
deployment. The helper never renews credentials, permissions or approvals.
Immediately before `azd up`, after preflight reads/token acquisition and
inventory encryption, it rechecks that the frozen approval has at least
30 minutes left: 20 for azd, five for capture and five for the finalizer.
This is a minimum remaining execution budget, not an automatic extension.
The bounded azd subprocess owns its internal token exchanges; the helper does
not intercept them. The caller's deadline keeps that subprocess inside the
already-approved window.

Preparation verifies pinned age tooling and encrypted custody before the first
mutation. Deployment compares all six scaffold files to the fixture at the
approved checkout SHA, accepts only its exact azd configuration/environment,
rejects extra files/hooks, verifies the active CI identity, records an
authenticated app GET returning supported `ResourceNotFound`, and snapshots
deployment IDs. It persists an encrypted UNKNOWN inventory **before** invoking
azd. Only a successful azd result, one new matching ARM deployment and successful
Create operation, and app readback establish OWNED. Nonzero/timeout/lost or
ambiguous acknowledgement remains UNKNOWN. The workflow forbids MCP ACA retries;
the on-disk inventory also blocks a second helper invocation from another
Copilot process in the same run/attempt.

Before azd, the helper reads the bounded
[management-lock inventories](https://learn.microsoft.com/rest/api/resources/management-locks/list-at-resource-group-level?view=rest-resources-2016-09-01)
at the exact approved subscription, resource group and future app scopes
(API `2016-09-01`). An inherited or app/child `CanNotDelete` or `ReadOnly` lock
blocks creation with `CLEANUP_LOCKED`. An incomplete, unauthorized or
unclassifiable lock inventory also fails closed; a 404 is not an empty list.
A lock scoped only to an unrelated standing resource does not inherit to the
app. No lock is removed or modified. This read checks observed locks, not
future policy changes or a guarantee of delete authorization. In particular,
an RG-level shared protection lock makes this lifecycle incompatible with that
environment: it is an operator/environment blocker, **not missing RBAC** and
not something this fixture can repair. Subscription-level lock read permission
is a prerequisite; the helper never grants it.

Deployment and operation inventories follow every continuation page, accepting
only HTTPS `management.azure.com`, the exact collection path (ARM casing is
insensitive) and the fixed API version. Opaque cursors are preserved; duplicate
query keys, redirects, changed scope/origin/API and continuation loops fail
closed. Each collection is limited to 100 pages, 10,000 items and 32 MiB of
decoded JSON, with a 120-second deadline checked before and after each page
request. Individual token/request timeouts and the overall helper deadline
still apply while a page is in flight. No partial list establishes ownership:
an error after azd leaves UNKNOWN and cannot trigger another deployment.
The Create operation is bound through its exact parent deployment and
operation ID; the correlation ID is the **parent deployment's**. An optional
operation correlation/service-request ID is not required. Non-resource output
evaluation operations may have a null target and do not establish ownership.
ARM app ID comparison is case-insensitive. The service's `systemData.createdAt`
is retained and compared verbatim, including wire values without a timezone;
this does not relax the strict UTC format required for approval timestamps.

An `always()` runner-owned finalizer loads the helper from the checkout commit,
rechecks scope, creation operation/correlation and the app's creation time,
environment, identity and image binding, and deletes **only that app**. It
requires a supported HTTP 404 readback; a submitted DELETE, 401/403, network
failure, missing inventory or UNKNOWN record is never absence proof.
Immediately before sending DELETE, **after** acquiring its token, the helper
rechecks that the frozen approval has at least five minutes left and that at
least two minutes remain in its 240-second cleanup/poll budget. Expiry or
insufficient reserve prevents the mutation and preserves unresolved intent.
Cleanup is capped at five minutes. Cancellation,
runner loss or expired credentials may prevent completion and require an
owner handoff; `always()` is not a cleanup guarantee.

Pattern 25's functional grade is unchanged: cleanup failure remains explicitly
visible but does not turn a successful functional smoke into failure. The
cleanup success state is **`APP_ABSENT_IMAGE_RETAINED`**, never “all deleted”.
Only encrypted `inventory.age` is uploaded, with one-day artifact retention;
raw approval and inventory remain in the private ephemeral runner directory.
The owner must retrieve ciphertext before that deadline and separately honor
the image retention deadline. The record captures the observed image reference,
not a resolved immutable digest or all registry build/cache artifacts; ARM
deployment records also remain. None of those residuals is certified removed.
This is same-UID CI supervision, not a hostile-agent-proof sandbox.
Changes to `setup-agentops-age.sh` select AgentOps, MCP ACA, Hosted and GHCP;
changes to `mcp-aca-ci-lifecycle.py` select all three lifecycle consumers;
`hosted-ci-lifecycle.py` selects Hosted and GHCP. Normal dependency fanout still
applies. AgentOps and MCP-auth remain excluded only when selected solely as
another skill's dependency on the change-gated PR path.

```bash
python3 -m unittest scripts.tests.test_mcp_aca_ci_lifecycle scripts.tests.test_foundry_mcp_aca_fixture_contract -v
```

## Hosted and GHCP native reconciliation

The public Hosted/GHCP fixtures call
[`hosted-ci-lifecycle.py`](../../scripts/hosted-ci-lifecycle.py), which reuses
the reviewed MCP ACA scope, lock, pagination and encrypted-custody primitives.
It is **proposed source requiring live validation**, not approval to operate
on historical agents. Their functional readiness/inference checks remain in
the fixtures. The deployment helper uses native `azd package`, `azd publish`
and one `azd deploy --from-package`; it never replaces those producers with
hand-rolled Docker/ACR builds or creates a resource group/model/capability host.
The runner pins azd 1.34.1 and `azure.ai.agents` 1.0.0-beta.14 for these two
legs; the lifecycle SDK runs in its own bounded Projects 2.3.x/OpenAI 2.45.x
environment. The fixture management installs use the same OpenAI bound:
an unconstrained OpenAI 3.x dependency does not supply the HTTPX import
required by Projects 2.3.0. Container cohorts and private environments are
unchanged.

The owner supplies separate `HOSTED_CI_LIFECYCLE_APPROVAL_JSON` and
`GHCP_CI_LIFECYCLE_APPROVAL_JSON` secrets. Both use this exact proposed
schema (no operational values belong in the repository):

| Fields | Required binding |
|---|---|
| `schema_version` | Integer `1`, not boolean |
| `skill`, `repository`, `sha`, `run_id`, `run_attempt` | Exact selected skill, checkout and known run/attempt; no future-run wildcard |
| `tenant_id`, `client_id`, `project_id`, `project_endpoint`, `acr_server`, `model` | Exact CI identity/project/registry and `gpt-5.4-mini`; subscription from the CI environment must match |
| `expires_at`, `retain_until` | Strict UTC `Z` timestamps, future expiry at most 24 hours away; explicit residual custody until at most seven days away and no earlier than expiry |
| `owner`, `purpose`, `age_recipient` | Accountable operator, bounded purpose, owner-held X25519 encryption recipient |
| `delete_reconciled_native_objects` | Literal `true`; only reconciled native objects, not anything matching a name prefix |
| `retain_images_identities_and_stored_responses` | Literal `true`; no automatic image/cache, directory-identity, stored-response or telemetry purge |
| `temporary_foundry_user_grants` | Literal `true` for GHCP, `false` for Hosted; no other roles or principals |

Limits are schema ceilings, not automatic permission for that duration.
There is no renewal, secret write or credential repair. Missing custody,
wrong context, expired approval or inherited/unreadable locks fails before
packaging or publication. The source check freezes all canonical files, the
single service, instructions and exact azd environment. Additional hooks,
services, source files or environment overrides fail closed.

The Hosted/GHCP and Jobs-hosted source checks share one pinned azd-state
validator. Only the selected `.azure/<run-name>/` directory is allowed:
the exact root config and environment values, plus optional azd 1.34.1
`.azure/.gitignore` (exact generated bytes), an empty `.env.lock`, and an
empty-object per-environment `config.json`. These are local bookkeeping, not
permission for hooks, alternate services/environments or arbitrary files.
Symlinks, non-regular/multiply-linked files, unknown directories and nonempty
configuration are rejected before azd reads the environment.

The native SDK bridge retains `AzureCliCredential`, requesting only the
approved subscription; Azure CLI rejects simultaneous tenant/subscription
arguments. The preceding runner-side identity check still binds that
subscription, tenant and service-principal client ID. There is no credential
fallback, account switch or new permission grant.

Every encrypted `inventory.age` receipt contains the complete frozen approval
and its canonical SHA-256 binding, including owner, purpose, tenant, project
ID/endpoint, expiry and retention. It remains a self-contained custody record
after the runner or original secret disappears; plaintext approval is never
uploaded or logged. Missing, incomplete or mismatched receipt custody fails
closed before any producer, with encryption repeated before packaging. A
recovered receipt is historical evidence, not renewed execution permission.

Before packaging, native GET must prove the full-UUID name absent. Encrypted
UNKNOWN intent is persisted before each producer. The machine-readable
package receipt binds the local image/config hash; the native publication
destination is derived from that receipt, with a complete registry repository
inventory proving its namespace unused. After publication, exact digest and
manifest/config hash are checked. Shared image digests are never deleted.
Only the reviewed immutable-image/imagePassthrough transformation is applied
before the frozen complete SDK definition and deploy intent are recorded.
Minimum remaining approval is 45 minutes before package and 25 before
publish/deploy; every boundary is rechecked after inventory encryption.
The azd subprocess owns internal token exchanges, within its bounded timeout.

Successful deployment is **not a CREATE ACK**. Ownership is
`RECONCILED_OWNERSHIP`: authenticated preGET404, durable single deploy intent,
complete bounded version inventory (exactly one version), direct GETs matching
the complete frozen definition/image, creation time, version ID, agent ID and
instance identity. The native version list is limited to three data pages
plus a terminal page, six total items and 120 seconds. A partial list,
nonzero/lost producer acknowledgement, changed binding or extra version leaves
UNKNOWN/residual; neither a new helper process nor a workflow retry may deploy
a replacement. This conservative implementation does not automatically
reconcile a nonzero native deploy into deletion authority.
The definition comparison accepts only one service default: an additional
`container_protocol_versions: []` when absent from the frozen definition.
It does not remove or replace `protocol_versions`, accept a populated/null
legacy field, or ignore any other definition difference. Frozen definition
and receipt bytes are not rewritten to make a mismatch disappear.
Workflow retries are disabled for these two legs even for failures before
creation; retry recovery is not silently exchanged for uncertain ownership.
Any gate failure or tool denial stops the fixture; the consumer must not patch
source/tests or invoke/deploy directly around the helper. A tool denial before
execution is not Azure RBAC evidence. Checkout mutation still fails grading.

GHCP grants only the bound instance principal at the exact account/project
scopes. Complete scoped inventories preserve standing assignments. Each new
assignment has its own UUID ID, preGET404, persisted intent, HTTP 201 ACK and
matching readback before OWNED. No blueprint grant or privilege repair occurs.
An unresolved assignment prevents invocation. The one Hosted invoke and six
GHCP propagation attempts consume persistent per-run/attempt counters; a new
process does not reset their budgets. This does not increase AgentOps budgets.

Hosted endpoint routing is also runner-owned: `configure-routing` issues the
single `update_details` write only after acquiring its token, completing
bounded inventory and direct binding reGETs, and checking at least ten minutes
of approval remain. The fixture only polls readiness and calls the helper.
Routing intent/acknowledgement is independent of the invocation counter;
missing/uncertain routing prevents invocation, and another process cannot
repeat the write. Expiry during polling, encryption or token/binding reads
does not authorize a late write.

The runner finalizer reloads code from the original checkout SHA. It reGETs
binding immediately before SDK deletion, after token acquisition, uses
`force=False`, and deletes only correlated sessions, the version and the
same empty agent. Exact run-created roles are independently reGET-checked and
revoked; an uncertain second grant does not prevent removal of the first
acknowledged grant. No DELETE is reissued after a lost acknowledgement.
Deleting the final version may also remove its parent. Only an already
reconciled version/agent binding, the exact persisted version DELETE intent
and verified version-absence receipt allow that cascade to complete cleanup.
The finalizer rechecks version absence and requires two supported parent
GET404 observations, without querying the absent parent's sessions or issuing
a synthetic parent DELETE. Resume uses the same proof; missing persisted
absence, a reappearing parent/version or any unknown read error fails closed.
The first confirmed parent absence is journaled before the second observation,
so interruption cannot turn a later reappearance into permission to delete.
An inventory 404 is never treated as an empty collection.
Only supported authenticated 404s prove absence; auth/network failures do not.
Five minutes of approval must remain at each delete boundary. Overall cleanup
is bounded to 280 seconds under the five-minute workflow step, with fixed
error codes and encrypted residual evidence.
Cleanup requires an already persisted native binding: an UNKNOWN receipt
without it is not automatically promoted by the finalizer. The internal
`reconcile(ledger, native)` predicate is distinct from the cleanup entrypoint;
historical recovery needs separately reviewed, complete evidence and operator
authority, never an edited original receipt or an implicit retry.

Functional PASS remains separate. Even successful native/role removal means
images, caches, directory identities and stored response/telemetry data remain
under the explicit owner retention handoff, **not ALLDELETED**. Only encrypted
inventory is uploaded, with one-day retention. Cancellation/hard runner loss
can prevent the finalizer or last upload; `always()` is not a guarantee.
Same-UID supervision is not a hostile-agent-proof sandbox.

```bash
python3 -m unittest scripts.tests.test_hosted_ci_lifecycle scripts.tests.test_ghcp_hosted_agents_ga_contract -v
```

## Jobs: standing infrastructure and run custody

The opt-in `ci.bicep` path uses an existing workload RG, ACR/CAE, **distinct**
app and worker UAMIs, dedicated keyless synthetic Blob/Cosmos accounts and a
standing Cosmos database. Default consumer `main.bicep` is unchanged.
`standing.bicep` is an owner-only azd bootstrap, never selected by the fixture.
It reuses canonical modules rather than giving CI subscription role-definition
or RBAC-admin authority. Its custom role is assignable only at the workload RG:
`Microsoft.App/jobs/read`, `jobs/start/action`, `jobs/execution/read`,
`jobs/executions/read`, and `jobs/stop/execution/action`.

The owner pregrants app Job Operator at that RG, app/worker AcrPull at the
existing legacy-permissions registry, app/worker/runner Blob Data Contributor
at the dedicated storage account, app/worker Cosmos SQL Data Contributor and
runner SQL Data Reader at the exact database. CI creates **no** native SQL or
ARM assignments, so their receipt disposition is `NONE_CREATED`, not deleted.
The runner's existing Contributor may independently permit account/database
deletion. The helper's narrower allowlist is not an Azure deny policy: protect
standing asset IDs separately and verify effective authority.

Additional exact same-name inputs, beyond the existing audience and URLs:

| Input | Meaning |
|---|---|
| `MCP_ACA_JOBS_RESOURCE_GROUP_ID` | Existing workload RG ARM ID |
| `MCP_ACA_JOBS_ENVIRONMENT_ID` | Existing CAE ARM ID in that RG |
| `MCP_ACA_JOBS_APP_IDENTITY_ID` | Dedicated app UAMI ARM ID |
| `MCP_ACA_JOBS_WORKER_IDENTITY_ID` | Different worker UAMI ARM ID |
| `MCP_ACA_JOBS_COSMOS_ACCOUNT_ID` | Dedicated standing Cosmos ARM ID |
| `MCP_ACA_JOBS_COSMOS_DATABASE` | Existing database name, never cleanup-owned |
| `MCP_ACA_JOBS_STORAGE_ACCOUNT_ID` | Dedicated standing storage ARM ID |
| `MCP_ACA_JOBS_CALLER_PRINCIPAL_ID` | Runner UAMI **object** ID, checked against its acquired token |
| `MCP_ACA_JOBS_NETWORK_PERIMETER_ID` | Optional exact dedicated NSP ID; empty selects public test posture, nonempty requires the strict binding below |
| `MCP_ACA_JOBS_CI_LIFECYCLE_APPROVAL_JSON` | Owner's exact-run authorization described below |

The approval object has exactly `native`, the twelve snake-case fields in
[`INPUTS`](../../scripts/jobs-ci-lifecycle.py), `delete_run_resources: true`
and `standing_resources_retained: true`. `native` is the complete existing
Hosted authorization shape above (skill `foundry-hosted-agents`), including
owner, purpose, repository/SHA/run/attempt, tenant/client, project ID/endpoint,
registry/model, expiry, recipient and bounded retention. It authorizes the
secondary Hosted producer, not a change to AgentOps or delegated consent.
Full approval and its canonical hash are encrypted in `inventory.age` before
any producer. The uploaded ciphertext remains sufficient for custody after
secret replacement or loss of `approval.json`; plaintext/tokens are never
public artifacts. Same-UID agents are still not a hostile-code sandbox.

The 90-minute helper ceiling leaves a separate 15-minute finalizer inside the
120-minute job. Individual operations have tighter budgets; producer gates
reserve the additional 850-second finalizer lifetime, and every DELETE
rechecks remaining lifetime after token acquisition. An expired approval is
not renewed automatically. Lost runner/cancellation can still interrupt
custody upload or cleanup and must be reported as unresolved.

One azd provision creates the app, Job, one control container and two Blob
containers. Exact preGET404, frozen source/parameters, parent deployment
correlation and child Create/Succeeded operation IDs plus stable direct
readbacks bind each child. Cosmos's generic PUT 200/bodyless 202 is **not**
called a creation-only ACK. Capture validates the complete bounded deployment
tree before promoting any ownership. An explicit Failed child Create is then
recorded per resource: independently proven siblings are reconciled and their
receipts encrypted before capture returns aggregate failure. Ambiguous/failed
effects stay UNKNOWN and block replacements/retry. A proven app can be cleaned
independently, but an unresolved Job prevents deletion of its backing data.
The existing canonical postdeploy hook converges the shared image. Prompt and
Hosted agents have separate native bindings; EasyAuth and revision restarts
are runner-owned and limited to the bound app.

Functional acceptance covers real task completion, idempotent task reuse,
cancellation, legacy fallback, callback shape, and genuine Prompt/Hosted MCP
calls with matching input/task IDs. It is not a repository inspection.
Finalization separately removes the bound native objects, app and Job,
verifies auth/execution cascades, captures data keys, then removes bound
containers and reGETs captured records/blobs. Unknown producer/cascade absence
preserves data. Deletes are single-attempt; auth/network errors never mean
absence. The standing database/accounts/UAMIs/grants and owner-retained
images/provider history are never selected for deletion. No broad `azd down`,
shared-Job mutation/restore or lock removal occurs.

Standing prerequisites remain operational gates, not source-level assumptions.
If the actual storage network posture is Disabled despite an Enabled
deployment request, the fixture fails before creating anything; investigate
policy rather than retrying deployments or silently enabling public access.
This explicit synthetic test posture does not alter private Auth acceptance.

Where owner-approved governance supports `SecuredByPerimeter`, the standing
template has an explicit `networkStage` opt-in. Owner `azd provision` with
`associate` keeps both accounts Disabled, enables Cosmos SystemAssigned
identity and creates a dedicated NSP/profile with only one inbound
current-subscription rule and the two Enforced data-account associations.
After readback of the exact association IDs, a second owner provision with
`enforce` changes the two accounts to SecuredByPerimeter. No IP wildcard,
outbound allowance, policy exemption or network/RBAC change is available to CI.
Retain the emitted perimeter/profile/rule/association IDs as owner inventory.
For a brownfield mode change, pass `cosmosAutomaticFailover` with the observed
account value rather than resetting it to the new single-region default
`false`; Cosmos TLS remains explicitly `Tls12`. Review the full what-if for
unintended resets caused by provider API defaults before either phase.

Set `MCP_ACA_JOBS_NETWORK_PERIMETER_ID` and approval `network_perimeter_id` to
that exact NSP ID (or both empty for the public posture). The native gate
enumerates bounded complete profiles/rules/associations, requiring only
`jobs-data`, only `ci-subscription` admitting the current subscription, and
exact `storage`/`cosmos` Enforced associations. Foreign or additional members,
rules, profiles, Disabled accounts, missing Cosmos identity and inconclusive
reads all fail before producers. Blob/Cosmos data-plane reads must then pass:
the template and subscription rule do not prove runner-UAMI FIC reachability.

Historical CI orphans require separate owner-authorized reconciliation.
An inherited RG deletion lock is an environmental incompatibility, not a
missing-RBAC diagnosis. Targeted live proofs must cover MCP ACA, Hosted,
GHCP temporary-role partial failure, auth acceptance, and AgentOps exact
event/attempt authorization separately from cleanup. This PR's **shared
workflow changes still require the full 25-leg matrix**, not merely those
targeted proofs. Prerequisites, lock compatibility, actual
base/head selection and costs must be resolved before delivery; offline
regressions do not establish live acceptance or merge readiness.
