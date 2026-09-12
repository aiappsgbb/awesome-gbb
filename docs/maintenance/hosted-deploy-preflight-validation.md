# Hosted deployment preflight correction — 2026-09-12

**Local implementation; cloud-dependent release validation remains pending.**
No Azure operations, provisioning, RBAC changes, cleanup or runtime-mirror changes
were performed for this correction. This record must not be cited as a new live
hosted deployment PASS.

## Incident and evidence limits

Retained operator evidence from a private injected deployment showed:

- The account, project and model existed, but project capability-host GET returned
  `value: []`. Generic hosted guidance against manual capability hosts conflicted
  with the canonical private Basic project's required `Agents` host.
- The operator used only the existing Basic project-host module after
  authorization; readback returned `Agents` / `Succeeded`. The failed first
  version stayed failed. A second version with unchanged runtime/cohort also
  failed with `ProvisioningError`. Missing setup was real, **not the proven sole
  cause**.
- Native azd creation included `metadata.enableVnextExperience: "true"`, absent
  from the original direct-SDK create. A corrected third version still failed.
  Matching metadata is a creation-contract correction, **not a provisioning fix
  proven sufficient**.
- Raw LIST versions reported `active` while the exact raw version GET
  simultaneously reported `failed` with `ProvisioningError`. Session inventory
  was empty and hosted business receipts/operation ledgers were zero.
- A separate working private setup used a Basic project host and default
  container identity. Its earlier fixed-UID failure concerned
  `/home/session/.sessions`; its empty unmodeled protocol field did not prevent
  success. Those observations do not justify changing every runtime SDK cohort
  or claiming the failed deployment ran.

The application working on another runtime, an offline container starting,
health/liveness and a signed binding are explicitly not hosted execution proof.
All failed versions, images, identities, signed associations and environments
remain preserved by the operator. These are supplied incident observations,
not independently replayed Azure experiments in this worktree.

## Correction and local coverage

One shared read-only JSON evidence gate now distinguishes private Basic,
private Standard/BYO and public platform-managed setup. It never authenticates,
calls Azure or mutates resources. It reports exact blockers and preserves
unknown/failed states. Supplied receipt contents remain an operator trust
boundary; consistency checks do not authenticate a receipt.

RED-first regressions detected the missing executable, both unscoped hosted
prohibitions, stale public-ACR requirement and PUT-as-verification. Subsequent
RED cases caught missing creation metadata validation and malformed nested input.
The bounded agent baseline already chose to stop on conflicting guidance;
no failed agent-behavior run is claimed. Automated regression failures, not
fabricated model mistakes, establish the mechanical RED evidence.

The corrected offline agent scenarios chose preservation/blocked results for
all incompatible or missing prerequisites. They also exposed a staging
ambiguity: actual platform image pull and native mounted-home success cannot
be prerequisites for creating the first session. The corrected gate now
separates network/configuration/local-candidate evidence from mandatory
`pending_live_checks`, and requires actual hosted-home evidence at execution.
No first-session success is inferred from the pre-registration receipt.

An independent local code review found two additional issues, each reproduced
RED before correction: canonical rollout omitted the metadata required by
the new gate, and execution evidence accepted mutable image tags. The rollout
now emits the native metadata and both phases require immutable image digests.

Local checks cover required/missing/healthy/wrong-scope/failed hosts, exact BYO
connections and preservation, private/public mode mismatch, stale/partial reads,
project/model scope/state, ACR date boundary and RBAC/ABAC/policy, operator versus
runtime path, digest/UID/home/protocol/cohort, reserved environment fields,
native creation metadata, and direct-GET versus LIST/business proof.

First-party references checked on 2026-09-12:

- [Deploy a hosted agent](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent):
  project creation **after June 25, 2026** supports private registries; project-MI
  pull and `azureADAuthenticationAsArmPolicy` remain separate requirements.
- [ACR permission modes](https://learn.microsoft.com/azure/container-registry/container-registry-rbac-abac-repository-permissions):
  legacy AcrPull is not honored in ABAC mode.
- [Capability-host GET contract](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts#verify-your-configuration):
  exact account/project scope and connection configuration.

### Executed local checks

| Command / check | Result |
|---|---|
| `python3 -m unittest scripts.tests.test_hosted_deploy_preflight scripts.tests.test_foundry_hosted_agents_refresh_contract scripts.tests.test_foundry_caphost_lifecycle_fixture_contract scripts.tests.test_foundry_endpoint_contract` | 64 tests passed, including actual emitted create arguments and the isolated direct-GET polling function; no Azure clients executed. |
| `python3 scripts/validate-skills.py` | Passed: 38 skills, 34 pins, 205 references and both manifests. |
| `python3 scripts/build-plugins.py --check` | Passed; plugin remains 4.32.0. Existing skills changed only, so no catalog-level version bump. |
| `python3 scripts/build-site.py --out docs/ --validate` | 47 HTML files built; zero broken root-relative links. |
| `git diff --check` | Passed. |
| In-memory nested-shape robustness probe | 744 mutations returned structured gate results without crashes. This is a robustness check, not 744 Azure tests. |

Skill versions: hosted agents **2.2.0 MINOR** (new reusable preflight reference
and executable), VNet deploy **1.2.1 PATCH**, capability-host lifecycle
**2.0.1 PATCH**. Runtime pins and upstream validation dates are unchanged.

## Remaining verification before publication

Run the existing hosted Copilot-CLI fixture on its supported public route and
separately verify private Basic and Standard paths with explicit authorization.
Exercise real project-MI private image pull, actual hosted session home,
authenticated model/tool access and correlated requested tool/audit result.
Attach exact commit/run evidence before release or merge. Local receipt tests
are not T3; no pin refresh, SDK downgrade, public exposure or automatic prompt
substitution is authorized by this change.

The approximate 30-minute objective is a bounded routine operator workflow on
prepared infrastructure, not a guaranteed Azure provisioning duration.
