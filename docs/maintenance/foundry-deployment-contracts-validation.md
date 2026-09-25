# Foundry deployment contracts — #518 acceptance record

**Unreleased draft candidate. Partial source-bound Azure evidence, not ready
for issue closure.**
Original source baseline: `2a29e084882a52e74b94def3ee9bb32b73592e60`.
Candidate `67a0409f8203f2994962379a7d737926e6dc9d73` is published in #520,
not an installed/adopted revision. The owner subsequently
authorized the necessary CI setup, live verification, run-owned cleanup and one
candidate PR. A dedicated validation-only Entra audience/application principal
and native project registry connection are now verified standing prerequisites,
not application-level T3 evidence. No new role grants, registry-mode/network
changes, mirror updates or downstream writes were made.

## Area-by-area evidence

| Issue area | Implemented boundary | Evidence and remaining gate |
|---|---|---|
| 1 — Versioned hosted contract | `hosted-contract.json`, profile selector, template/stager validation, dependency/provenance references | Local profile/drift tests and canonical T1/T2 runner PASS. Historical BASIC evidence remains scoped to #500; new consumer/native emission and T3 acceptance still required. |
| 2 — Early capability/permission checks | Capabilities phase before images; mode/generation, ACR isolation feasibility, separate identities/actions, ingress-trust receipt | Positive/negative local gate cases PASS. Actual environment, grants, read rights and ingress still require authorized live proof. |
| 3 — Desired versus loaded | Separate config ID, registry manifest/index, deployed reference and serving session; rollout ACK no longer claims serving success | Local manifest/binding cases PASS. Loaded-policy/config discriminator and runtime behavior require live observations. |
| 4 — SDK/platform boundaries | Creating with absent future identity remains pending; native Projects transport tests, explicit cohorts, null/readback handling | Supported Projects 2.3 local transport tests PASS. Actual App Containers 5.0 transport covers accepted/unbound start and no hidden LRO polling. No demonstrated in-repo second-metadata-read or conditional-response guard defect was invented. Additional native observations are still needed where the issue's examples apply. |
| 5 — Response/effect custody | Pre-parse hosted metadata, durable-record interfaces, no retry after client/delivery failure; Jobs native receipt and unknown-start/worker guards | Local transport, three Teams handler and Jobs regression cases PASS. Real controlled lost-response/effect readback still required; model completion is not business proof. |
| 6 — Diagnostics/evidence | Finite CLI/HTTP waits, opt-in new diagnostic inference, private raw capture versus safe projection, explicit inconclusive results | Shell replay tests PASS without Azure; no new inference by default. Live changed commands and private evidence review remain pending. |
| 7 — Source/adoption | Read-only hashes of actual helper/template bytes, legacy migration-only, source versus installed distinction | #509 ancestry and both published execution hashes preserved. No installation/adoption was performed. Threadlight adoption is an external dependency, not completed by this candidate. |

## Local runs (2026-09-24)

- **200 targeted tests PASS**: profile/capability, response custody, private
  bootstrap, Teams handlers, diagnostics, hosted refresh, MCP fixture and GHCP
  deployment contracts. Real SDKs use local fake transports, not Azure.
- **169 Jobs tests PASS, one existing skip**: adapter/orchestrator/worker/models/
  protocol/store/callback coverage. This is not a deployment or remote effect test.
- **15 delegated management/invoker tests PASS** with existing consent behavior.
  This does not close the delegated-auth candidate's live release gates.
- **T0 PASS**, plugin structure PASS.
- **Hosted pin T1/T2 PASS** through `scripts/run-pin-validation.py::run_one`,
  including all existing expected outputs plus the profile/provenance check.
  The MAF package cohort was not upgraded.
- The global interpreter's complete discovery/execution was **not green**:
  it had Projects 2.1 rather than the supported 2.3 cohort, missing APIM SDK,
  and version/inventory assertions requiring the intended release updates.
  This result is not evidence of a platform failure.
- Preparing the declared catalog CI cohort in a session-only environment
  failed on the configured feed's **HTTP 500 for fastmcp-tasks 4.0.5**.
  One bounded recovery at the declared compatible floor **4.0.1** failed with
  the same HTTP 500. No feed switch, repository pin change or repeated recovery
  was performed during that attempt. Full-suite reproduction was BLOCKED
  pending the owner's alternative-source decision, recorded below.

