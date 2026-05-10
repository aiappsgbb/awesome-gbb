# SpecKit Template

> Adapted from ghcpsdk-process-builder for general-purpose business process specification.
> No runtime or SDK specifics — pure business + technical spec.

```markdown
# SpecKit: [Process Name]

> Generated: [date]
> Status: draft | review | approved

## 1. Process Overview

**Name**: [Full process name]
**Domain**: [Industry or business domain]
**Description**: [2-3 sentences describing the process end-to-end]
**Target Persona**: [Who will see the demo — CIO, CFO, COO, CDO, CISO, Developer, or mixed]

### Goals
- [Primary goal — what outcome does this deliver?]
- [Secondary goals]

### Scope
- **In scope**: [What's included]
- **Out of scope**: [What's excluded]

### Participants
| Role | Type | Description |
|------|------|-------------|
| | human / system / agent | |

> Type `human` = end user or stakeholder who interacts with the system
> Type `system` = external system the agent integrates with (SAP, CRM, DB, API, etc.)
> Type `agent` = the AI agent or one of its specialist skills

---

## 2. Process Flow

### Steps

#### Step 1: [Name]
- **Actor**: [Who performs this — agent, human, or system]
- **Input**: [What's needed to start this step]
- **Action**: [What happens]
- **Output**: [What's produced]
- **Decision**: [Branch conditions — if X → Step Y, if Z → Step W]

#### Step 2: [Name]
- **Actor**:
- **Input**:
- **Action**:
- **Output**:

> Add as many steps as needed. Keep each step atomic — one actor, one action.
> Decision branches should reference step numbers for clarity.

---

## 3. Business Rules

Number all rules BR-XXX. These drive evaluation scenarios and skill logic.

### BR-001: [Rule Name]
- **Condition**: [When does this rule apply?]
- **Action**: [What must happen?]
- **Exception**: [Any exceptions to the rule?]
- **KPI** (optional but recommended — see § 9 Business KPIs): [Name of the metric this rule influences, e.g. `auto_decline_rate`]

### BR-002: [Rule Name]
- **Condition**:
- **Action**:
- **Exception**:
- **KPI**:

> Business rules are the backbone of the spec. Every skill procedure and
> evaluation scenario should trace back to one or more BR-XXX rules.
>
> **Continuous evaluation contract:** every BR-XXX should map to at least one
> measurable KPI in § 9. The KPI is what the `foundry-evals` continuous loop
> watches week-over-week — `eval_dataset.jsonl` (one-shot) only proves the
> agent works in lab; KPIs prove it keeps working in production.

---

## 4. Data Models

Define the entities the process works with. These become the schema for mock data.

### [Entity Name]
| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| | string / int / float / bool / enum / datetime | yes/no | constraints | |

- **System of record**: [Which system from § 5 owns this entity — or "internal" if agent-managed]

> Include all entities: inputs, outputs, intermediate state, reference data.
> For enum fields, list valid values in the Validation column.
> The `System of record` links entities to integrations — entities backed by
> **mock** systems in § 5 will get sample data generated in `specs/sample-data/`.

---

## 5. System Integrations

External systems the process needs to interact with.

### [System Name]
- **Type**: database / API / SaaS / file-store / message-queue
- **Direction**: read / write / read-write
- **Data exchanged**: [What entities flow in/out]
- **Auth**: [Auth type — OAuth, API key, managed identity, none]
- **Availability**: available / auth-required / internal-only / **mock** ← for systems you can't access

> For systems marked **mock**: sample data will be generated in `specs/sample-data/`
> matching the data models above. When the real system becomes available, replace
> mock data with an MCP server or API connection.

---

## 5b. External Systems & Mocks (MCP contract)

> **INPUT CONTRACT for `foundry-mcp-aca`.** This section drives the FastMCP server
> generation. Every tool the agent calls against an external system must be declared
> here with its endpoint shape, response semantics, and reset behavior.

For each system from § 5 that the agent will reach **via an MCP tool** (mock or real),
specify:

### [System Name]
- **MCP server**: `mock` (FastMCP backed by sample data) | `real` (deployed MCP) | `cosmos-toolkit` (10 built-in tools) | `playwright` (browser automation)
- **Endpoint shape**:
  - Style: `request-response` | `streaming` (SSE) | `webhook` (push from system)
  - Pagination: `none` | `cursor` | `offset-limit` | `keyset`
  - Idempotency key field: `[field name or "none"]`
- **Tools exposed** (one row per MCP tool — match § 6 contracts):
  | Tool name | Read/Write | Latency budget | Notes |
  |-----------|-----------|----------------|-------|
  | `get_customer_by_id` | R | <100ms | Backed by `customers.json` |
- **Mock data scale**: rows per entity (e.g. `customers: 50, orders: 200, ledger: 1000`)
- **Reset semantics**: `idempotent` (re-seed wipes + repopulates) | `append-only` (history preserved across runs) | `none` (read-only)
- **Demo state machine** (if any): list discrete demo states the data should cycle through (e.g. `pristine → mid-incident → resolved`) so the same seed file can drive a story.
- **Real-system swap notes**: what changes when the real backend appears (URL, auth header, schema differences).

> **Why a separate section?** § 5 is the business-level inventory ("we talk to SAP").
> § 5b is the developer-level contract ("here's exactly what the MCP server returns,
> at what shape, and how to reset it for a clean demo run"). The first is for stakeholders;
> the second is what `foundry-mcp-aca` reads to generate code.

---

## 6. Tool Contracts

Define the tools the agent will use. These are abstract — not bound to any specific runtime.

### [tool_name]
- **Description**: [What does this tool do?]
- **Used by**: [Which skill/agent uses this]
- **Inputs**:
  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | | | | |
- **Output Schema**: `{ field: type, ... }`
- **Side Effects**: [Any state changes, external calls]
- **Error Cases**: [What can go wrong and how to handle it]
- **Backed by**: [System integration name from § 5, or "internal logic"]

---

## 7. Knowledge Sources

Reference documents, policies, or data the agent needs for reasoning.

### [Source Name]
- **Type**: document / database / search-index / API
- **Content**: [What information does it contain?]
- **Format**: PDF / DOCX / HTML / JSON / structured DB
- **Update Frequency**: [How often does it change?]
- **Backing service**: `foundry-iq` (Azure AI Search Knowledge Agent — agentic retrieval, query planning, citations) | `mcp-search` (live API search) | `inline-context` (small enough to paste into instructions)
- **Reasoning effort** (for foundry-iq): `minimal` | `low` | `medium` — drives Knowledge Agent config
- **Citation requirement**: `mandatory` (every answer must cite ≥1 source) | `recommended` | `optional`

> **Static / semi-static knowledge → `foundry-iq`.** Policies, regulations,
> product docs, brand guidelines, runbooks, technical specs — anything that
> changes monthly-or-slower and benefits from query planning + citations
> belongs in a Foundry IQ Knowledge Base. This is the **default knowledge
> retrieval pattern** for every threadlight process — even processes that
> primarily query transactional data should ship with a Foundry IQ index for
> their domain policies. See the `foundry-iq` skill for index design,
> document chunking, and Knowledge Agent reasoning levels.

---

## 7b. AI Services & Model Selection

> **INPUT CONTRACT for `foundry-doc-vision-speech` and the model declarations in
> `azure.yaml` `config.deployments`.** Every model-backed capability the agent uses
> must be declared here so deployment can provision the right model SKU and capacity.

For each AI capability the agent needs:

### [Capability Name]
- **Capability type**: `chat-reasoning` | `vision-structured-extract` | `vision-unstructured-reason` | `document-extract` | `speech-to-text` | `text-to-speech` | `embeddings`
- **Service**: `Azure OpenAI` (chat / vision / embeddings) | `Document Intelligence v4` (forms, IDs, invoices) | `Azure Speech` (STT / TTS) | `Azure Vision` (OCR, image analysis)
- **Model + version** (current as of 2026-05):
  | Use case | Recommended model | Notes |
  |----------|-------------------|-------|
  | Default chat reasoning | `gpt-5.4-mini` (2026-03-17) | 400K context, vision-capable, best cost/quality |
  | High-stakes reasoning + vision | `gpt-5.4` (2026-03-05) | 1M context, premium |
  | Premium reasoning + vision | `gpt-5.4-pro` (2026-03-05) | When vision feeds multi-step reasoning |
  | Bulk / cheap vision | `gpt-5.4-nano` (2026-03-17) | Returns triage, photo screening |
  | Code-related multimodal | `gpt-5.3-codex` (2026-02-24) | Diagrams → code |
  | Structured doc extract (passport, invoice, ID) | Document Intelligence v4 prebuilt | Use prebuilt when possible |
  | Custom doc extract | Document Intelligence v4 custom model | Train when prebuilt doesn't fit |
  | Voice intake | Azure Speech-to-Text (real-time) | n/a |
- **Capacity (TPM)**: e.g. `120K` for default, `300K+` for high-volume
- **Reasoning effort** (for capable models): `minimal` | `low` | `medium` | `high` (default `medium`)

> **Do NOT use `GPT-4o` or `GPT-4o Vision`** — both are legacy as of May 2026.
> The `gpt-5.4` family supersedes them in every dimension (context, latency, vision
> quality, cost). If a SPEC carries forward a `GPT-4o` reference from an older
> template, that's a bug — sweep to `gpt-5.4-mini` (default) or pick from the
> table above based on the capability profile.

---

## 8. Human Interaction Points

Where humans are involved — approvals, escalations, input requests, feedback loops.

### [Interaction Name]
- **Trigger**: [When does this happen?]
- **Actor**: [Which human role?]
- **Channel**: [How — Teams, email, portal, chat?]
- **Data Presented**: [What the human sees]
- **Options**: [What actions can the human take?]
- **Timeout/SLA**: [How long before escalation?]
- **Action gate** (use the canonical taxonomy below): `approve` | `edit-and-approve` | `reject` | `escalate` | `signoff` | `audit-view` | `request-info`
  | Gate | Semantics | Typical UX |
  |------|-----------|------------|
  | `approve` | Yes/no on a proposed action | Adaptive Card with two buttons |
  | `edit-and-approve` | Human can amend the agent's proposal before approving | Editable form fields + approve button |
  | `reject` | Human refuses the action with a reason | Reason picker + free-text |
  | `escalate` | Human routes the case to a higher authority | Role/queue picker |
  | `signoff` | Human attests they reviewed (no veto) | Single confirm button + signature trail |
  | `audit-view` | Read-only inspection (no action taken) | Detail pane with audit log |
  | `request-info` | Human asks the customer/external party for more data | Templated message composer |
- **Linked business rules**: [BR-XXX list] — which rules require this gate

> **INPUT CONTRACT for `threadlight-hitl-patterns`.** The action gate
> drives Adaptive Card generation and bot UX. The linked BR-XXX list drives
> the audit trail wiring.

---

## 8b. Human Interaction (Workspace UX)

> **INPUT CONTRACT for `threadlight-workspace-ui`.** This section describes the
> case-management surface that humans use day-to-day — independent of the chat/Teams
> approval gates above. Skip this section if humans only interact via approval cards.

- **Workspace shape**: `case-list` (queue of items, filter/sort, click into detail) | `inbox` (chronological stream) | `dashboard` (KPI tiles + drill-down) | `console` (live ops with action toolbar) | `kanban` (stages with drag) | `map` (geo) | `none`
- **Primary filters**: list (e.g. status, owner, age, risk-band)
- **Detail pane sections** (top to bottom): list (e.g. summary card, agent reasoning trace, tool call log, decision history, action toolbar, audit viewer)
- **Action toolbar** — gates from § 8 that appear here (subset)
- **Audit viewer**: `inline` (always visible) | `drawer` (open on demand) | `none`
- **Bulk operations**: list (e.g. assign-to-me, batch-reject) — or `none`

---

## 9. Success Criteria

### Functional
- [ ] [Expected behavior — tied to business rules]

### Performance
- [Throughput, latency, SLA targets]

### Quality
- [Accuracy, error rates, coverage targets]

### Evaluation Scenarios

| ID | Scenario | Input | Expected Output | Business Rules | Category |
|----|----------|-------|-----------------|----------------|----------|
| S-001 | | | | BR-XXX | happy-path / edge-case / error / approval |

### Business KPIs (BR → KPI mapping)

> **INPUT CONTRACT for `foundry-evals` continuous-loop.** Every BR-XXX should
> map to at least one **measurable KPI** that can be computed from agent traces
> (Application Insights). This is what the continuous evaluation dashboard
> watches week-over-week — not just the binary scenario pass/fail.
>
> **Use the industry-native KPI vocabulary** from `references/data-realism/{industry}.md` § "<industry>-native KPIs". Generic names like `auto_decline_rate` should be the exception — most processes have a domain-recognized KPI an SME will accept on first read.

**Industry exemplars** (replace these with KPIs from the relevant industry file):

| Industry | Example KPI (good) | Example KPI (bad) |
|----------|--------------------|-------------------|
| FSI / AML | `alert_to_case_conversion_rate`, `l1_false_positive_rate`, `sar_filing_cycle_days_p50` | `decline_rate` |
| FSI / KYC | `edd_throughput_cases_per_analyst_per_day`, `first_touch_resolution_pct` | `auto_decline_rate` |
| Mfg / Plant | `oee_pct`, `first_pass_yield_pct`, `dpmo`, `capa_closure_cycle_days_p50` | `quality_score` |
| Mfg / Supply | `otif_pct_inbound`, `single_source_pct_of_spend` | `supply_score` |
| Retail / PIM | `pim_completeness_pct`, `time_to_publish_hours_p95` | `enrichment_rate` |
| Retail / Returns | `return_cycle_time_business_days_p50`, `restock_a_pct` | `return_resolution_rate` |
| Telco / Order | `order_fallout_rate_pct`, `fallout_mttr_hours_p50` | `order_success_rate` |
| Telco / Network | `mttr_hours_p1`, `first_call_resolution_pct` | `incident_resolution_rate` |

| BR | KPI Name | Formula (computable from traces) | Target | Alert threshold |
|----|----------|-----------------------------------|--------|-----------------|
| BR-001 | `<industry-native-kpi>` | `count(decisions where outcome=...) / count(decisions)` | (industry benchmark from data-realism file) | (alert when off-baseline) |
| BR-007 | `policy_citation_rate` | `count(answers where citations≥1) / count(answers)` | 100% | <95% |
| BR-012 | `human_escalation_rate` | `count(escalated) / count(decisions)` | (industry-realistic band) | (off-baseline) |

> Trace fields the agent must emit (declared in the skills' procedures):
> `decision.outcome`, `decision.business_rules_fired`, `answer.citations[]`,
> `escalation.reason`, etc. The continuous-loop ACA job pulls these from
> App Insights, computes KPIs, and writes back to a workbook + raises
> alerts on threshold breaches.

---

## 10. Trigger & Run Model

How and when the process executes.

- **Trigger**: [on-demand / scheduled / event-driven / continuous]
- **Schedule**: [If scheduled — cron expression or cadence]
- **Event source**: [If event-driven — what triggers it]
- **Expected volume**: [Requests per hour/day]
- **Latency/SLA**: [Max acceptable response time]
- **Concurrency**: [Parallel execution expected?]

### 10b. Triggers (Receiver contract)

> **INPUT CONTRACT for `threadlight-event-triggers`.** For event-driven and
> scheduled processes, declare the receiver shape so the right ACA job /
> Function / Event Grid sub / Service Bus consumer can be scaffolded.

| Trigger source | Receiver type | Idempotency key | Dedup window | Dead-letter rule |
|----------------|---------------|-----------------|--------------|------------------|
| Cron `0 6 * * *` | ACA Job | run timestamp | n/a | retry 3× then alert |
| Event Grid topic `orders/created` | Function (HTTP receiver) | `event.id` | 5 min | DLQ to Storage Queue |
| Service Bus queue `claims-incoming` | ACA consumer (Service Bus binding) | `MessageId` | 24h | move to `claims-poison` after 5 attempts |
| Webhook from external system | ACA Job (HTTP-triggered) | `X-Request-Id` header | 10 min | return 5xx to trigger sender retry |

> **Note for pilots:** event-driven triggers are **worth declaring** but **not mandatory
> to build for the first pilot** — the customer often integrates with their own event
> bus on their own terms. Ship the contract; let the integration follow.

---

## 11. Security, Compliance & Governance

- **PII involved**: yes / no — [if yes, what fields, with citation to the
  governing regime (HIPAA Safe Harbor § 164.514, GDPR Art 9, CPNI 47 CFR
  Part 64 Subpart U, PCI-DSS v4.0, etc.)]
- **Auth model**: [How users/systems authenticate — keyless / managed
  identity end-to-end is the default; any deviation is a flag]
- **Data residency**: [Customer expectation — `EU`, `US`, `UK`, `India`,
  `multi-region`. Names the Azure regions chosen. GDPR / PIPL / DPDPA
  compliance implications.]
- **Data retention**: [How long to keep agent traces, case data, audit
  events; deletion policy; right-to-be-forgotten path]
- **Regulatory**: [GDPR, HIPAA, SOX, FFIEC, MiFID II, PCI-DSS, ISO 27001,
  SOC 2 Type II, IATF 16949, GxP, ITAR/EAR, industry-specific — or
  `none` for internal automation only]
- **Access control**: [RBAC matrix — who can run this, who can see
  results. Reference Easy Auth / Entra ID groups by name.]
- **Audit requirements**: [What must be logged for auditability —
  decision rationale, citations, model+prompt version, human-overrides,
  upstream/downstream data lineage. Default: 7-year retention for
  regulated; 90-day for unregulated.]
- **Responsible AI posture**: [Risk tier per Microsoft RAI Standard v2
  (`limited`, `general`, `consequential`, `restricted`); applicable RAI
  goals — fairness, reliability, privacy, transparency, accountability;
  GDPR Art 22 (automated-decision rights) implications if applicable]
- **Model governance**: [Model + prompt version pinning; promotion gate
  from dev→prod (eval pass threshold); rollback procedure; drift
  monitoring cadence]
- **Customer onboarding RACI**: [Who on the customer side is **R**esponsible /
  **A**ccountable / **C**onsulted / **I**nformed for this process —
  business sponsor, IT owner, security/compliance signoff, legal/privacy,
  ops handoff. Demos that don't name a sponsor don't fund.]
- **ROI hypothesis**: [Quantifiable lever — `FTE-hours × loaded-rate`,
  `revenue-at-risk × probability`, `regulator-fine-avoided`, `cycle-time-
  compression × volume`. Cite the formula explicitly so the customer can
  replace the inputs with their own numbers.]
- **Change management**: [Org-side adoption plan — who trains the L1/L2
  analysts, how the agent's recommendations enter the existing workflow
  (parallel-run period? shadow-mode? full cutover?), what KPIs prove
  adoption stuck.]

### 11b. AI Governance Hub Posture (opt-in spoke)

> **INPUT CONTRACT for the optional governance-hub spoke handoff in
> `threadlight-deploy`.** Every regulated process should declare whether
> it needs to land as a spoke against an AI Governance Hub (e.g. an
> internal central LLM gateway / policy plane). The deploy flow generates
> the standalone agent first; if `governance_hub.required` is true,
> deploy then runs the spoke-onboarding handoff as a separate, opt-in
> step.

- **Governance hub spoke required**: `yes` (FSI, healthcare, regulated supplier risk) | `no` (PoC, internal automation)
- **Reason**: [Why — regulator audit, central LLM gateway policy, Key Vault federation, RAI policy enforcement, etc.]
- **Spoke artifacts needed**: list (e.g. `Access Contract`, `APIM connection`, `Key Vault secret federation`, `Product Policy`, `JWT auth`, `network whitelist`)
- **Tenant strategy**: `shared demo tenant` (default) | `dedicated customer tenant` | `customer-deferred`

---

## 11c. Tech Stack (Module selectors)

> **INPUT CONTRACT for `azd-patterns` Bicep module library and the
> composer in `threadlight-deploy`.** This selector vocabulary is the
> **canonical source of truth** — both the `azd-patterns` module library
> and the `threadlight-deploy` Phase-6 composer must read from this list
> verbatim. If you change a selector name, change it here first.
>
> Declare which infra modules the process needs. Don't list modules the
> process doesn't need (every selected module costs money).

| Module | Selected? | Purpose in this process |
|--------|-----------|-------------------------|
| `cosmos-db` | yes/no | Persistent case state, audit log, agent memory (no for stateless single-call agents) |
| `ai-search` | yes/no | Foundry IQ Knowledge Base backing |
| `doc-intel` | yes/no | Structured document extraction (passport, invoice, ID — when prebuilt model fits) |
| `azure-vision` | yes/no | OCR / image analysis (when not using GPT vision) |
| `azure-speech` | yes/no | Voice intake / TTS responses |
| `event-grid` | yes/no | Pub/sub for trigger events |
| `service-bus` | yes/no | Reliable queueing for case workflow |
| `storage-blob` | yes/no | Document upload, large artifacts, dataset hosting |
| `app-insights` | yes (default) | Telemetry — required for continuous evals |
| `aca-job` | yes/no | Scheduled / event-triggered batch work |
| `aca-mcp` | yes/no | Custom MCP server (mock or real) |
| `aca-bot` | yes/no | Teams bot |
| `foundry-iq-index` | yes/no | Pre-provisioned Knowledge Base + chunked corpus |

**Always-created** (not selectable): shared **UAMI** (managed identity),
the **Foundry project** + agent definition, the **ACR** for container
images.

**Implications** (the composer enforces these — declare them so SPEC
review can sanity-check):
- Selecting `aca-bot` implies `aca-mcp` (bot needs MCP for case lookups)
- Selecting `event-grid` or `service-bus` implies `aca-job` (you need a
  receiver)
- Selecting `foundry-iq-index` implies `ai-search` and `storage-blob`
- Selecting `azure-speech` with custom voice / custom model implies
  `azure-speech-custom-subdomain` (**IRREVERSIBLE** flag — the deploy
  script must surface a `--confirm-irreversible` confirmation)

**Keyless by mandate.** `key-vault` is **not** in the always-created or
default-selected list. Threadlight pilots use managed identity end-to-end
per the keyless-mandate; add Key Vault only when the process integrates
with a customer-side service that demands a literal API key (and document
that integration explicitly in § 5).

---

## 11d. Demo Data (Realism rules)

> **INPUT CONTRACT for `threadlight-demo-data-factory`.** Sample data shape
> beyond the basic schema in § 4.

- **Per-entity volume**: e.g. `customers: 50, orders: 200, alerts: 1000`
- **Distribution**: realistic skew (e.g. `80% low-risk / 15% medium / 5% high`)
- **Golden cases** (named, hand-curated for the demo script): e.g. `kyc-cardinal-aerospace-holdings` (premium corporate onboarding, edge-case UBO chain), `fault-pinewood-gnb-overload-2026-04-15` (cascading failure for the dashboard demo). Naming **must** follow the two-token-shift rule from `references/data-realism/README.md` — no `acme-*` or `contoso-*`.
- **Reset semantics**: `idempotent` | `append-only` | `none` (see § 5b)
- **Realism rules** (industry-specific — see `references/data-realism/{industry}.md`):
  - PII: [allowed / synthetic-only / none]
  - Vendor / brand names: [synonym-shifted / fully fictional]
  - Regulatory identifiers (SSN, IBAN, etc.): [valid-format-fake / pattern-only]
  - Geographic distribution: [single-country / multi-region / global]

---

## 12. Assumptions & Open Questions

### Assumptions
- [Assumption 1 — something taken as given]
- [Assumption 2]

### Open Questions
- [Question 1 — needs stakeholder input]
- [Question 2]

### Dependencies
- [Dependency 1 — external system, team, or timeline]
- [Dependency 2]
```
