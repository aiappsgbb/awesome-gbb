# Threadlight boundary and reusable evidence

AgentOps handles one already-deployed agent. It neither deploys a Threadlight
lifecycle nor replaces the owning platform's controls. This is an ownership
contract, not an executable integration.

## Approved responsibility matrix

| Owner | Owns | What foundry-agentops does instead of duplicating it |
|---|---|---|
| Citadel | Gateway/access contracts, tenant and network isolation, routing, rate limits | Consume the existing approved endpoint and access path. Report gaps; **do not mutate Citadel**, APIM, RBAC, routing or networking. |
| `foundry-evals` | Deep evaluator design, dataset curation, evaluation methodology | Run the agreed per-agent native eval loop and retain its results. Reuse compatible reviewed evidence; do not invent a competing deep-eval suite. |
| `foundry-observability` | OpenTelemetry instrumentation, App Insights integration, telemetry destination/capture/retention approval | Read authorized telemetry and record availability/coverage; require separate pre-execution approval for native network exports. Missing telemetry is unverified, not permission to instrument or healthy status. |
| `foundry-agt` | AGT authoring and runtime governance | Inspect approved governance evidence; do not change AGT runtime behavior or claim enforcement from a file's presence. |
| `foundry-agentops` | One-agent operations, Doctor, regression/baseline review, trace promotion and native operational evidence | Preserve target, time, coverage, native status and private provenance; no final production-readiness certification. |
| Threadlight lifecycle | Lifecycle normalization, cross-stage evidence and final readiness/policy decisions | Supply compatible native artifacts and prerequisites only; final interpretation and readiness remain with Threadlight. |
| `threadlight-cicd` | Threadlight pipeline generation, gates and final workflow ownership | Supply config/prerequisites and a sanitized gap summary; never run `workflow generate` or author competing pipelines in Threadlight mode. |

Detection and working-directory rules live in
[workflow-modes.md](workflow-modes.md); one-agent selection and context
reconciliation live in [SKILL.md](../SKILL.md).

Local logs staying private do not authorize network exports. Apply the
[PRE-EXECUTION telemetry approval](day2-runbook.md#pre-execution-telemetry-approval)
before every adopted eval/Doctor invocation. Native project auto-discovery is not
authorization to capture payloads. If destination, capture or retention is
unverified/unauthorized, STOP and hand off to `foundry-observability`; do not
change Citadel, instrument the runtime or rewrite approved configuration here.

## Reuse, not replacement

Existing eval, Red Team, ASSERT or ACS evidence can be reused only when its
format is understood and its target/version, environment, freshness, scope,
coverage and hashes match the intended decision. Record the actual producer,
version and run; do not relabel another producer's result as an AgentOps run.

Native `assert_path`, `acs_path`, `redteam_path` are artifact references, not
commands or execution/enforcement proof. Generic discovery can summarize a plan
or contract that has never run. Deep tests remain with their owners: do not
repeat a compatible completed scan just to obtain an AgentOps-branded file.
If evidence lacks required normalization, request a reviewed compatible export
or mark the gap; do not synthesize a pass.

Apply [artifact-contract.md](artifact-contract.md): retain original native
results privately, supply only allowlisted status/metric/gap summaries,
provenance and restricted pointers downstream. Preserve native blocked/warning/
unknown states. An AgentOps `ready` is neither Threadlight readiness nor a
release approval, and standalone mode cannot claim final readiness either.

## Adapter is future work

A Threadlight adapter for this contract is **not yet released**. This skill
ships no adapter executable, normalization schema, manifest writer or
Threadlight readiness scorer. Do not recommend a nonexistent sibling command
or skill as though it can be invoked now. Do not create or edit
`specs/manifest.json`, merge native fields into it, or invent a manifest block.

Until an adapter is reviewed and released, hand the lifecycle owner the existing
restricted archive pointers plus a sanitized inventory of producer, agent,
environment, timestamps, coverage, native gate status and unresolved gaps.
Any future adapter must validate the native contracts, preserve failure signals,
enforce the private-payload boundary and defer final policy to Threadlight.
Neither this handoff nor an unsigned mutable latest artifact certifies readiness.