The earlier source inventory was **1478 tests**: previously verified 1448 plus 30 added
methods. On September 24 this was an arithmetic inventory, not a fresh full-suite
execution result; the September 25 run below now verifies that discovery count.

## Authorized public-source verification (2026-09-25)

The owner explicitly approved public PyPI for public verification dependencies
in session-isolated environments. Installation used one explicit
`https://pypi.org/simple` index with process-local pip configuration disabled,
no extra index and no shared-cache reuse. Install reports confirm that all
downloaded distribution artifacts came from `files.pythonhosted.org`.
No repository constraints or global configuration changed; both earlier
configured-feed HTTP 500 outcomes remain historical evidence, not erased retries.

The catalog environment resolved the existing declared compatible ranges to
FastMCP/fastmcp-tasks **4.0.9**, MCP **2.1.1**, Projects **2.6.1**, OpenAI
**3.8.0**, App Containers **5.0.0** and API Management **5.0.0**.
`pip check` passed for every restored environment. Public package names and
version constraints only were sent to PyPI; repository source was not uploaded.

- **Full catalog suite: PASS — 1478 tests in 185.527 seconds, 32 conditional
  skips.** The first run found one stale documentation-shape assertion for
  the intentional `effectState` addition. The corrected test still requires
  the exact closed public shape; the runtime-shape test also passed.
- **Supported hosted cohort: 86 tests PASS**, separately from the catalog's
  newer SDK cohort.
- **Doctor MCP 1.27.x: 21 tests PASS.**
- **Delegated auth: 18 catalog/policy + 9 server + 15 management + 2 hosted
  tests PASS** in their three separately declared environments. These overlap
  existing catalog coverage; do not add them to the catalog discovery count.
- **T0, plugin structure, diff whitespace and three docs-preservation tests
  PASS.** The September 24 canonical hosted T1/T2 result remains tied to
  unchanged execution/helper/pin source; this follow-up changes only the stale
  test expectation and acceptance documentation.

This is local execution on **macOS / Python 3.14.5**, not a GitHub Linux CI
result. Of the 32 pre-existing conditional skips, **29 require Linux sealed
memfd support**, **2 require the exact optional AgentOps native v0.14.0 checkout**,
and **1 is the fallback-shim test skipped because the real fastmcp-tasks package
is installed**. No skip condition or test assertion was weakened to obtain PASS.
Linux/native-source coverage remains a separate execution gate where applicable.
Private install reports, per-cohort package inventories and full logs are
retained in the session artifacts; they are not automatically published files.

## Explicit standing-resource Jobs reuse (2026-09-25)

The owner approved **local implementation only** of the CI route that reuses
existing identities and database instead of adding shared grants or provisioning
new identities. Earlier 1478-test evidence and the prior 91-file hash manifest
are retained as historical baselines, not reused as proof of this new diff.

The candidate now includes:

- `templates/infra/ci-reuse.bicep`, an explicit resource-group-scoped composition
  of the canonical app, Job and Cosmos modules. It creates no RG, identity,
  database, role definition or assignment. `cosmos.bicep` adds
  `useExistingDatabase` with default **false**, preserving ordinary provisioning.
- `ci_reuse.py` plus conditional azd hooks: mandatory input validation,
  authenticated exact standing reads, endpoint/identity/active-target checks,
  executor Cosmos reader versus runtime writers, and no fallback on missing
  permission. Built-in roles are identified by their immutable role IDs.
- Run-specific app/Job/control container/blob containers and two explicit
  image repositories. Private pre-write absence and created-object receipts
  gate cleanup; shared database, identities, grants, accounts and RG are never
  deletion targets. Replaced/unregistered resources and changed/shared image
  tags block cleanup. Missing native creation provenance remains an explicit
  ownership gate rather than a broader deletion workaround.
- One-shot prompt/hosted invokes using the existing custody helper; SDK and
  application retries are disabled for uncertain effects. Hosted version
  cleanup requires its recorded pre-write absence and creation identity.
  Build-context allowlists exclude `.azure` and private evidence.
- Identical standing-input wiring for the runner preflight and primary/retry
  fixture environments. No GitHub secret or live resource was changed during
  that local-only iteration; subsequent setup is recorded below.

