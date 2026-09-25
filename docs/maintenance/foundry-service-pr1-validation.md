# Foundry service contracts: scoped validation

This record covers the service-contract changes in Toolbox 2.3.0, Routines
1.2.0 and Skills Catalog 2.1.0, with minimal Prompt/Hosted routing corrections.
It is not a claim that every preview, network topology or identity variant
passed. No existing hosted-runtime or upstream package pin was upgraded.

## Source and environments

Manual execution on **2026-09-25** used an approved existing test project,
isolated tenant-specific CLI state and an explicitly selected cached user.
Management used `azure-ai-projects 2.6.1`, `azure-identity 1.25.3` and MCP 1.29.x.
The native Skills provider test used the existing **MAF core 1.17.0** line,
Foundry client 1.13.0 and OpenAI adapter 1.14.2 in a separate environment.
The old hosted runtime was neither rebuilt nor upgraded.

Private-ingress tests used a separate, uniquely owned Basic account/project,
private endpoint/DNS and internal ACA runner with a dedicated managed identity.
Public access stayed disabled. No shared account, network, model deployment,
policy, consent or existing role assignment was changed. The private test used
platform-managed backing stores and deployed no model.

Canonical source under test:

| File | Scope |
|---|---|
| `skills/foundry-toolbox/references/python/service_tools.py` | A2A 1.0 model; source-key ToolConfig composition; explicit no-auth MCP option |
| `skills/foundry-routines/references/creator_routine.py` | Fresh disabled creator routine and fail-closed saved authorization |
| `skills/foundry-skill-catalog/references/skill_packages.py` | Unchanged exact/default version and ZIP reader |
| `skills/foundry-skill-catalog/references/foundry_skills_source.py` | Existing adapter, including optional provider-context compatibility |
| `skills/foundry-skill-catalog/references/mcp_skills_provider.py` | Native experimental MCP progressive-body provider and approval defaults |

Private run inventories bind resource IDs, request IDs, source hashes,
chronological errors/results and cleanup receipts. They are deliberately not
published in this repository.

## Functional evidence

| Surface | Result | Observed acceptance |
|---|---|---|
| Native Skills inline/ZIP | PASS | Two inline versions, ZIP body/asset bytes, exact/default selection, promotion, rollback and stable pin through the unchanged reader |
| Skills Toolbox references | PASS | Actual MCP resource reads; pinned body remained stable while a floating reference changed after promotion/reconnect |
| Native progressive provider | PASS | Two advertised skills; model invoked `load_skill`; only the relevant full body was fetched and its synthetic instruction was applied |
| Adapter/provider interface | PASS | Actual MAF context argument accepted; historical no-argument API retained |
| Tool Search | PASS | Both meta-tools and an explicit source-key pin discovered; ranking keywords found the intended fetch tool |
| Tool invocation | PASS | Harmless public Learn search plus exact discovered-name fetch through `call_tool`; expected document content returned |
| Toolbox versions | PASS | Explicit default promotion/rollback and unchanged original version metadata |
| Prompt Toolbox bridge | PASS, preview | Actual `tool_search` and `call_tool` calls in prompt-agent output, plus expected documentation URL |
| A2A 1.0 Toolbox invocation | PASS | Owned RemoteA2A connection and peer; canonical GA model; completed task with exact synthetic peer output |
| Creator authorization | PASS, configuration | Disabled creation and saved creator wire mapping; not delegated-tool consent |
| Temporal routine | PASS | Real one-shot `timer_delivery` before manual dispatch |
| Manual routine | PASS | Original dispatch ID correlated with completed `queued_dispatch` history |
| Routine business output | PASS | Two original agent-bound responses matched distinct expected inputs; project-level retrieval was 404 |
| Private Skills | PASS | Private DNS/address, canonical pinned download and actual MCP resource content |
| Private File Search | PASS | Synthetic upload/indexing and actual private Toolbox query returned the indexed phrase |
| Public-route rejection | PASS | Valid authenticated external request rejected with “Public access is disabled” |

The routine pair consumed 68 reported model tokens. The first provider run
reported 1,444 tokens; further exact-source/provider and Prompt runs have
separate private usage receipts. Tool-internal indexing/retrieval usage is not
claimed to be included in those model counts. No user spending ceiling was
imposed.

## Failures retained and corrected

- Routines manual dispatch produced `queued_dispatch`, not the test harness's
  expected `manual_dispatch`. The same original dispatch/output was recovered
  without redispatching.
- RemoteA2A requires `properties.audience`; copying a RemoteTool-style metadata
  audience caused an explicit resolver error. Correcting the owned connection
  resolved discovery.
- The discovered A2A `SendMessage` input is a message object with text parts,
  not a string. Invocation passed with the actual discovered schema.
- MAF 1.17 passes a context into `SkillsSource.get_skills`. The adapter now
  accepts it optionally without breaking the old call or changing selection.
- The isolated private project-host deployment reported a missing account
  capability host. GET confirmed absence; the same owned graph was corrected
  using the existing no-subnet account-host pattern. No public fallback or
  unrelated resource replacement was used.
