# Foundry AgentOps — partial validation record

**Manual evidence as of 2026-09-05, before PR CI. Unreleased:** proposed catalog
**4.31.0**, AgentOps skill **1.0.0**. This is a **draft candidate eligible for PR validation**,
not merged, released, or production-ready. It is **not publicly installable**
through the default install while unmerged; no released downstream pin is available.
CI results and candidate SHA will be recorded in the PR, not as a self-referential
source pin.
This record is a sanitized outcome, not raw logs, a release, or certification.

**Before PR CI, as of 2026-09-05:**

| Gate | Outcome |
|------|---------|
| Corrected-source execution | Completed **corrected-source manual execution PASS** — one native cycle, manual CLI-user route |
| Corrected-source quality | **quality FAIL (4/5 thresholds)** — fluency 2 below threshold 3, despite exact expected match |
| Corrected-source Doctor | **Doctor readiness BLOCKED** — native and evidence checker exit 2; valid evidence, not execution failure |
| Prior verified manual run | Historical **manual execution + quality PASS** — distinct earlier cycle, 5/5 thresholds |
| Unchanged CI / service principal / workload route | **CI/SP NOT RUN** |
| Actual full matrix | **full matrix NOT RUN** |
| Publication | **release PENDING** — not merged or released |

## Corrected-source manual cycle

On **2026-09-05**, one native cycle completed in **166.5 seconds**, from
11:46:48.575949 to 11:49:35.035578 UTC. The current Copilot session executed the
corrected fixture directly with a CLI **user** identity via `AzureCliCredential`;
`AZURE_CLIENT_ID` was unset. No recursive or second CLI was launched.

Preflight stopped on a copied cache's **wrong subscription** before native work.
The owner context selection was then resolved: the owner approved initializing
only the explicitly selected subscription in the disposable copy. The same
approved tenant/user was verified, and that cache stayed fixed throughout the
native cycle. This was not a shared-context switch or a new retry cycle.