**Verification: PASS — 1490 tests in 150.360 seconds, 32 existing conditional
skips** in the declared isolated catalog cohort on macOS. Twelve new reuse
tests cover missing/wrong-scope inputs, endpoint/principal/permission mismatch,
executor-versus-writer semantics, exact staged azd target, ordinary-template
preservation, compiled resource graph, shared/replaced-resource deletion
rejection, image custody and one-dispatch behavior after malformed acceptance.
Both ordinary and CI Bicep entrypoints compile with the existing compiler.
The compiler retains only the repository's existing experimental-assertions
warning; no new schema warning is accepted. T0/plugin/whitespace checks pass.

**CI selection consequence:** adding required inputs to the shared matrix job
makes the existing canonical selector choose the full **25-leg** Azure matrix,
not the earlier 15-leg selection. The selector/quarantine/retry policy was not
changed to bypass this rule and no workflow was run. Cost, prerequisites and
publication and cost assessment must use this new selection.

## Authorized CI prerequisites (2026-09-25)

The dedicated CI API audience and its service principal were created with a
verified human owner: single tenant, v2 tokens, no secrets/certificates, API
permissions, delegated scopes or app roles. Caller authorization remains the
resource server's explicit ACL, not the audience ID. They are standing CI
components, with an owner review by December 24, 2026.

The existing default project's registry connection was provisioned once using
the actual ejected azd 1.34.1 / agents beta.14 graph. Native inputs bind the
project principal to the existing registry; an ordinary connection GET verified
the category, target, authentication type and registry metadata. Existing project
pull permission was checked before provisioning. No models, account, project,
registry, host, role or network resource were provisioned by this graph.

Four previously absent CI input names were set from verified standing records:
`MCP_AUTH_APP_CLIENT_ID`, `MCP_ACA_JOBS_COSMOS_ENDPOINT`,
`MCP_ACA_JOBS_STORAGE_ACCOUNT_URL` and `MCP_ACA_JOBS_REGISTRY_ID`.
Existing secrets were neither extracted nor overwritten. Successful writes and
name/timestamp readback do not prove the runner's actual values; the exact-target
preflight must still pass there before any workload write.

Producer authentication is now required during provisioning, before the real MCP
image replaces its inert placeholder. The fixture distinguishes anonymous 401,
permitted 200, excluded-caller 403 and restored-policy 200, with bounded reads.
Its cleanup uses pre-write absence/native ownership receipts and exact app/image
targets, never `azd down` against the shared resource group. Eight additional
local tests cover these changes. The fresh isolated catalog run completed
**1498 tests in 156.326 seconds: PASS, 32 unchanged conditional skips**.
T0 and plugin checks also pass. The later Linux/live results below are attached
to their exact candidate and do not retroactively certify other revisions.

## First candidate execution and safe stop