- The first private query probe selected a tool by a substring instead of its
  configured name. The actual schema named it `private-files`; the corrected
  probe used that exact name and passed. Both attempts cleaned their data objects.

## Lifecycle evidence

Functional result and cleanup are separate. All public-test agents, connections,
Toolboxes, Skills, Routines and stored response objects had explicit delete and
authenticated absence checks. Direct provider model requests used `store=False`;
their returned responses were checked for non-persistence.

**A2A exception:** the completed synthetic task/context has documented
service-managed retention of 60 days after the last write. The owner explicitly
accepted that bounded retention; expected expiry is **2026-11-24**. No further
writes are planned. This is **retained with owner acceptance, not verified
deletion** or independent proof of backend purge. The peer, connection and
Toolbox were deleted separately. `AGENT_NOT_FOUND` after peer removal does not
prove `TASK_NOT_FOUND`.

Private probe data objects (Skills, Toolbox, uploaded file and vector store)
were deleted with authenticated absence readback after each attempt. Temporary
infrastructure teardown completed with **19 unique authenticated absence
checks**, including the dedicated runner, hosts, project, private endpoint/NIC,
DNS links/zones, identity, scoped assignment, account, workspace, VNet and the
verified-empty resource-group container. The platform-managed ACA resource
group was also confirmed absent; the deleted Foundry account was purged and
its soft-deleted entry was absent.

The ACA environment remained `ScheduledForDelete` while its platform-owned
infrastructure was being removed. No locks, service-association links or managed
resources were forcibly removed. The same deletion was observed to completion;
an ARM resource-list lag was reconciled before removing the empty group.
No active temporary Azure resources remain from this manual cycle. The accepted
A2A service-managed records above remain a separate retention disposition.

## Explicit coverage limits

Not certified by these tests: GitHub/Teams event delivery, delegated creator
consent/revocation, recurring cron delivery, header-free REST, lazy supplementary
asset/archive behavior, native Prompt `skills`/`harness` fields, BYO datastore
private networking, private A2A/Prompt bridge or general agent-egress isolation.
Existing event/CLI compatibility guidance was not expanded into new certified
recipes. Skills and Prompt Toolbox integration keep their preview terms;
experimental native MCP provider support is not a GA runtime claim.

## Offline and CI boundaries

The unchanged five applicable pin scripts passed through the official isolated
runner. T0 passed for all 42 skills and 35 pins. The complete repository suite
passed **1,448 tests (32 skipped)** in a clean environment using the CI dependency
set. Targeted integration checks passed, including generated-docs versions and
link validation. Nineteen owned
offline tests are now wired into a separate CI environment; the native Skills
consumer fixture is registered without altering auth/retry/quarantine gates.
The registered repository count is now **1,469** after adding 21 cleanup tests;
this count does not claim a new full-suite execution. The closure pass covers
only the changed fixture/cleanup contracts and directly related metadata.

PR checks and their exact source SHA must be recorded in the pull request.
Manual user-identity evidence is not CI/OIDC evidence, and registration is not
a passing consumer-fixture execution.

## Accepted fixture recovery and cleanup scope

After the explicitly selected rollback from the failing Citadel driver to the
working direct-Foundry route, selective Routines and Toolbox CI legs passed.
The new Skills fixture instead performed repository maintenance, without
executing its live API lifecycle. Its instructions now explicitly require live
execution and forbid maintenance/unit-test substitution. This is a fixture
intent correction, not a new functional Skills API failure; its corrected CI
execution remains a separate gate.

The pre-existing MCP ACA fixture had two group-scoped teardown calls targeting
shared infrastructure. Both are replaced by one canonical exact-app ownership
helper and a per-step failure guard. Authentication and MCP/Easy Auth blocks
remain unchanged. Pre-create absence, an independent full run UUID/tag and the
exact approved resource ID bind cleanup; failures preserve their original exit
status. No shared RG, CAE, registry, UAMI, repository or unproven artifact is a
delete target.

A narrow manual ARM check exercised `prepare`, `start`, `capture` and cleanup
using one new MCR-placeholder app and an infra-only `azd provision`. The first
post-delete observation failed closed on an unclassified HTTP404. A later typed
ARM read confirmed absence; no app recreation or second DELETE was performed.
The helper's read-only bounded observation was then refined and covered by
focused mocks, followed by readback of the same already-absent app.

The helper intentionally keeps generic artifact custody unresolved. The manual
check independently proved no image build/push occurred, bound the sole new
deployment-history record through baseline absence, its raw command receipt,
run parameters and app output, then deleted and verified that exact record.
All effects of the manual check are closed; shared resources remained present
with unchanged tags and no new retention was required.

**This is real helper CRUD/cleanup evidence, not the full revised MCP deployment
and authentication fixture.** The focused cleanup suites passed 96 tests and
108 subtests. Neither this evidence nor the three protected branch checks
(`gate`, `validate-pins`, `validate`) waives execution of the corrected Skills
fixture or permits launching an unsafe legacy Jobs path. The coordinator owns
the minimal safe Jobs integration and publication decision.