- Native pin: `agentops-accelerator==0.14.0` (cockpit extra), upstream
  [`v0.14.0`](https://github.com/Azure/agentops/tree/v0.14.0), commit
  `fb5c93eee489c71ef4084fa209adae24f762e3d7`.
- Resolved dependencies: `azure-ai-projects` 2.4.0, `azure-identity` 1.25.3,
  `httpx` 0.28.1. Sol served the target, eval judge, and Doctor judge roles.
- **auth exit 0**, **Analyze exit 0**, **Eval exit 2**, **execution checker exit 0**.
  Evaluation executed successfully; quality did not pass. One synthetic row had
  an **exact expected match**, but **fluency 2** missed the native default
  **threshold 3**. Coherence, similarity, and response completeness each scored
  5; average latency was approximately 1.77 seconds.
- The native row summary reported `items_passed_all=1` and `items_pass_rate=1.0`,
  but aggregate policy reported `thresholds_passed=4`, `thresholds_total=5`,
  `threshold_pass_rate=0.8`, and `overall_passed=false`. The actual quality gate
  is **4/5 thresholds**, not the contradictory green row proxy.
- **Doctor exit 2**, **evidence checker exit 2**, valid **evidence v1**:
  **2 critical** findings, **8 warnings**, **1 info**. Critical IDs were
  `opex.release.latest_eval_failed` and `waf.security.local_auth_disabled`.
  These are native finding IDs, not a claim that API key authentication was
  disabled or that remediation occurred.
- All four sources were enabled:
  `results_history`, `azure_monitor`, `foundry_control`, `azure_resources`.
  All four approved component-scoped monitoring aggregates were queried over a
  **1-day** lookback; this is historical telemetry, not fresh per-agent ingestion.
- There was **no retry**, **no threshold reduction**, **no errors hidden**, and
  **no shared repair**. All subprocesses completed without timeout. Doctor's
  valid blocked result is not malformed evidence or a successful readiness gate.

## Prior manual cycle (historical, distinct)

The prior outer CLI stalled at the **first skill-load** and was stopped before
any native work. A direct current-Copilot **manual continuation** then completed
one native cycle using a CLI user identity through `AzureCliCredential`.
Analyze and Eval each returned exit 0: one synthetic row, exact expected match,
**5/5 thresholds passed**. Doctor returned exit 2 with evidence v1,
**1 critical**, **8 warnings**, **1 info**. The critical finding was enabled local
**API key** authentication in the shared environment; no account changes were
authorized or made to remove it.

This earlier cycle remains historical evidence, not the corrected cycle's quality
result. Neither cycle proves that the stalled outer executor recovered, nor is
either a substitute for unchanged CI/service-principal execution. One-row samples
are not broad quality coverage.

## Evidence fingerprints

Private evidence fingerprints (SHA-256; raw material remains private). Corrected
artifact digests come from the sanitized corrected summary. The current source
fixture's SHA-256 was independently matched to its executed-fixture digest;
changing that fixture requires new evidence. Prior provenance remains distinct.

| Artifact | Digest |
|----------|--------|
| Corrected sanitized outcome summary | `6a2369c43e2559b63d7fd4c7ef0f26511aa3b3a29c2b0db9d36f65147f0b6526` |
| Executed corrected-source fixture | `22de211e642a915c451c444e1f8005624108e3a5b4d7769c422520fe098aea5e` |
| Corrected approval | `60436f44aa6e105f17c435268010dd4a0dfb2c84c7002894378d233cf229f058` |
| Corrected native results | `f40a0419dbee405e01f9fa445049b300bf6286c5f07e61a0ccdad850b7823563` |
| Corrected Doctor evidence | `c52e7c5453c6958281fc642a6e1208034d4a575a48223000d0e5d512358cee16` |
| Corrected Doctor history | `fbd2f2c237690539ed2505d9891c219918dfe6908e4788c282232f20e8ba4510` |
| Corrected outcome | `363dcadb7fdcb1542950bd4b57a269a70927e4ebd74829311a08f03449851560` |
| Verified prior outcome summary | `f9c63bae9bb1689951f0c51951129c5b9a0390226c28d33e3e55e5ef5d6c81f7` |
| Executed prior fixture, not corrected source | `49d8cc10d42aa159b4cf8220a11d25d114f85c3376256d39607138d502463f4d` |

## Readiness, privacy, and cleanup limits

- The observability readiness label was misleading: underlying status was
  `not_configured`, with **0 rows** and **0 rubrics**. It does not prove readiness.
- **24-hour** Application Insights aggregates were historical, not proof of
  **fresh ingestion** from this cycle. The official evaluation was missing;
  governance and landing-zone readiness were unknown.
- No existing conversations were searched or reused.
- Own agent versions were deleted, with agent-container **GET 404** asserted by
  the same timed cleanup subprocess, not an additional Azure call. The disposable
  workspace and only the **new copied credentials** were removed; the original
  context alias was untouched. Persistent model deployments were untouched.
- Stored Responses remain **purge unproven**: native invocation omits `store=false`
  and loses the **response ID**, so individual deletion was not verified.
  Any service-stored synthetic response remains under **approved service retention**;
  workspace cleanup is not proof of service-side erasure.
- The local raw-artifact **7-day** deletion policy and effective table **90-day**
  retention are distinct, **illustrative** observations, not recommended defaults
  or a service-side deletion deadline. Component retention was 90 days; the workspace
  default was 30 days, but effective table retention was 90 days.
- **Both cycles**' raw local artifacts are scheduled for deletion on
  **2026-09-12 at 07:29:57 UTC**, retaining the original schedule. Corrected-cycle
  deletion is **intentionally earlier** than its 7-day maximum. The schedule is
  **not proof that deletion has occurred** and does not establish service purge.

## Pending gates

Corrected-source manual execution is complete, but quality failed and Doctor
readiness is blocked. No retry, threshold adjustment, or shared-environment repair
was used to turn those outcomes green. The prior result does not override them.

Evidence-bearing draft push/PR authorization is granted before the final candidate
commit, with normal push and the existing full **23-fixture** CI matrix using
**CI resources only**. This does not authorize merge, release, auto-merge,
Threadlight work, or shared-Azure mutations.

At the manual-record cutoff above, the unchanged CI/SP/workload route and actual
full matrix were **not run**. No non-main workflow dispatch, OIDC mutation, staging,
commit, push, PR, merge, release, main checkout, or Threadlight work was performed
in that manual correction cycle. No personal-user run was substituted for CI
evidence. Subsequent CI results and the candidate SHA belong in the PR; neither
this historical record nor PR validation alone establishes production readiness.

Proposed specialist PATCH versions remain `foundry-evals` **1.3.2**,
`foundry-observability` **1.2.4**, and `foundry-agt` **2.0.1**.
See [catalog adoption](../../README.md#per-agent-agentops-adoption) and
[unreleased changes](../../CHANGELOG.md).