[Run 36131433448](https://github.com/aiappsgbb/awesome-gbb/actions/runs/36131433448)
tested `67a0409f8203f2994962379a7d737926e6dc9d73`. Its final outcome was
**cancelled on the owner's instruction**, not a successful complete matrix:
11 Azure legs succeeded, 2 failed and 12 were cancelled.

- Linux catalog: **1498 tests PASS, 3 conditional skips**, 164.440 seconds;
  the separate supported hosted cohort passed 83 tests and Doctor passed 21.
  Pin validation, T0, automation gate and delegated-auth local checks passed.
- Passing legs: Harness (authoritative native SDK step), azd-patterns, backup,
  monitor baseline, AGT, caphost lifecycle, cost monitoring, document/vision/
  speech, evals, hosted agents and IQ. A leg PASS is not broader contract,
  private networking, business-effect or client-delivery certification.
- Resource diagnostics produced the malformed marker `PASS`, not the required
  exact result marker. The read-only probe reported a result, but the leg
  correctly failed; no platform failure or successful CI verdict is inferred.
- AgentOps stopped at the missing explicit telemetry-approval input, before
  eval/Doctor. The owner later approved one synthetic run with specific privacy,
  retention and expiry terms; actual dedicated workspace/table retention was
  checked and a private v1 record supplied. A job-specific rerun request was
  rejected because the original workflow was still running. No AgentOps live
  execution or quality/readiness PASS is claimed.
- During cancellation IQ finished; MCP ACA reached bootstrap only, before
  scaffold/provision, and Jobs did not start. Neither authenticated producer
  acceptance nor the Jobs reuse live contract has passed.

**Cleanup is separate and incomplete.** The azd-patterns Job was no longer
present in the scoped readback; the caphost group's original resource set was
unchanged. Hosted teardown was denied by the runner's shell tool. Exact
readback confirmed the run's hosted version and its actual image manifest
remain present. A repository-name lookup derived from the agent name was not
the image's actual reference and is not absence evidence. No alternative delete
was attempted to bypass the denial. Evals reported deletion but its complete
original object identity was not retained; IQ recorded DELETE 204 without an
independent absence check. These gaps remain explicit, not zero-residue claims.

**Target mismatch observed in the first run.** The actual CI hosted target was an
existing non-default project, while the new standing registry connection and
the initial AgentOps approval record were bound to the platform-default
project. Neither resource health nor the default flag authorizes replacing
`FOUNDRY_PROJECT_ENDPOINT`. Reconcile the intended project, exact connection
and still-valid approval before further affected execution; no implicit switch,
approval extension, broad grant or network change is permitted.

The owner's subsequent completion mandate explicitly selected the **existing
actual CI project**, without changing the endpoint, and authorized correcting
its connection and the approval's endpoint binding. The native default
connection name returned an ownership conflict with the other project's
backing workspace. The failed ARM deployment and unchanged owner connection
were reconciled before one project-qualified connection was provisioned using
the same native generic module. Its ordinary GET matched the exact registry
and retained project-MI mapping; no role, network or registry-mode change was
made. The AgentOps record changed only its approved project endpoint; the
original privacy terms, telemetry destinations and expiry remain unchanged.

The owner explicitly instructed that the previously retained hosted version
and associated image **must not be deleted**. They remain retained with residual
cost exposure, not a cleanup PASS or an invented retention deadline. Independent
validation is authorized to continue. New hosted fixture runs now record
pre-write absence and exact version/image custody, and use a bounded helper
that removes only its recorded version, otherwise-empty agent and actual image
manifest. Local tests cover changed versions, shared/nested image repositories
and independent absence readbacks; live validation of this helper is pending.
The follow-up full local suite passed **1547 tests with 32 unchanged skips**
in 164.625 seconds, including eight new hosted-ownership tests. T0 passed.

## Incremental CI integration

The coordinator handed off main
`5fba230af14189bec50b1bdff159c4345e02a1ac` (#521 and #522) for local integration,
preserving the original candidate commit. The merge keeps the new local gates,
driver preflight, required `smoke-result`, and discovery-reported test total;
it also retains this candidate's supported SDK cohort and standing-input checks.
See [incremental CI](incremental-ci.md).

On the merged working tree, **184 targeted tests PASS** and the full isolated
macOS catalog reports **1539 tests PASS, 32 unchanged conditional skips** in
160.847 seconds; T0 and plugin checks pass. These are local integration results,
not Azure validation of the merged head. The owner subsequently authorized
completion, necessary execution and normal protected merge. The specific
no-delete instruction remains in force for the retained first-run hosted
objects, without blocking independent UUID-scoped tests. Selection against the
actual PR base remains 25 legs because of this candidate's shared consumer
input/toolchain changes; the CI integration alone selects only two canaries.
No selector override, assertion relaxation or duplicate full rerun was introduced.

## Live and publication gates

The owner selected the existing CI target and authorized necessary setup, live
operations and verified run-owned cleanup, without a numeric spending ceiling.
This is not permission for unlimited spending: estimate the actual matrix and
execute the minimum reasonable proofs, with no blind repeated full runs or
unexpected expensive permanent infrastructure. Keep run-owned resource
inventory private and verify deletion or obtain explicit bounded retention.
No shared-resource modifications are implicitly authorized.

Required evidence includes: supported deploy/invoke/readback, exact permissions,
actual image/runtime binding, positive/negative ingress as applicable, controlled
lost response with one business effect, and separate client completion.
An omitted MCP auth test is not authenticated-path acceptance.
Teams/browser delivery needs its own authorized equivalent; local channel fakes
do not certify that UI.

Threadlight was inspected read-only at
`4aaf3831a707cf47406ca1629dc6f3673c96b523`: its deployment contract still names
the older toolchain/two-file shape. Its owner must review the published contract
diff and validate adoption separately. No second PR or downstream change is
authorized by this record.

Do not use `Fixes #518`, publish a release, update installed mirrors or claim
closure until the applicable missing evidence is complete. No auto-merge.
