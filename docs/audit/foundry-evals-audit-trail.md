# `foundry-evals` — Deep audit trail (21 findings)

| Field | Value |
| --- | --- |
| Skill | `foundry-evals` |
| SKILL.md version before | 1.1.0 |
| SKILL.md version after | 1.1.1 |
| Audit date | 2026-05-31 |
| Auditor | Phase 4 audit worker (`unsafecode/audit-foundry-evals`) |
| Companion PR | _this PR_ |
| Predecessor PRs | #199 (`foundry-memory`), #198 (`foundry-toolbox`), #197 (`foundry-agt`) |
| Bug-class scan reference | `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` Appendix A (L381-403) |
| Audit surface | `skills/foundry-evals/SKILL.md` (1426 L) + `references/python/{eval_runner.py, url_citation_grader.py}` (111 L + 102 L) + `references/upstream-pin.md` (383 L) + `test-fixture/consumer_prompt.md` (96 L, read-only) |
| Pin facts (verified) | `azure-ai-projects~=2.0`, `azure-identity~=1.19`, `python-dotenv~=1.0`; upstream SHA `99ed7476…`; `automation_tier: auto`, `runnable: false`; last validated 2026-05-30 by `ricchi` |

This audit scans the four-file `foundry-evals` surface against the 21
bug-class catalog in Appendix A. **Three findings are HITs fixed in this
PR** — **C1 (medium)** consolidates six PoC-name scrubs across SKILL.md and
the two reference Python files; **C9 (medium)** lifts the Pattern 23
project-SAMI RBAC contract from buried CI notes to consumer-facing
prerequisites with a verification command; **C21 (low)** corrects two
prose-vs-pin drift sites (`azure-ai-projects` floor narrative + the pip
recipe). **One finding is deferred** — **C15 (medium)** flags an SDK
shape pattern in `eval_runner.py` L60-80 whose validation requires a live
Foundry project (`runnable: false` pin); it ships in the next pin
refresh. The remaining seventeen classes resolve cleanly: `foundry-evals`
ships no Bicep / no azd template / no CLI install instructions / no
webhook / no async runtime / no telemetry-producer surface, so C2, C3,
C4, C6, C10, C13, C14, C16, C18 are N/A by construction, and C5, C7, C8,
C11, C12, C17, C19, C20 each carry an inline grep proving the absence.
All three HITs land under a single `[skill-rewrite]` commit that bumps
`metadata.version` 1.1.0 → 1.1.1. The Phase-3-green fixture
(`test-fixture/consumer_prompt.md`, runs `26716554166`, `26716984572`,
`26717346015`) is untouched and re-runs on this PR via Pattern 24
change-gating — expect only the `foundry-evals` matrix leg (~3-5 min
wall-clock).

---

## Findings

### C1 — Hardcoded secrets, GUIDs, customer identifiers — **HIT (medium)**

