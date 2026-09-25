# Hosted deployment: prerequisites to requested tool result

This is the shared contract for hosted agents, private setup and capability-host
lifecycle. It is not a deployment framework or permission to repair resources.
Use `azd` by default. For an approved raw/brownfield integration, preserve its
native creation contract and the selected runtime cohort.

## Early capability evidence

Before preparing an image, run `deploy_preflight.py <private-capabilities.json>
--phase capabilities`. This separate schema-1 snapshot needs no image or future
session. `READY_FOR_ARTIFACTS` is an evidence-consistency result, not authorization,
not effective-policy evaluation by the helper, and not runtime proof.

| Field | Required observation/decision |
|---|---|
| `schema_version`, `observed_at` | `1`, oldest observation timestamp; same freshness rules as setup |
| `target.profile`, `consumer` | Explicit profile from `hosted-contract.json`, observed exact azd/extension versions |
| `target.mode`, `target.registry_network` | `basic-private`, `standard-private` or `managed-public`; registry `private` or `public`. Required features must include hosted-container and the selected private-agent-network/private-registry-pull/byo-stores capabilities. A private registry also requires the native `environment.project_created_at` observation after the documented June 25 boundary. |
| `target.environment_id`, `target.required_features`; `environment` | Exact environment resource, supported feature names and retained evidence; receipt fields `result`, `evidence`, `resource_id`, `supported_features` |
| `target.registry_id`, `target.repository`, `target.pull_requirement` | Explicit registry/repository and `repository-only` or `registry-wide`; the latter also requires `registry_wide_approved: true` |
| `registry` | Receipt with `id`, `role_assignment_mode`; repository-only requires `repository_condition_verified` and `broader_pull_grants_excluded`, both true based on real effective-policy observations |
| `target.source_access_required` | Explicit boolean; false only for a workload with no external source |
| `target.required_permissions` | One row per `image-pull`, `invoke`, `version-read`, `response-read`, `session-read`; add `source-read` if needed. Each row: `operation`, actual `principal_id`, `scope`, exact required `actions`, reviewed versioned `api_contract` reference |
| `permissions` | Exactly one matching receipt per operation, identical identity/scope/actions/API contract plus `effective_conditions_verified: true`; the collector must examine applicable roles/conditions, not merely copy the requested values |
| `ingress` | Receipt with `authentication_enforced`, `direct_backend_bypass_blocked`; `forwarded_headers: ignored` or `verified-proxy-chain` with a retained `trusted_proxy_contract` |

Use the actual identities per hop. Project-MI pull does not establish the caller's
version-read or result-read permission. Invoke permission does not imply either
read. Registry-wide `AcrPull` cannot meet repository-only requirements, and an
ABAC role without a repository condition is also registry-wide. Missing access
or an unsupported environment blocks dependent work without grants, registry-mode
changes, public exposure or trusting arbitrary headers.

The setup schema below is retained for existing observation files. It does not
replace this earlier gate; its legacy `condition_allows_repository` boolean
proves neither repository isolation nor this expanded permission contract.

## Scope before action

| Mode accepted by the gate | Required setup | Missing or incompatible setup |
|---|---|---|
| `basic-private` | Private injected AIServices account, project/model, **project** host `Agents`/`Succeeded`, no BYO connection arrays | Empty successful project inventory: obtain explicit authorization for only the [Basic project-host module](../../foundry-vnet-deploy/templates/basic-vnet/modules-network-secured/add-project-capability-host.bicep), using the existing account/project. No account-host creation requirement. |
| `standard-private` | Account host/subnet plus project host with exact approved BYO names | Stop for the existing [Standard module/lifecycle](../../foundry-caphost-lifecycle/SKILL.md). Preserve all hosts, connections and stores. Never substitute Basic. |
| `managed-public` | Selected public/platform-managed azd setup | No additional manual hosts from legacy guidance. Existing BYO configuration requires a mode decision, not silent reuse. |

Private brownfield azd is still private: an `endpoint:` pointer does not establish
the project host. Raw/legacy public or other modes are deliberately **not
automatically certified** by this bounded gate; review their specific contract.
Do not introduce `enablePublicHostingEnvironment` into a private project.