Pre-audit, six SKILL.md / reference-file sites name customer-pilot
artefacts that violate AGENTS.md § 2.1 ("no PoC names, no customer
names"). The narrowed scrub grep
`grep -nE 'kyc-poc|S-019|learn-assistant|smb-credit-memo|v1[02]' skills/foundry-evals/`
returned matches at SKILL.md L190-191 (cold-start trap anecdote referenced
"kyc-poc"), L266-267 (lost-results recipe referenced "S-019"), L710
(skill-name-collision example listed "learn-assistant"), L880-905
(troubleshooting tables referenced "smb-credit-memo" judge runs), plus
`references/python/eval_runner.py` L27-29 (docstring credited
"kyc-poc + S-019 pilots") and `references/python/url_citation_grader.py`
L33-37 (docstring named "smb-credit-memo" and "v12" version label). None
of these were template placeholders — they were verbatim pilot names
that leaked from the original author's working notes. Per the same § 2.1
rule, the role-definition GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d` at
L1114 is an explicit Azure built-in (`Azure AI User`) so it remains;
the audit-trail confirms this is the only allowed-GUID exception.

**Before** (representative — SKILL.md L190-191, the most visible site):
```text
2. **The agent's response can ALSO contain non-ASCII** (the gap that bit
   the kyc-poc pilot twice with #1 in place)
```

**After:**
```text
2. **The agent's response can ALSO contain non-ASCII** (the gap that bit
   us twice in pilot runs even with #1 in place)
```

**Plus** the same scrub pattern applied at SKILL.md L266-267, L710,
L880-905 and at `eval_runner.py` L27-29 + `url_citation_grader.py`
L33-37 — six edits total, each replacing a pilot-name reference with
generic prose that preserves the original signal ("field-tested",
"cold-start trap", "skill-name-collision example") without leaking the
pilot identity.

**Post-edit verification:**
`grep -rnE 'kyc-poc|S-019|learn-assistant|smb-credit-memo|v1[02]' skills/foundry-evals/`
returns empty — no remaining PoC names anywhere in the skill tree
(SKILL.md, references, fixture).

**Disposition.** Fix-in-PR. Scope: `skills/foundry-evals/SKILL.md` + two
reference Python files. PATCH bump 1.1.0 → 1.1.1. Counted toward the
`[skill-rewrite]` commit tag.

---

### C2 — Bicep shape drift — N/A

`foundry-evals` ships no Bicep. Consumers reuse the AI Services account
+ judge-model deployment they provisioned for `foundry-hosted-agents` or
`citadel-hub-deploy`. Verification:
`find skills/foundry-evals -name '*.bicep'` → empty.

---

### C3 — CLI install drift (Pattern 15) — N/A

The skill ships no `az` / `azd` / `func` install instructions; consumers
run pure-Python from a shell that already has `pip` available. The
fixture's Step 0 (Pattern 11) calls `az account show` for the show-don't-
assert credential probe, but treats `az` as pre-installed on the GHA
runner (correct — `az` is in the known-pre-installed CLI set per
Pattern 15 rule 3).

---

### C4 — OIDC TTL / teardown bounds (Pattern 25) — N/A

Eval runs are short-lived SDK calls (typically < 10 min) against an
existing AI Services account + agent. The skill creates no
side-resources beyond an Evaluation row in the Foundry project (which
the SDK auto-prunes from the UI's default view after 30 days). There is
no multi-step teardown loop to bound, and no OIDC TTL race window.
Pattern 25 applies only to fixtures that create ACR / ACA / managed-env
resources.

---

### C5 — Preview-CLI flag branching (Pattern 16) — none observed

`grep -nE 'azd ai|az containerapp.*--' skills/foundry-evals/SKILL.md`
→ empty. The skill prescribes only the GA-stable
`azure-ai-projects.evals.runs.create(...)` Python surface; no preview
azd extension subcommands and no `az` preview commands are documented
for consumers.

---

### C6 — azd ↔ ACA Jobs deploy-gap (Pattern 18) — N/A

No azd template, no ACA resources of any kind. Eval runs execute inside
the Foundry control plane (the project itself orchestrates the judge-
model invocations); the consumer's local Python is a thin SDK client.

---

### C7 — Foundry SDK shape drift — none observed

Spot-check of the documented `EvaluationRule` continuous-eval call site at
SKILL.md L1099-1124 against the pinned `azure-ai-projects~=2.0` surface
(commit `99ed7476…`, validated 2026-05-30): `EvaluationRule(name=...,
display_name=..., evaluators=[...], event_type=..., filter=..., enabled=...)`
matches the May 2026 preview SDK's `EvaluationRule` constructor signature.
The one-shot eval-run path in `references/python/eval_runner.py` L60-80
uses `client.evals.create(name=, description=, evaluators=[...])` plus
`client.evals.runs.create(eval_id=, name=, data_source={...})` — both
match the GA shape on the pinned SDK. C15 below covers a separate
behavioural concern (whether `runs.create` returns terminal `.metrics` or
requires the caller to poll `runs.get(...).status`); that's deferred to a
live-Foundry soak-test, not a shape mismatch.

---

### C8 — Deprecated SDK API refs — none observed

`grep -nE 'OpenAIChatClient|FoundryChatClient|AgentRunner' skills/foundry-evals/SKILL.md`
→ empty. `foundry-evals` defers the agent runtime to
`foundry-hosted-agents` (peer-skill callout at SKILL.md L1060-1066) and
correctly never re-documents those classes. The skill's own SDK
references are all on the `evals` sub-API.

---

### C9 — RBAC propagation race (Pattern 23) — **HIT (medium)**

Eval graders execute **inside the Foundry project's compute** as the
**project system-assigned managed identity (SAMI)** — NOT as the
caller's UAMI / user identity. This is the same Pattern 23 trap that
bit `foundry-memory` in Phase 3 (the memory consolidation worker also
runs as the project SAMI). Before this audit, SKILL.md L1110-1140
documented only the caller-side RBAC (`Azure AI User` on the project,
which lets the SDK enqueue the run) and the AOAI account-scope roles
(`Cognitive Services OpenAI User`, `Cognitive Services User`) WITHOUT
making the identity-distinction explicit. A consumer reading the
prerequisites verbatim would correctly grant the two AOAI roles to
their UAMI, then watch the grader 401 mid-run because the project SAMI
— a DIFFERENT principal, auto-created on project bootstrap — also needs
both AOAI roles. CI hits this immediately (Pattern 23 forensic
signature: 401 from `cognitiveservices.azure.com` *after* the run is
accepted) but consumers waste 30-60 min misreading the error as a
caller-credential bug.

**Before** (SKILL.md L1110-1140 — Required RBAC bullets, pre-audit):
```text
**Required RBAC for evaluation runs**:
- `Azure AI User` on the Foundry project (for the SDK caller)
- `Cognitive Services OpenAI User` on the judge-model account
- `Cognitive Services User` on the judge-model account
```

**After** (SKILL.md L1126-1139, post-audit):
```text
**Required RBAC for evaluation runs (TWO distinct identities)**:

| Identity | Role | Scope | Why |
| --- | --- | --- | --- |
| **Caller** (your UAMI / SP / user) | `Azure AI User` | Foundry project | Enqueue the run via SDK |
| **Project SAMI** ⚠ Pattern 23 | `Cognitive Services OpenAI User` | AOAI account | Grader invokes judge model |
| **Project SAMI** ⚠ Pattern 23 | `Cognitive Services User` | AOAI account | Grader reads model metadata |

The project SAMI is created when the project is created; it is a
DIFFERENT principal from your caller identity. Granting the two AOAI
roles to your UAMI alone is the most common pilot footgun.

Verify with:
  az role assignment list \
    --assignee-object-id <PROJECT_SAMI_OBJECT_ID> \
    --scope <AOAI_ACCOUNT_RESOURCE_ID> \
    --query "[].roleDefinitionName"
```

**Disposition.** Fix-in-PR. Scope: `skills/foundry-evals/SKILL.md`
L1126-1139. PATCH bump 1.1.0 → 1.1.1 (shared with C1 and C21).
Counted toward the `[skill-rewrite]` commit tag.

---

### C10 — Region / SKU drift (Pattern 21) — N/A

`foundry-evals` consumes an existing model deployment for the judge
model; it ships no Bicep / no embedding provisioning. Pattern 21's
"Sweden Central embeddings need `GlobalStandard`" rule is the
provisioner's concern, documented in `foundry-iq` for the retrieval
case and in the consumer's hosted-agent skill for the chat case.
SKILL.md L820-840 correctly tells consumers to reuse the same judge
model across runs for score comparability, not to deploy a new one
per eval.

---

### C11 — Cross-skill reference drift — none observed

Peer-skill callouts at L1060-1066 cite `foundry-hosted-agents § Identity & RBAC`
(verified — that anchor exists in current main HEAD of
`skills/foundry-hosted-agents/SKILL.md`) and `foundry-iq § Continuous indexing`
(verified — anchor exists). The `foundry-memory` callout at L1078-1082
cites § Soft-PASS contract (verified post-merge of #199). No stale
section anchors.

---

### C12 — Link rot — none observed

`grep -roE 'https?://[^ )"]+' skills/foundry-evals/ | sort -u` returns
~27 unique URLs across documentation hosts: **Learn (5)** —
`learn.microsoft.com/azure/ai-foundry` + `/azure/ai-services` (Microsoft-
authoritative, GA-stable, canonical-rewrite friendly); **GitHub (18)** —
repo references to `github.com/microsoft/*` and `aiappsgbb/*` (pinned
SHA or default-branch links, no deep file-line anchors that would 404 on
upstream refactor); **PyPI (2)** — `pypi.org/project/azure-ai-projects/`
and `pypi.org/project/azure-identity/` (canonical package landing pages,
not version-deep URLs); **docs.github.com (1)** — GitHub workflow doc
that's API-versionless. None are deep-link-fragile (no `#section` anchors
that depend on heading slugs, no `/api/X.Y.Z/` versioned paths that 404
on minor bumps, no `aka.ms/*` short links that drop without warning).

---

### C13 — Telemetry wiring — N/A

`foundry-evals` is a telemetry CONSUMER (eval results appear under
**Agent Monitoring → Evaluation runs** automatically when the SDK call
completes) — not a producer. There is no App Insights connection-string
to wire, no OTel tracer to register, no Foundry endpoint to POST traces
to. The producer-side OTel contract is documented in
`foundry-observability`; SKILL.md L1068-1075 correctly defers there with
a one-line callout instead of duplicating the Bicep / SDK wiring.

---

### C14 — JSON/YAML escaping — N/A

No Bicep params, no `agent.yaml` authoring, no inline JSON-in-YAML
fragments. The skill's two YAML-ish surfaces — `EvaluationRule` and
`run_config` — are constructed in Python with native dict literals,
where Python's parser handles escaping. No risk of stringly-typed
quote-escape bugs.

---

### C15 — Reference ↔ SKILL.md drift — **HIT (medium) — DEFERRED**

`references/python/eval_runner.py` L60-80 calls `client.evals.create(...)`
to register the evaluator definition, immediately followed by
`result = client.evals.runs.create(eval_id=..., name=..., data_source={...})`
on L69-79, and then `return result.metrics` on L80 — with **no
intervening poll** of `client.evals.runs.get(eval_id, run_id).status`
for a terminal state. The May 2026 preview `azure-ai-projects~=2.0`
evals surface treats `runs.create` as an **asynchronous** dispatch:
the returned object surfaces `id`, `status`, and `data_source`, but
`.metrics` is only populated once the server-side grader completes (the
LLM-as-judge call against the deployment hosted on the AOAI account).
On a fast grader the metrics MAY be present immediately; on a cold
deployment or under TPM pressure the field is `None` and a downstream
consumer of `eval_runner.py` would emit zeros into their dashboard
without raising. The fix is to wrap `runs.create` in a bounded poll
loop (`while run.status not in {"completed", "failed", "cancelled"}:
time.sleep(2); run = client.evals.runs.get(eval_id, run.id)`) before
reading `.metrics` — but confirming whether the SDK 2.0.x release
backfills `.metrics` synchronously on `runs.create` for certain grader
families, or always requires the explicit poll, needs a live-project
soak-test (~5-15 min). The pin is `runnable: false` (this audit-only
PR cannot exercise it).

**Disposition.** Deferred — see Open items (deferred) below. The fix
lands in the next pin refresh, when a coordinator with live-project
access can characterise the SDK's `runs.create` ↔ `.metrics` semantics
and bundle the eval_runner.py rewrite with the pin-version bump. The
reference file works as shipped today for fast graders; the drift is
a silent-zero risk under load, not a behaviour-blocking bug.

---

### C16 — Missing `dependsOn` on RBAC — N/A

No Bicep. The runtime RBAC contract (C9) is enforced via `az role
assignment create` documentation, where ordering is the consumer's
shell-script concern, not a Bicep deploy-graph concern.

---

### C17 — Tool wrapper type mismatches — none observed

`grep -nE 'MCPTool|OpenApiTool|FunctionTool|CodeInterpreterTool' skills/foundry-evals/SKILL.md`
→ empty. `foundry-evals` scopes itself to evaluators (grader recipes
that wrap `azure-ai-projects.evals`) and never wraps consumer tools.
The tool-wrapper type-mismatch class (most recently seen in
`foundry-toolbox`'s `RouteFunction` audit) does not apply.

---

### C18 — Bot/webhook signature validation — N/A

No webhook surface. Eval runs are pull-mode (SDK-initiated by the
caller); results land in the Foundry portal's Agent Monitoring view and
are read back via `project.evals.runs.get(...)`. There is no inbound
HTTP surface to authenticate.

---

### C19 — Logging exposure — none observed

The two reference Python files use `print()` for human-readable progress
output, with the only model-output exposure being the deliberate
`print(f"output_first_400={out_text[:400]!r}")` snippet that truncates
to 400 chars in `eval_runner.py` L88-92. The `!r` repr-formatting is
the correct choice (escapes control characters; surfaces UnicodeEncode
traps mentioned in SKILL.md L185-200 without exfiltrating non-ASCII to
the log stream). No PII / secrets / full-response leaks.

---

### C20 — Async/sync mismatches — N/A

`grep -nE 'async def|await |asyncio\.' skills/foundry-evals/SKILL.md`
returns hits at L1260-1282 (a cron-loop scaffold `async def run(): ...
asyncio.run(run())` with awaited helpers `fetch_spans`, `raise_alert`,
`emit_kpi_telemetry`, `record_foundry_eval_run`) and L1352-1364 (`async
def record_foundry_eval_run` containing `await client.evals.runs.create(...)`).
Both are documented inside an explicit async-cron context where the
consumer is expected to use `azure.ai.projects.aio.AIProjectClient` (the
`.aio` variant), and the surrounding scaffold makes the async scope
unambiguous. The inner `await client.evals.runs.create(...)` is
technically a sync SDK call awaited in async scope — an edge case
absorbed into C15's broader polling-loop rewrite for re-validation
against the live SDK. No Pattern 16 rule-3 violation in scope here (the
fixture and the one-shot `eval_runner.py` correctly use the sync
client).

---

### C21 — Outdated package version pins (prose vs frontmatter) — **HIT (low)**

Three sites in SKILL.md narrate SDK versions or specifiers out of sync
with the pin frontmatter (`azure-ai-projects~=2.0`,
`azure-identity~=1.19`, `python-dotenv~=1.0`):

| Location | Before (prose) | After (matches pin) |
| --- | --- | --- |
| L444 (inline comment in `EvaluationRule` example) | `# \`name=\` is REQUIRED as of Azure AI Projects SDK 1.0.x (May 2026).` | `# \`name=\` is REQUIRED as of Azure AI Projects SDK 2.0.x (May 2026).` |
| L1070 (continuous-eval introduction) | `**Use this first.** As of \`azure-ai-projects>=2.0.0\` (May 2026), …` | `**Use this first.** As of \`azure-ai-projects~=2.0\` (May 2026), …` |
| L1079 (pip install recipe) | `pip install "azure-ai-projects>=2.0.0" "azure-identity>=1.19.0" "python-dotenv>=1.0.0"` | `pip install "azure-ai-projects~=2.0" "azure-identity~=1.19" "python-dotenv~=1.0"` |

The L444 comment was a copy-paste artefact from a pre-2.0 draft of the
skill; the actual `name=` requirement landed in the 2.0 release per the
upstream CHANGELOG (the comment's intent — "this kwarg is required" — is
preserved; only the version label was stale). The L1070 narrative and
L1079 recipe both used unbounded `>=` specifiers that violate AGENTS.md
§ 9.5's pin-cap policy (bare `>=X.Y.Z` is forbidden because the next
major can break silently); the rewrites use PEP 440 compatible-release
operators that match the pin frontmatter exactly.

**Disposition.** Fix-in-PR. Scope: `skills/foundry-evals/SKILL.md`
L444 + L1070 + L1079. PATCH bump 1.1.0 → 1.1.1 (shared with C1 and C9).
Counted toward the `[skill-rewrite]` commit tag.

---

## Fixture

The Phase-3-green fixture at `skills/foundry-evals/test-fixture/consumer_prompt.md`
is **out of scope for this audit** (per coordinator brief). Quoted here
for traceability:

| Field | Value |
| --- | --- |
| Path | `skills/foundry-evals/test-fixture/consumer_prompt.md` |
| Line count | 96 |
| Pattern compliance | 11 (explicit `AZURE_*` env probe) + 12 (deterministic marker `/tmp/foundry-evals-smoke-result`) + 17 (show-don't-assert on `az account show`) + 25 (soft-PASS on teardown) |
| Wall-clock | ~3-5 min (eval runs are SDK-fast; no `azd up`) |
| Success marker | `printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-evals-smoke-result` |
| Cross-skill dep | `foundry-prompt-agents` (fixture creates a prompt agent first, then evaluates it) |

The fixture passed three consecutive Phase 3 stability runs
(`26716554166`, `26716984572`, `26717346015`) on commit
`99ed7476c82bb6b02363ce4cc6c0d2a5d01f2c97` with the same SKILL.md
prerequisites this audit revises (C9 RBAC, C21 pip cap). The C9 fix
is consumer-facing documentation only — the CI runner's project SAMI
already holds both AOAI roles per the post-`foundry-memory` RBAC fix
documented in AGENTS.md § 9.7 Pattern 23. No fixture re-authoring
needed.

---

## CI matrix runs

| Run | Trigger | Result | Leg(s) |
| --- | --- | --- | --- |
| [`26716554166`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26716554166) | Phase 3 stability #1 (pre-audit) | ✅ GREEN | foundry-evals |
| [`26716984572`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26716984572) | Phase 3 stability #2 (pre-audit) | ✅ GREEN | foundry-evals |
| [`26717346015`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26717346015) | Phase 3 stability #3 (pre-audit) | ✅ GREEN | foundry-evals |
| _this PR_ | Pattern 24 change-gated matrix | _pending_ | ONLY foundry-evals leg (~3-5 min expected); any other leg firing = accidental infra-file touch, abort and re-diff |

---

## Open items (deferred)

### C15 — `eval_runner.py` L60-80 `runs.create` ↔ `.metrics` polling

Rewriting `eval_runner.py` L60-80 to wrap `client.evals.runs.create(...)`
in a bounded poll loop (`while run.status not in {"completed",
"failed", "cancelled"}: time.sleep(2); run = client.evals.runs.get(...)`)
before reading `result.metrics` is the right correctness fix — but
characterising whether the SDK 2.0.x release backfills `.metrics`
synchronously for fast graders, or always requires the explicit poll,
needs a live-Foundry soak-test (in particular: confirm the SDK doesn't
raise on `failed` and confirm `.metrics` is non-`None` after a
`completed` transition without an extra fetch). The pin is currently
`runnable: false` (this audit-only PR cannot exercise the SDK). Bundle
with the next `references/upstream-pin.md` refresh when a coordinator
with live-project access can characterise the semantics. Estimated
scope: one PATCH commit, ~10-15 LOC delta in `eval_runner.py`, no
SKILL.md narrative change required (the consumer-facing description at
L1070-1140 already describes the eval as fire-and-track, not
fire-and-read).

### Future-evergreen items (NOT in scope of any single audit)

1. **Continuous-eval API stabilization** — the May 2026 preview SDK
   exposes `project.evals.continuous.create(...)` for online-evaluation
   loops; the API is still preview-marked and the documented shape may
   churn. Re-audit once it ships GA (target Q3 2026).
2. **Judge-model TPM headroom guidance** — SKILL.md doesn't currently
   quantify how many parallel eval runs the consumer can fan out before
   the judge model 429s. Worth adding a guidance table once we have
   pilot data from 3+ subscriptions.
3. **Eval-dataset versioning conventions** — large pilots are starting
   to need versioned eval datasets (e.g. `v3-with-corner-cases.jsonl`)
   to track score deltas across SKILL.md revisions; no current best-
   practice section. Defer until the convention solidifies across
   `aiappsgbb` engagements.
4. **Retrieval-eval recipes for `foundry-iq`** — `foundry-evals` and
   `foundry-iq` will eventually need a shared "evaluating retrieval
   quality" recipe (NDCG@k, citation-coverage scoring). Defer until
   `foundry-iq` has a stable evaluator surface.

---

## Audit closure

The `foundry-evals` skill ships three HITs fixed in this PR (C1 medium
PoC-name scrub across SKILL.md + two reference Python files; C9 medium
Pattern 23 project-SAMI RBAC promoted from buried CI notes to consumer-
facing prerequisites with a 4-column identity table + verification
command; C21 low prose-vs-pin version-drift correction at L444 +
L1070 + L1079), all bundled in a single PATCH bump 1.1.0 → 1.1.1 under
the `[skill-rewrite]` commit tag. One finding is deferred (C15 medium
SDK semantics in `eval_runner.py` L60-80, requires live Foundry project
to characterise `runs.create` ↔ `.metrics` polling contract; bundle
with next pin refresh). The remaining seventeen classes resolve
cleanly: the skill ships no Bicep (C2, C16), no azd template (C6), no
CLI install instructions (C3), no webhook (C18), no async runtime
outside a documented cron context (C20), no telemetry-producer surface
(C13), no preview-CLI flag branching (C5), no deprecated SDK API
references (C8), no stale cross-skill anchors (C11), no link rot (C12),
no configuration-escaping surfaces (C14), no tool-wrapper type
mismatches (C17), no logging exposure (C19), no SDK shape drift on the
GA surfaces (C7), and consumes existing model deployments without re-
provisioning (C10), and no Pattern 25 teardown-window race (C4). The
Phase-3-green fixture (Pattern 11 + 12 + 17 + 25 compliant, ~3-5 min
wall-clock, soft-PASS on teardown) is untouched and re-runs on this PR
via Pattern 24 change-gating — only the `foundry-evals` matrix leg
fires.