Every selected existing registry also needs its own **project-scoped
ContainerRegistry connection**, separately from the capability-host BYO arrays.
The gate reuses a correct connection without writes. Missing routes to
[native connection-only provisioning](private-basic.md#missing-only-native-configurationprovisioning)
with explicit authorization; unreadable or mismatched state blocks. Native
identity mapping must have retained non-secret provisioning provenance, not a
credential-retrieval call or an inference from `AcrPull`.

For verification use only GET, never an idempotent-looking PUT. Retain full
successful inventories, consume pagination, and read each returned host by its
actual name. Use the [lifecycle GET shapes](../../foundry-caphost-lifecycle/SKILL.md#5-inspect-query-caphost-state-before-any-change);
retain `id`, `capabilityHostKind`, state and connection names, without credentials.
403, unsupported API, timeout and partial inventory are **unknown**, not `value: []`.
Creating/deleting/failed hosts block registration; record the exact scope/error
and use a bounded observation window, not automatic DELETE/recreate/purge.

## Collect once, fail early

Use an approved read-only operator path, with tenant isolation already established.
Do not log secrets, tokens, signed bindings or full runtime environment values.
Keep snapshots and receipt files private. Set `observed_at` to the **oldest**
included observation, never to the time you edited the evidence file.

The canonical [Python gate](python/deploy_preflight.py) uses only the standard
library. From the catalog root:

```bash
python3 skills/foundry-hosted-agents/references/python/deploy_preflight.py <private-setup-evidence.json>
python3 skills/foundry-hosted-agents/references/python/deploy_preflight.py <private-execution-evidence.json> --phase execution
```

Exit `1` means `BLOCKED`, with the first issue's exact `code`, `scope` and `action`.
Resolve/recollect that observation before rerunning. Exit `0` for setup means
`READY_FOR_REGISTRATION`, **not permission to deploy and not hosted success**.
The result explicitly lists `pending_live_checks`: real project-MI platform
pull, native mounted session home, hosted model/tool access, direct-version
readiness, endpoint routing and requested business result. These cannot be
certified before the first hosted session exists. Do not make setup circular by
inventing such receipts: configuration/network/local-candidate checks precede
registration; actual session checks follow it.
No calls, logins, role assignments, file rewrites or remediation happen in this
helper. It validates supplied evidence structure/consistency; it does **not**
independently authenticate receipt contents or verify the operator's assertions.
Never populate a `pass` from assumption, a laptop-only check, or health alone.

### Setup evidence schema (version 1)

All fields below are required unless explicitly conditional. ARM objects retain
their native camelCase; gate-specific observation records use snake_case.

| Field | Required content / collection |
|---|---|
| `schema_version`, `observed_at` | `1`; timezone-aware ISO timestamp, at most 30 minutes old, not in the future. |
| `target` | Approved `mode`, `account_id`, `project_id`, `model_id`, `registry_id`, `registry_connection_name`, `registry_network` (`private` or `public`), immutable `image` (`registry/repository@sha256:<64 hex>`), `project_endpoint`, `operator_route`, `runtime_route`, `tool_endpoints` (all required tools; empty only if none), `connections` (approved map of connection arrays), and `model_env` (the runtime's model environment key; its declared value must match the deployment name in `model_id`). Private modes also supply `subnet_id`. The opt-in live BASIC consumer additionally requires `tenant_id`. |
| `project_connections` | Complete credential-free ordinary ARM GET-list envelope `{"value": [...]}` without error or unconsumed `nextLink`. Selected connection retains exact project child `id`, `properties.category: ContainerRegistry`, bare `target` matching registry `loginServer`, `authType: ManagedIdentity`, `metadata.ResourceId` matching registry ARM ID, no error or returned credentials. Never use listsecrets. |
| `registry_connection_identity` | Non-secret projection of reviewed native provisioning: selected `connection_id`, project `principal_id`, registry `registry_id`, `source: native-provisioning`, and retained `evidence` reference. The native registry contract maps `credentials.clientId` to **project principalId**, `credentials.resourceId` to the registry ID. Missing provenance blocks; GET metadata/roles alone do not establish this mapping. |
| `account`, `project`, `model`, `registry` | Exact ARM GET bodies: `id`, `properties.provisioningState`. Account also `kind: AIServices`, `publicNetworkAccess`, `networkInjections`; each private injection has `scenario: agent`, selected `subnetArmId`, `useMicrosoftManagedNetwork: false`. Project retains `identity.principalId`, `systemData.createdAt`, and `properties.endpoints`; selected `project_endpoint` must be among these endpoints. |
| `account_hosts`, `project_hosts` | Complete successful GET-list envelopes `{"value": [...]}` without unconsumed `nextLink`. Retain exact host GET bodies in `value` after comparing identities with the inventory. Do not turn a read failure into an empty list. |
| Host properties | `capabilityHostKind: Agents`, `provisioningState: Succeeded`. Standard account: selected `customerSubnet`; project: exact `threadStorageConnections`, `vectorStoreConnections`, `storageConnections`, optional `aiServicesConnections`. Basic: arrays absent/null/empty. Names are not ARM IDs. |
| Registry properties | `loginServer`, `publicNetworkAccess`, `roleAssignmentMode` (`AbacRepositoryPermissions` or `LegacyRegistryPermissions`), `policies.azureADAuthenticationAsArmPolicy.status: enabled`. Do not change mode to make a role work. |
| `pull` | Receipt plus **project MI** `principal_id`, registry `scope`, `repository`, mode-appropriate `role`, `condition_allows_repository: true`. Verify effective assignment/ABAC conditions for that repository; deployer/agent MI access is not evidence of project-MI pull. |
| `probes` | Receipt array, each with `purpose`, exact `target`, approved `route`, `tls_verified: true`. `operator-project` targets `project_endpoint` on `operator_route`; `runtime-model` targets `model_id`; `runtime-tool` targets each tool endpoint. These three require `authenticated: true` using an approved probe identity, whose limits the receipt records. `registry-network` targets the immutable image's registry route and requires `network_reachable: true` (DNS/TLS, including registry/data endpoints; an expected auth challenge proves only network reachability). The latter three purposes use `runtime_route`. |
| `runtime` | Receipt for the exact `image`, `platform: linux/amd64`, `container_user: ""` (default image identity), `session_home: /home/session`, `session_home_writable: true`, `session_home_check: local-candidate` (or an already observed `hosted-session`), `protocol: responses`, `protocol_version: 2.0.0`, `cohort_reference`, `cohort_verified: true`, `management_environment_separate: true`. |
| `registration` | `path: sdk` or `azd`, `metadata.enableVnextExperience: "true"` (string), `evidence` referencing the reviewed frozen create request/native emission. This matches the observed native azd creation path; it does not guarantee provisioning. |
| `environment_variables` | Only user-declared string map from YAML/SDK definition. No `FOUNDRY_*`, `AGENT_*` or `APPLICATIONINSIGHTS_CONNECTION_STRING`. Do not dump platform-injected values into it. |

A **receipt** is `{"result": "pass", "evidence": "<private-observation-reference>"}`
plus the fields in its row. The reference must identify actual retained output,
not a planned test. No boolean/receipt here is a cryptographic attestation.
Supply exactly one current receipt per required purpose/target/route. Duplicate
or contradictory matching probes block; resolve the conflict through a new
observation and retain superseded attempts separately, not as competing current
receipts.
Runtime-path model/tool probes must cover DNS, TLS and the expected authenticated
surface from the injected network, not only an operator proxy. If using an approved
equivalent probe location before registration, document its equivalence and
identity limits in the receipt; it still cannot certify the future hosted session.
An unavailable network/probe check stays blocked rather than quietly falling back
to public DNS. Registry network reachability and effective project-MI role/policy
checks are prerequisites, not a fabricated actual project-MI image-pull receipt.

The runtime receipt binds a container inspection/startup/write/import check to
the exact digest and chosen validated lock/cohort. For `local-candidate`, verify
write/startup behavior under `/home/session/.sessions` using the planned home/mount
layout, explicitly recording that the live mount is still pending.
Do not force UID 65532, override the platform home, chmod platform mounts or
weaken readiness. A local writable directory is not proof the live mounted home
works. A fixed-UID/custom runtime needs separate validation, outside this default
route. Keep management SDK packages separate from the hosted image; do not copy
all pins from an unrelated working cohort. Responses `2.0.0` is a protocol
version, not a mandate to set every SDK package to version 2.0.0.

### Private ACR condition (checked 2026-09-12)

[Microsoft Learn](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent)
states projects created **after June 25, 2026** support registries behind private
endpoints with public access disabled. Projects created before that date require
public endpoint reachability for image pulls. The day itself is ambiguous in the
source: the gate blocks June 25/older/unknown dates for an owner decision. Use
**project** creation time, not account age. Never expose a retained private registry
automatically. A supported generation does not prove DNS, pull authorization or
registry policy.

[ACR's permission-mode contract](https://learn.microsoft.com/azure/container-registry/container-registry-rbac-abac-repository-permissions)
distinguishes `Container Registry Repository Reader` for ABAC mode from `AcrPull`
for legacy mode. Legacy roles are not honored by ABAC registries. Verify narrow
repository conditions and `azureADAuthenticationAsArmPolicy`; no broad role grants.

## One route, four evidence gates

These business-execution gates remain mandatory when business tools are
requested. For a **no-tools** bootstrap, use the separate
[native private BASIC oracle](private-basic.md): a real completed model response
and independent response/session/version readbacks, without inventing a business
receipt or requiring future tool authentication. It does not certify business
effects or independently prove a native mount write.

1. **Prerequisites:** select mode, read exact project/model/hosts and registry,
   collect path/runtime observations, run setup gate. Use the existing azd
   packaging/deployment path; freeze the candidate image and complete definition
   before registration. If that route rebuilds the image, recheck the new digest;
   an image override is not proof no rebuild occurred. Raw SDK integrations must
   preserve native creation metadata, typed Responses protocol and identity
   contract. An empty unmodeled `container_protocol_versions` field is not evidence
   of a broken serializer when typed `protocol_versions` is correct.
2. **Registration:** issue one approved create for the frozen inputs. On lost ACK,
   timeout or disconnect, retain the attempt and **list/reconcile before retry**.
   Compare name/version, digest, full definition, creation metadata and actual
   identity. One exact match may be recovered; multiple/divergent/unknown results
   block. LIST `active` is not readiness. Do not add timestamps or change the
   image merely to defeat deduplication after an uncertain create.
3. **Readiness and invocation:** poll the exact **direct version GET**, requiring
   two consecutive `active` observations with no error. Stop on failed or after
   the agreed budget; retain IDs, request correlations and errors. Observe exact
   endpoint routing/version/identity/digest, then make an authenticated request.
   Preserve signed associations; any changed version/image/identity requires a
   new observation and association, never reuse an old binding.
4. **Requested result:** retain response/session/tool-call identifiers and
   independently correlated business audit/result. For writes, verify the real
   authorized effect and replay semantics; for identity, compare actual claims.
   Empty output, noop, health, assistant prose or a VM result cannot certify it.
   A prompt agent is a separately agreed architecture, not an automatic fallback.

### Execution evidence schema

The execution file supplies `observed_at` (oldest included receipt/observation,
fresh within 30 minutes), expected `version`, immutable `image`, actual hosted
`identity`, and `observations` in chronological order. Each observation has those
three binding fields, `source: direct-version-get`, `status`, `observed_at`, and
the actual `error` when present. The last two must be distinct, fresh, active
direct GETs without errors.
The entire supplied history must have valid, strictly increasing timestamps;
an out-of-order entry could otherwise hide a newer failed GET. Older failures
may precede later recovery, but must never be moved ahead of older active reads
to make the final two entries pass.

`endpoint` and `invocation` are receipts with the same three binding fields.
Invocation also requires `response_id`, `session_id`. `business` is a receipt
with the same `response_id`, `tool_call_id`, independent `audit_id`, and
`requested_result_verified: true`. `hosted_runtime` is a receipt with the same
version/image/identity and invocation `session_id`, plus
`native_session_home_writable: true` from the **actual** hosted session. Read
the underlying receipts: the helper
reports `BUSINESS_PROOF_RECORDED` / `RECORDED_NOT_INDEPENDENTLY_VERIFIED`,
not a new live test. It does not issue requests or authorize business effects.

Aim for a roughly 30-minute **routine** cycle on already supported/ready
infrastructure: agree finite prerequisite, registration and invocation budgets
before starting (for example 5/15/10 minutes). This is an operator stop/escalation
budget, not an Azure provisioning SLA. Greenfield private deployments, propagation
or platform failures may exceed it; return an actionable blocked result rather
than expanding scope, guessing SDKs, deleting resources or promising completion.
