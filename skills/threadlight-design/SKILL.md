---
name: threadlight-design
description: >
  Spec out a business process or customer use case for an enterprise pilot, then
  generate agent architecture (AGENTS.md + Skills) — a durable SpecKit specification
  first (process flow, business rules, data models, tool contracts, mock data,
  KPIs, governance), then implementation artifacts derived from the spec. Targets
  named LOB processes in regulated industries (FSI, Mfg, Retail, Telco, Healthcare,
  Utilities) where a customer SME will judge the SPEC on industry realism before
  the demo even runs.
  USE FOR: design a process, spec out a use case, create agent architecture, automate
  a regulated workflow, threadlight design, skill factory, business process
  specification, speckit, define a customer scenario, mock backend systems,
  seller prep guide, demo script, demo prompts.
  DO NOT USE FOR: running existing skills, executing code, deploying (use threadlight-deploy),
  general Q&A, internal Microsoft tooling automation, generic chatbot prototyping.
metadata:
  version: "1.5.1"
---

# Threadlight Design

Turn a business process or customer use case into a **durable specification** (SpecKit)
and then derive **AGENTS.md + Skills** from it — ready for a credible enterprise pilot
that holds up in front of an industry SME.

## When to Use

Invoke this skill when the user wants to:
- Spec out a business process or customer scenario (any regulated LOB domain)
- Design agent architecture for a workflow that will face a CIO / CCO / COO / CDO
- Create a structured skill folder with a formal, audit-ready specification
- Mock backend systems they can't access yet (SAP, CRM, core banking, OSS/BSS)
- Turn vague requirements into a concrete, reviewable spec with cited industry data

## Using this skill in Microsoft Copilot Cowork

This skill is designed for two personas:

- **Sellers (non-technical) — usually in Microsoft Copilot Cowork.** Use Cowork to
  tailor-craft a use-case pitch with the customer's named pain, sourced industry
  stats, and a customer-facing `specs/demo-deck.html` you can screen-share on the
  next call. **Fast-PoC mode** is the right default in Cowork — the skill asks
  2–3 essential questions, assumes sensible defaults, and produces everything in
  one pass. You don't need to be a developer to drive this.
- **Solution Engineers (technical) — usually in GitHub Copilot CLI / Claude
  Code.** Use **Full mode** when the design will face a customer SME for
  industry-realism review, or when the design is a prelude to a workshop deploy.
  After the spec is committed, hand off to `threadlight-local-test` for fast
  inner-loop iteration or directly to `threadlight-deploy` for the customer
  sandbox.

> [!TIP]
> **Cowork-specific tips:** keep the customer's industry vocabulary inline (don't
> abstract to generic "the customer"); attach the generated `specs/demo-deck.html`
> directly to the conversation so the customer can react to the visual; if the
> customer wants to see the agent run live, ask the SE to invoke
> `threadlight-local-test` and screen-share back into Cowork.

## Workflow Overview

```
Clarify → Discover → SpecKit (CHECKPOINT — stop/resume here)
                                    ↓
                        Agents.md + Skills (derived from spec)
```

**Two modes:**

| Mode | When | Flow |
|------|------|------|
| **Full** | Production-bound work, stakeholder review needed | Full discovery → checkpoint → review → Phase B |
| **Fast-PoC** | Demos, rapid prototyping, customer-facing PoCs | Essential questions → assume defaults → generate everything in one pass |

To activate fast-PoC mode, the user says "quick PoC", "fast demo", or similar.
The skill can also suggest it when the brief is short or vague.

### Fast-PoC Minimum Baseline

Every PoC, regardless of mode, MUST have:
- ✅ **Keyless auth** (`DefaultAzureCredential`) — no API keys
- ✅ **At least one MCP server** (mock or real) — agent must have callable tools
- ✅ **Mock MCP server** for inaccessible systems — FastMCP backed by sample data, customer swaps endpoint later
- ✅ **SpecKit spec** with assumptions documented in § 12
- ✅ **AGENTS.md + skills** derived from spec
- ✅ **Deployable scaffold** (`azd up` ready)
- ✅ **Eval dataset** from spec § 9 scenarios — so the demo can be scored
- ✅ **`specs/demo-deck.html`** — cinematic talk deck for the live customer moment (always — primary customer-facing artifact; **see Step 6 § 7**). Skip ONLY when spec § 12 assumptions explicitly flag `internal-no-demo: true`. Replaces the legacy `overview.html` — see migration note in `references/demo-deck-template.md`.
- ✅ **`specs/experience.html`** — bespoke cinematic customer journey (**optional — on request**; **see Step 6 § 8**). Generate when the user asks for a "cinematic", "experience", or "journey", or when spec § 12 sets `experience: true`. Skip otherwise.
- ✅ **`tests/killer-prompts.md`** — 5–10 ranked wow-prompts wired into `STARTER_{1,2,3}_TITLE/PROMPT` env vars (see Step 6 § 11). Mandatory under the same condition as the deck.
- ✅ **`specs/demo-rehearsal.md`** — beat-by-beat run-of-show (T-24h / T-15min / T-5min / T-0) with backup paths (see Step 6 § 12). Mandatory under the same condition as the deck.

---

### Runtime capability probe (run before Phase A)

Before starting discovery, probe what the runtime can actually do. Some
runtimes (Cowork sandbox, locked-down Cloud Shell images, hardened
corporate Codespaces) lack browser automation or media tooling — finding
out at T-0 of a live demo is the worst failure mode. **Probe once at
session start**; record the result in `specs/SPEC.md § 12` so downstream
skills degrade gracefully instead of crashing.

Run these probes from your active shell:

| Capability | Probe | Used by | If unavailable |
|---|---|---|---|
| `playwright` (browser drive) | `python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch().close(); p.stop()" && echo OK` | Step 8 visual validation; `@playwright/mcp` MCP tools; `auto-demo-producer` recording phase | Visual validation drops to **manual** ("open `specs/demo-deck.html` at 1440×900, advance through every slide"); document the manual checklist in `tests/demo-rehearsal.md`. Drop `@playwright/mcp` from `mcp-config.json`. Disable `auto-demo-producer`. |
| `ffmpeg` (media assembly) | `command -v ffmpeg && ffmpeg -version \| head -1` | `auto-demo-producer` (mandatory); any skill that stitches narration + screen recording | `auto-demo-producer` cannot run — note "record manually via OBS / Loom / Teams meeting recording" in `specs/demo-rehearsal.md`. |
| `node` + `npx` | `command -v node && command -v npx && node --version` | `@playwright/mcp`, any Node-based MCP installer, `npx -y` MCP shorthand | Drop Node-based MCP servers from `mcp-config.json`; prefer Python-based equivalents (e.g. `fastmcp` over `@playwright/mcp` if web scraping is in scope). |
| `uv` (Astral) | `command -v uv && uv --version` | `threadlight-local-test` Pattern 0 bootstrap; `threadlight-deploy` `container.py` prebuilds | Fall back to `pip` + `python -m venv` (slower); local-test Quickstart still works, just adds ~30 s to bootstrap. |
| `docker` + daemon | `docker info > /dev/null 2>&1 && echo OK` | `threadlight-deploy` Phase 6 image build; ACR `az acr build` is a remote fallback when this fails | If daemon absent (Cowork, some CI runners), `threadlight-deploy` MUST use `az acr build` (remote build); skip any local-image smoke step. |

Then write the result into `specs/SPEC.md § 12 assumptions`:

```yaml
runtime:
  name: cowork                    # cowork | copilot-cli | cursor | codespace | local-mac | local-windows | local-linux
  playwright_available: false     # browser-based visual checks + @playwright/mcp
  ffmpeg_available: false         # auto-demo-producer video assembly
  node_available: true
  uv_available: true
  docker_available: false         # if false, deploy must use az acr build
```

**Known-bad combinations:**

| Runtime | Typical posture | Implication |
|---|---|---|
| **Cowork sandbox** | `python`+`pip`+`node`+`npx` ✅; `ffmpeg` ❌; `playwright` Chromium launch ❌ (sandbox blocks); `docker` ❌; `uv` ⚠️ (only if pre-installed) | Use **manual** visual validation; skip `auto-demo-producer`; use `az acr build` for any container; prefer Python MCP servers |
| **Azure Cloud Shell** | `az`/`azd` ✅; `python` ✅; `node` ✅; `docker` ❌; `playwright` ⚠️ (works for HTML inspection, may fail for full-page screenshots) | Use `az acr build`; visual validation is half-OK (DOM inspection works, screenshots are flaky) |
| **GitHub Codespaces (default image)** | Almost everything ✅; `playwright` install needs `playwright install chromium` first | Run `npx playwright install chromium` once at session start; otherwise full capability |
| **Local laptop (Mac/Win/Linux)** | Full capability when the contributor has installed the tools | Probe is still mandatory — the contributor may not have `ffmpeg`/`playwright`/`docker` installed |

**Downstream contract.** Every other skill in the chain reads
`SPEC § 12 → runtime.*` and either runs the full path or its
documented manual fallback. **No skill silently skips a step it
can't run** — it either degrades to a documented manual flow or
errors loudly with a pointer back to this probe.

---

## Phase A: Discovery → SpecKit

### Step 1: Clarify Purpose

**Goal**: Understand what the user wants to build. Be helpful, not gatekeeping.

Ask the user:

> What process or use case would you like to design? Give me a brief description
> of what it does, who's involved, and what outcome you expect.

Guidance:
- Accept anything — customer service flows, document processing, backend automation,
  content research, monitoring, reporting, internal ops, or anything else
- Help the user articulate their need if they start vague — ask clarifying follow-ups
- It's fine to be broad at this stage — discovery will sharpen scope

Capture:
- **Process name** (suggest one if user doesn't provide)
- **One-line description**
- **Domain** (financial services, healthcare, retail, operations, HR, marketing, etc.)
- **Target persona** (optional) — who will see the demo/PoC?
  - CIO/CTO → emphasize architecture, governance, platform fit
  - CFO → emphasize ROI, cost reduction, efficiency gains
  - COO/LOB VP → emphasize the workflow, before/after, process improvement
  - CDO → emphasize data strategy, semantic models, lineage
  - CISO → emphasize security, compliance, audit trail
  - Developer → emphasize technical architecture, APIs, extensibility
  - If unknown, design for a mixed audience (default)

#### Domain Primer (optional)

A primer is a **starting-point cheat sheet**, not a blueprint. Check `references/domains/`
for a matching file — if one exists, use it as loose inspiration during discovery:
- Skim for relevant business rules, data models, regulations, and vocabulary
- Cherry-pick what applies — most use cases only overlap partially with a primer
- The user's actual process always overrides primer suggestions

If **no primer exists** for the domain, that's completely fine — the trait-based
discovery works independently. Primers just save a few questions for well-known scenarios.

Available primers are samples; the team can add more over time. See `references/domains/README.md`.

### Step 2: Discover via Trait Detection

**Goal**: Progressive interview driven by detected traits. Start simple, branch as needed.

Reference: `references/process-traits.md`

#### Core Questions (always ask):

1. **Who's involved?** (Participants)
   - End users / customers
   - Internal staff / operators
   - External systems (APIs, databases, SaaS)
   - Other agents

2. **Where does data come from?** (Data Sourcing traits)
   - Websites → Web scraping trait
   - APIs / external systems → API integration trait
   - Documents / files → Document intake trait
   - Databases / corporate systems → Database query trait
   - Web search / research → Search/research trait
   - User provides it conversationally → User input trait
   - Events / webhooks / messages → Event-driven trait

3. **What happens to the data?** (Processing Style traits)
   - Extract → Extraction trait
   - Transform / normalize → Transformation trait
   - Compare / rank → Comparison trait
   - Analyze / score / assess → Analysis trait
   - Summarize / synthesize → Synthesis trait
   - Validate / check → Validation trait
   - Route / triage → Routing trait

4. **What gets produced?** (Output Mode traits)
   - Reports / documents
   - Structured data / records
   - Notifications / alerts
   - Decisions / recommendations
   - Conversations / responses
   - Actions in external systems

5. **How are humans involved?** (Interaction Model traits)
   - Fully automated (no human)
   - Human approves at key points
   - Real-time conversation
   - Human reviews output periodically

6. **When does it run?** (Temporal Pattern traits)
   - On-demand / user-triggered
   - Scheduled (daily, weekly)
   - Event-driven
   - Continuous / streaming

7. **Does this process track cases with a lifecycle?** (State Model trait)
   - Stateless — each request is independent
   - Session-based — state within a conversation, discarded after
   - Case-based — long-lived cases (open → in-progress → resolved)
   - Pipeline — items flow through ordered stages

   > **Default:** If the user doesn't know yet, **ask** rather than assume.
   > Stateless is the wrong default for any regulated process — assume
   > **case-based** for FSI / Healthcare / regulated supplier risk and
   > flag in spec § 12: "Defaulted to case-based; confirm lifecycle with
   > stakeholder."

8. **Does the agent take consequential actions?** (Action Criticality trait)
   - Read-only — only reads/analyzes data
   - Reversible writes — creates/updates data that can be undone
   - Irreversible actions — payments, approvals, notifications, external writes

   > **Default:** Read-only is the right default **only for the first
   > pilot iteration**. For any second-iteration spec, **ask** the user
   > which writes are in scope and document them in § 8 (Human Interaction
   > Points) with their action gates. A regulated process whose write
   > surface stays at "read-only" forever is a tutorial, not a pilot.

#### Trait-Driven Branching

Based on detected traits, ask the relevant follow-up questions from `references/process-traits.md`.
Don't ask all questions — only those relevant to the detected traits.

#### Data Availability Check

For each system integration identified:

- **Available** — you have access, credentials, API docs
- **Auth required** — exists but you need credentials/tokens
- **Internal only** — corporate system, need VPN/network access
- **Mock** — system exists but you can't access it for development

> **For systems marked "mock":** The spec will define data models and sample data
> so the agent can be developed and tested without the real system. When the real
> system becomes available, replace mock data with an MCP server or API connection.

#### Compliance Screen

At minimum, confirm:
1. **Data sources**: All public, or some require auth?
2. **PII**: Any personal data involved?
3. **Secrets**: Any API keys or credentials needed?
4. **Regulatory**: Any legal/regulatory constraints? (GDPR, HIPAA, industry-specific)
5. **Retention**: How long to keep data?
6. **Access**: Who can run this and see results?

### Step 3: Generate SpecKit

**Goal**: Produce the specification documents from discovery findings.

Use the template from `references/speckit-template.md`.

Create in the project directory:

#### `specs/SPEC.md` — The full SpecKit document

Must include all sections from the template:
1. **Process Overview** — name, domain, goals, scope, participants
2. **Process Flow** — step-by-step with actors, inputs, outputs, decision branches
3. **Business Rules** — numbered BR-XXX, each with condition/action/exception **+ KPI mapping** (drives § 9 continuous-eval contract)
4. **Data Models** — all entities with field-level schemas and system of record
5. **System Integrations** — each external system, direction, auth, availability (including **mock** flag)
5b. **External Systems & Mocks (MCP contract)** — endpoint shape, tools exposed, mock data scale, reset semantics. **INPUT CONTRACT for `foundry-mcp-aca`.** *Required for any process that talks to external systems.*
6. **Tool Contracts** — abstract tool definitions (not bound to any runtime)
7. **Knowledge Sources** — reference documents, policies, search indexes — with explicit `foundry-iq` / `mcp-search` / `inline-context` backing decision
7b. **AI Services & Model Selection** — chat / vision / DocIntel / Speech models with versions. **INPUT CONTRACT for `foundry-doc-vision-speech` and `azure.yaml` `config.deployments`.** Use **`gpt-5.4` family** as of May 2026 — `gpt-4o` is legacy. *Required for every process.*
8. **Human Interaction Points** — approvals, escalations, conversational flows — with **action-gate taxonomy** (`approve` / `edit-and-approve` / `reject` / `escalate` / `signoff` / `audit-view` / `request-info`). **INPUT CONTRACT for `threadlight-hitl-patterns`.**
8b. **Human Interaction (Workspace UX)** — case-list / inbox / dashboard / console / kanban / map shape with primary filters, detail sections, action toolbar, audit viewer. **INPUT CONTRACT for `threadlight-workspace-ui`.** *Optional — skip if humans only interact via approval cards.*
9. **Success Criteria** — functional, performance, quality targets + evaluation scenarios (S-XXX linked to BR-XXX) **+ Business KPIs table (BR → KPI mapping)** for continuous evaluation
10. **Trigger & Run Model** — how/when the process executes, volume, SLA
10b. **Triggers (Receiver contract)** — receiver type, idempotency key, dedup window, dead-letter rule. **INPUT CONTRACT for `threadlight-event-triggers`.** *Required for event-driven and scheduled processes.*
11. **Security, Compliance & Governance** — PII, auth, retention, regulatory, audit
11b. **Governance Posture (AI Governance Hub spoke — opt-in)** — `governance_hub.required` flag + spoke artifacts needed. **INPUT CONTRACT for the optional governance-hub spoke handoff in `threadlight-deploy`.** *Required for every regulated process.*
11c. **Tech Stack (Module selectors)** — Bicep module on/off list (cosmos, search, doc-intel, speech, event-grid, service-bus, foundry-iq-index, etc.). **INPUT CONTRACT for the `azd-patterns` Bicep module library and the composer in `threadlight-deploy`.** *Required for every process.*

> **Legacy-SPEC backfill — mandatory check before handing off to threadlight-deploy.**
> SPECs generated before § 11c was added to this skill (any SPEC where the section list jumps from § 11 to § 12, or has no kebab-case selector table) **must be backfilled** before Phase 6 of `threadlight-deploy` runs. The composer reads § 11c verbatim — without it, it can't tell "no aca-bot deployed" from "aca-bot intentionally not selected", and the post-deploy gate ships partial PoCs as if they were complete (for example, `aca-bot` and `aca-job` declared `yes` but zero deployed). Run a one-shot grep before generating Phase 6 modules:
> ```bash
> grep -E '^(##|###) 11c' specs/SPEC.md || echo "MISSING - reverse-engineer from azure.yaml services + infra/main.bicep modules and prepend § 11c table"
> ```
> If missing: read the existing `azure.yaml` services + `infra/main.bicep` modules, write the corresponding kebab-case selector table, prepend it to the SPEC at the right anchor, and re-validate.
11d. **Demo Data (Realism rules)** — per-entity volumes, distribution, golden cases, reset semantics, industry realism rules. **INPUT CONTRACT for `threadlight-demo-data-factory`.** *Required for every process with mocked systems.*
12. **Assumptions & Open Questions** — what's given, what needs stakeholder input

> **The abstract / pure-coding split.** Sections **5b, 7b, 8 (action gate), 8b, 9 (KPI table),
> 10b, 11b, 11c, 11d** are **input contracts** — each one is consumed mechanically by a
> downstream pure-coding skill. If a section is empty/missing, the corresponding
> downstream skill cannot generate working code. Always populate them at least minimally;
> use defaults from this skill's references when the user can't articulate them yet.

#### Generating Evaluation Scenarios (§ 9)

Every business rule (BR-XXX) must have **at least one** eval scenario. Derive them
systematically:

| For each BR-XXX | Generate these scenarios |
|-----------------|------------------------|
| **Happy path** | Input that satisfies the condition → verify the action fires correctly |
| **Boundary** | Input at the exact threshold → verify correct branch |
| **Negative** | Input that violates the condition → verify the exception/rejection |
| **Missing data** | Input with required fields missing → verify graceful handling |

**Naming:** `S-{NNN}` linked to `BR-{NNN}`. Example:
- BR-001: "Credit score < 580 → auto-decline"
- S-001: Happy path — score 780 → approved
- S-002: Boundary — score 580 → edge of auto-decline
- S-003: Negative — score 520 → auto-declined
- S-004: Missing — no credit score available → error handling

**Minimum coverage:** At least 3 scenarios per business rule (happy + boundary/negative + error).
For a spec with 10 rules, expect 30-50 eval scenarios.

These scenarios feed directly into `foundry-evals` for post-deployment scoring.

#### `specs/sample-data/{entity}.json` — Mock data (for systems marked "mock")

For each entity in § 4 Data Models where the backing system is marked "mock" in § 5:
- Generate **enough records to be credible at the scale named in § 11d**:
  the quick-rough default is **≥ 50 records per entity** for narrative
  walkthrough and **≥ 10K records** for executive scale-conversation.
  See `references/data-realism/{industry}.md` § "Production-realism
  volume + SLA defaults" for industry-specific volumes — those values
  win when they conflict with this default.
- Include varied data, hand-curated golden cases (named, story-bearing),
  some optional fields missing, and skewed distributions matching
  reality (no random uniform).
- Wrap each file as `{"_meta": {...}, "records": [...]}`. Do not put
  `_meta` as a sibling key to records — `threadlight-demo-data-factory`
  and `threadlight-workspace-ui` both depend on the wrapper shape.

> **Heavy lift goes to `threadlight-demo-data-factory`.** This skill
> writes the seed JSONs at narrative scale; the factory skill generates
> additional records to scale-conversation volume on demand using
> deterministic seeds, capped concurrency, and the per-industry
> distributions documented in `references/data-realism/{industry}.md`.

#### `specs/sample-data/README.md` — Migration guide

Explains:
- What each sample file represents and which system it mocks
- The expected schema (references SPEC.md § 4)
- How to replace mock data with a real MCP server or API connection
- Example: "When SAP becomes accessible, replace `specs/sample-data/orders.json` with
  an MCP tool call to `sap_get_orders` — the schema stays the same"

### Step 4: Checkpoint

After generating `specs/`, present the spec summary to the user:

```
📋 SpecKit: {name}
📌 Traits: {detected traits}

📊 Business Rules: {count} (BR-001 through BR-{N})
📦 Data Models: {list of entities}
🔌 Integrations: {list — marking which are mocked}
🧪 Eval Scenarios: {count}

📁 Generated:
  specs/SPEC.md
  specs/sample-data/{entity}.json (× {count})
  specs/sample-data/README.md
```

Then also generate `specs/manifest.json` for resume durability:

```json
{
  "process_name": "{name}",
  "spec_version": "1.0",
  "status": "checkpoint",
  "phase_reached": "A",
  "generated_files": ["specs/SPEC.md", "specs/sample-data/..."],
  "traits": ["{trait-1}", "{trait-2}"],
  "created_at": "{ISO date}"
}
```

Then tell the user:

> **Checkpoint reached.** You can:
> - **Review and edit** the specs before continuing
> - **Share** the specs with stakeholders for feedback
> - **Continue** to Phase B to generate AGENTS.md + Skills from these specs
> - **Stop here** and resume later — just say "generate agents from specs" in a future session

**In fast-PoC mode:** Skip the checkpoint — proceed directly to Phase B.

---

## Phase B: SpecKit → Agents.md + Skills

**Goal**: Read the specs and derive implementation artifacts.

If `specs/SPEC.md` exists, read it. If not, run Phase A first.

### Step 5: Design Architecture from Spec

Read the spec and derive the architecture using these deterministic rules:

#### Skill Derivation Recipe

1. **Map process steps to candidate skills:**
   - Group consecutive steps that share the same actor type into a skill
   - Steps with different actor types (agent vs system vs human) usually split into separate skills
   - A single step that is complex enough (multiple sub-actions, branching) can be its own skill

2. **Do NOT create "orchestrator" skills.** Orchestration is the agent's job (via
   AGENTS.md instructions), not a skill's job. Skills are domain-specific knowledge
   and procedures — they don't coordinate other skills. If you need orchestration logic,
   put it in `copilot-instructions.md` as behavioral guidelines, e.g.:
   - "When the user asks for X, first use skill A to gather data, then skill B to analyze"
   - "If risk score > threshold, escalate to human review"

3. **Human interaction points → dedicated handling:**
   - Each approval/escalation flow from spec § 8 maps to approval logic in the relevant skill
   - Conversational interaction points may warrant a dedicated skill

4. **Knowledge sources → Foundry IQ or MCP:**
   - **Documents, policies, regulations, product docs, brand guidelines, runbooks**
     (spec § 7) → **Foundry IQ** (Azure AI Search with agentic retrieval — query
     planning, multi-hop, citations). See `foundry-iq` skill. **Foundry IQ is the
     default knowledge retrieval pattern for every threadlight process** — even
     processes that primarily query transactional data should ship with a Foundry
     IQ index for their domain policies. Set `Backing service: foundry-iq` in spec
     § 7 unless the corpus is genuinely tiny (then `inline-context`) or genuinely
     live (then `mcp-search`).
   - **Dynamic/transactional data** (spec § 5 integrations) → **MCP server**
     (mock for PoC, real for production). See `foundry-mcp-aca` skill.
   - **Cosmos DB** → MCPToolKit (10 tools out of the box) as `src/mcp/`

5. **Temporal pattern → trigger design:**
   - On-demand → user invocation
   - Scheduled → Azure Functions or cron
   - Event-driven → webhook or message queue trigger

6. **Validation checklist (every item must pass):**
   - [ ] Every BR-XXX rule is covered by at least one skill's procedure
   - [ ] Every tool contract from spec § 6 has a concrete implementation (Foundry tool, MCP, or mock)
   - [ ] Every mocked system has sample data in `specs/sample-data/`
   - [ ] Every eval scenario (S-XXX) can be tested with the generated skills + mock data
   - [ ] No orphan skills — every skill is reachable from the agent's instructions

#### Feasibility Preflight

Before generating files, verify:
- [ ] Required tools are available (Foundry tools, MCP servers, or viable mock alternatives)
- [ ] Auth patterns identified for all non-mock system integrations
- [ ] Storage strategy defined for any persistent state (no local filesystem in production)
- [ ] Model capability matches needs (tool count, context window, reasoning depth)

#### Architecture Summary

Present to user before generating:

```
📋 Process: {name} (from specs/SPEC.md)

📁 Skill Structure:
  - {skill-1}: {purpose} (implements BR-001, BR-003)
  - {skill-2}: {purpose} (implements BR-002, BR-004, BR-005)

🔧 Tools:
  - {tool-1} → {Foundry tool or MCP server}
  - {tool-2} → {Foundry tool or MCP server}
  - {tool-3} → mock data (specs/sample-data/{entity}.json)

⚠️ Mock systems: {list — will need real integration later}
```

**Wait for user approval before generating files.**

### Step 6: Generate Implementation Artifacts

#### 1. `src/agent/skills/{skill-name}/SKILL.md` (for each skill)

Use the template from `references/skill-template.md`. Each skill MUST have:
- YAML frontmatter with `name` and `description` (include USE FOR / DO NOT USE FOR)
- **Spec traceability**: "Implements BR-001, BR-003" in the header
- Operational contract (inputs, outputs, deps, idempotency, failure behavior)
- Step-by-step procedure (derived from spec process flow)
- Output schema (derived from spec data models)

> **Convention:** Process skills go directly into `src/agent/skills/`. Do NOT put them
> in `.github/skills/` — that location is reserved for coding/development skills
> (skills that help develop the repo itself, not the agent's runtime skills).

#### 2. `AGENTS.md`

Use the template from `references/agents-template.md`. Must include:
- Agent identity and purpose (derived from spec § 1)
- Available skills table (derived from step 5 decomposition)
- Foundry tools required (derived from spec § 6 tool contracts)
- Data & storage strategy
- Behavioral guidelines
- **Spec reference**: "This agent implements specs/SPEC.md"

#### 3. `src/agent/config/{name}.json`

Configuration file with parameters and thresholds from the spec.

#### 4. `mcp-config.json`

MCP server configuration for development. Generate:
- `.vscode/mcp.json` — for VS Code Agent Mode (dev-time, local MCP servers)

> **Note:** Do NOT generate `.copilot/mcp-config.json` in the project — that's a
> user-level config. The runtime MCP config lives at `src/agent/mcp-config.json`
> and is generated by `threadlight-deploy`.

Map spec tool contracts to local MCP servers where possible:

| Spec Tool Type | Local MCP Server |
|---------------|-----------------|
| Web scraping | `@playwright/mcp` |
| Knowledge retrieval | Azure AI Search SDK (local) → Foundry IQ (deployed) |
| Cosmos DB | `@azure/mcp` with cosmos namespace → MCPToolKit ACA (deployed) |
| Azure AI Search | `@azure/mcp` with search namespace |
| Fabric data | `@microsoft/fabric-mcp` |
| Web search | Tavily MCP (remote HTTP) |

For tools backed by mock data: document in the project README which tools use
sample data files and will need real MCP/API connections later. Do NOT put
comments in JSON config files.

#### 5. `specs/manifest.json`

Machine-readable deployment contract (lives with the spec):

```json
{
  "name": "{process-name}",
  "version": "1.0.0",
  "speckit": "specs/SPEC.md",
  "description": "{one-line description}",
  "traits": ["{trait-1}", "{trait-2}", "{trait-3}"],
  "business_rules_count": 0,
  "skills": [
    {"name": "{skill-1}", "implements": ["BR-001", "BR-003"]},
    {"name": "{skill-2}", "implements": ["BR-002"]}
  ],
  "mock_systems": ["{system-1}"],
  "compliance": {
    "pii": false,
    "auth_required_sources": [],
    "regulatory": []
  },
  "deployment_manifest": {
    "module_selectors": {
      "foundry-account":  "yes",
      "cosmos-db":        "yes",
      "ai-search":        "yes",
      "foundry-iq-index": "yes",
      "aca-mcp":          "yes",
      "aca-bot":          "yes",
      "aca-job":          "yes",
      "workspace-ui":     "yes",
      "key-vault":        "no",
      "event-grid":       "no"
    },
    "services": [
      {"name": "agent",     "host": "azure.ai.agent",   "src": "src/agent"},
      {"name": "mcp",       "host": "containerapp",     "src": "src/mcp"},
      {"name": "bot",       "host": "containerapp",     "src": "src/bot"},
      {"name": "workspace", "host": "containerapp",     "src": "src/workspace"}
    ],
    "scheduled_jobs": [
      {"name": "{job-name}", "schedule": "*/15 * * * *", "tool": "{tool-name}", "src": "src/jobs/{job-name}"}
    ],
    "channels": [
      {"name": "Analyst Workspace",      "type": "web",            "service": "workspace"},
      {"name": "Teams adaptive card",    "type": "teams",          "service": "bot"},
      {"name": "Email deadline alerts",  "type": "email",          "service": "{service or external}"}
    ],
    "expected_resource_types": [
      "Microsoft.CognitiveServices/accounts",
      "Microsoft.DocumentDB/databaseAccounts",
      "Microsoft.Search/searchServices",
      "Microsoft.App/managedEnvironments",
      "Microsoft.App/containerApps",
      "Microsoft.App/jobs",
      "Microsoft.BotService/botServices",
      "Microsoft.ManagedIdentity/userAssignedIdentities",
      "Microsoft.ContainerRegistry/registries",
      "Microsoft.Insights/components"
    ]
  }
}
```

> **`deployment_manifest` is a contract `threadlight-deploy` reads
> mechanically.** The deploy skill's Phase 3 module-selector check
> walks `module_selectors`, confirms each service maps to a folder
> under `src/` with a Dockerfile, and confirms every `infra/*.bicep`
> module is wired in `main.bicep`. Phase 3.5 then takes
> `expected_resource_types` and asserts every entry is in
> `az resource list -g <RG>` after `azd up`. The mechanical
> implementation is the **`threadlight-safe-check`** skill — invoke
> `python -m threadlight.safe_check --phase {design|pre-deploy|post-deploy}`
> at the corresponding lifecycle points. If you flip a selector
> from `yes` to `no` mid-pilot, **delete the corresponding source
> folder and Bicep module too** ` orphans break the orphan check.

> **Required for every process where `aca-bot`, `aca-job`,
> `workspace-ui`, or any other selector that produces a deployable
> service is `yes`.** Without `deployment_manifest`, the deploy gate
> can't tell missing services from intentionally-skipped ones, and
> ships partial PoCs as if they were complete (`aca-bot` and
> `aca-job` declared `yes` in SPEC § 11c, deployed as zero resources,
> and not noticed until someone opens the resource group).

#### 6. `README.md`

Project documentation covering:
- What this agent does (from spec § 1)
- Architecture overview (text-based diagram)
- Skill catalog with purposes and spec traceability
- Configuration guide
- Mock data status (which systems are mocked, how to replace)
- Deployment path (reference threadlight-deploy)

#### Cross-cutting HTML artefact patterns (deck / experience / prep-guide)

Seven patterns apply uniformly to the HTML artefacts this skill emits.
Patterns 1–3 have surfaced as user gripes during PoC walkthroughs ("nothing
matches our brand", "this .md link is dead", "the seller doesn't want to read
azd commands"); Patterns 4–7 are battle-scars from the demo-polish phase
(persona leaks into the talk deck, internal jargon like "OneAsk" or "Sweden
Central" leaking onto customer-facing slides, fabricated tool names
contradicting AGENTS.md, and commit-language closings the seller can't
defend). Implement them all once at generation time; never reach for them
post-hoc.

##### Pattern 1 — Brand cascade rule (mandatory when brand palette declared)

When SPEC § 1 (Customer / domain) declares a customer brand palette OR the
discovery transcript captured brand colours implicitly (logo url, "they're
red like that well-known UK telco", "their site is the orange one"), every generated HTML
artefact MUST cascade the brand accent + key shadow tokens while preserving
the **structural neutrals** that give each visual paradigm its identity
(parchment, charcoal, navy, brass wax-seal accents on the dossier paradigm;
ink-blue + slate on the editorial paradigm; etc.).

**Detection rule.** During Step 6 generation, scan SPEC § 1 + the discovery
transcript for any of:

- Explicit `customer.brand_palette: { primary: "#XXXXXX", secondary: "#YYYYYY" }`
- Brand-colour mention captured in transcript ("they're red like the well-known UK telco", "their site is the orange one")
- Logo URL → fetch + sample dominant non-neutral hex (offline if possible)
- Sector convention ("any NHS trust uses #005EB8")

When a brand palette is detected, inject ONE override block at the top of
the artefact's CSS that swaps `--accent` / `--accent-strong` / `--shadow-key`
while leaving paradigm tokens (`--parchment`, `--charcoal`, `--ink`,
`--brass`, `--linen`) untouched.

**Cascade table** (paradigm tokens that swap vs preserve):

| Token category | Swap to brand? | Why |
|---|---|---|
| `--accent`, `--accent-strong`, `--cta` | YES | Carries the brand instantly recognisable on hero / CTAs |
| `--shadow-key`, `--ring-focus` | YES (de-saturated brand) | Keeps shadows brand-coherent without screaming |
| `--parchment`, `--charcoal`, `--ink`, `--brass`, `--linen` | NO | Structural neutrals define the **paradigm**, not the brand. Swapping them collapses the dossier / editorial / blueprint look into a generic web page. |
| `--success`, `--warn`, `--danger` | NO | Universally legible; do not negotiate |

**Validation.** Before declaring done, grep that the brand accent hex (or
its rgb()/rgba() equivalent) IS present in the generated CSS for each of
demo-deck.html / experience.html / prep-guide.html. If absent → cascade
rule wasn't applied → fix before presenting to user.

**Deeper rules for `demo-deck.html` (the talk deck).** A talk deck takes
the cascade further than the brief/dossier/crib-sheet artifacts because the
brand has to read at projector distance:

- **Brand FLOODS** — full-bleed `bg-{brand}-flood` panels: **mandatory on
  friction + follow-up + close** (the 3 emotional anchors) + ≥ 1 more
  chosen from {hero, the-shift, scale, posture} → ≥ 4 flood panels per
  deck. A **dark hero** with brand-accent gradient is a valid cinematic
  opening (the reference deck uses this); it does NOT have to be one
  of the brand-flood panels.
- **Brandmark substitute** (when no logo licensed) — a 2-letter monogram
  rendered on a white circle on the brand-flood panel. Echoed on slide 1
  (cold-open) and slide N (close) as bookend. See
  `references/demo-deck-template.md` § "Brandmark substitute recipe".
- **Microsoft 4-color SVG co-brand bar** — canonical hex `#F25022 #7FBA00
  #00A4EF #FFB900` (verbatim, do not approximate) + "Microsoft × {Customer}"
  wordmark. Present on hero AND close.
- **No third-color accents** — if the brand primary is `#E60000` red, the
  deck CANNOT introduce cobalt / amber / purple as section accents. Use
  brand-darker (`--brand-dark`) and brand-brighter (`--brand-bright`)
  shades only.
- **Reveal pacing tuned to brand identity** — telco / retail / consumer =
  bold/fast (200ms stagger); FSI / healthcare / public-sector =
  serif/measured (400ms stagger). Read the cue from SPEC § 1 domain.
- **Convention fallback** — when `customer.brand_palette.primary` is NOT
  captured and there's no logo URL, consult
  `references/brand-palettes.md` for the sector convention (UK telco red
  `#E60000`, NHS blue `#005EB8`, etc.). Annotate SPEC § 12 assumptions
  with `brand_palette_source: convention-fallback` so the next iteration
  confirms with the customer.

**Auto-review for deck (in addition to the base validation above):** grep
for ALL of (a) the brand hex, (b) `bg-{brand}-flood` class present, (c)
brandmark substitute markup present on slide 1 + final slide, (d) MS
co-brand block on hero + close.

##### Pattern 2 — Markdown modal pattern (mandatory in HTML artefacts that link to .md)

Sellers cannot meaningfully open `.md` files. A `<a href="../specs/SPEC.md">`
link either 404s on `file://` (the most common way sellers open the
artefact during a Cowork pitch), or — if hosted — opens raw markdown as a
plaintext blob with no formatting. Both outcomes degrade credibility.

**Required behaviour.** Every `.md` link in any generated HTML artefact
MUST open as a click-to-render dialog with:

1. The markdown rendered in-browser
2. A short explanatory blurb above ("This is the SpecKit specification —
   the canonical source of truth the agent implements.") so the seller
   knows *what they're looking at* before they read it
3. Esc key + overlay click both close the modal
4. Brand-styled dark substrate that looks consistent regardless of the
   host artefact's theme (parchment / dark / dossier all coexist)

**Self-contained anatomy.** No fetch() — works on `file://`. Pattern:

1. **Embed the markdown** as opaque blobs at the bottom of the host HTML:
   ```html
   <script type="text/markdown" id="md-spec" data-source="../specs/SPEC.md">
   # SpecKit Specification
   ...full markdown here, no escaping needed because it lives in a script tag...
   </script>
   ```
   Browsers do not parse the contents of `<script type="text/markdown">` —
   they're inert blobs you read via `document.getElementById(...).textContent`.

2. **Register the link → blob mapping** in a small JS object at the top of
   the artefact:
   ```javascript
   const MD_REGISTRY = {
     "../specs/SPEC.md":      { id: "md-spec",     title: "SpecKit Specification",
                                intro: "The canonical source of truth..." },
     "../README.md":          { id: "md-readme",   title: "README",
                                intro: "Quick-start guide..." },
     "../tests/eval-summary.md": { id: "md-eval",  title: "Evaluation Summary",
                                   intro: "Latest quality bar..." }
   };
   ```

3. **Rewrite `<a href="*.md">` to `<a data-md="*.md">`** at generation
   time. Add a CSS affordance hint:
   ```css
   a[data-md]::after { content: " ◇"; opacity: .6; font-size: .85em; }
   ```

4. **Single document-level click delegate** intercepts:
   ```javascript
   document.addEventListener("click", (e) => {
     const a = e.target.closest("a[data-md]");
     if (!a) return;
     e.preventDefault();
     openMdModal(a.dataset.md);
   });
   ```

5. **Renderer with fallback.** Try `marked.js` from CDN
   (`cdn.jsdelivr.net/npm/marked@12`) loaded async at modal open; fall
   back to a ~50-line hand-rolled subset that handles h1-h3, fenced
   code, blockquotes, lists, tables, links, bold/italic. **Do not**
   ship without the fallback — sellers in Cowork frequently have CDN
   blocked.

6. **Modal substrate** uses FIXED dark tokens independent of host page
   tokens (so it looks consistent on parchment + dark hosts):
   ```css
   .md-modal { background: rgba(10,12,18,.92); }
   .md-modal-card { background: #f6f3ec; color: #1a1c22; /* parchment-on-dark */ }
   ```

> **Reusable pattern, NOT shipped reference script.** Each pilot writes
> its own ~120-line generator (`gen_md_modal.py` or inline Python in the
> artefact-generation script). The pattern above is more durable than
> any specific implementation; resist the urge to ship a reference
> script that turns into the next stale dependency.

##### Pattern 3 — `<details class="se-only">` audience-collapsible

Sellers reading a prep-guide do NOT want to scan past `azd up` blocks,
Bicep walkthroughs, raw GUIDs, or re-deploy procedures to reach the
demo script. SA / SE engineering content MUST be wrapped in
`<details class="se-only">` so seller-mode readers see only
seller-relevant content by default.

**Anatomy:**

```html
<details class="se-only">
  <summary>
    <span class="audience-pill">SA only</span>
    <strong>Re-deploy after corpus refresh</strong>
    <span class="hint">azd deploy agent · ~3 min</span>
    <span class="chev">▸</span>
  </summary>
  <div class="se-body">
    <pre><code>azd deploy agent
azd ai agent invoke "test prompt"</code></pre>
  </div>
</details>
```

**CSS rules:**

- `.audience-pill` — orange-bordered amber pill (use `--confidential`
  token, default `#eb9700`); short label like "SA only" or "Engineer"
- Bold dark `<strong>` summary text + right-aligned dim hint
  (`margin-left: auto`, mono small) describing what's inside without
  opening
- `<span class="chev">▸</span>` rotates 90° via
  `details[open] .chev { transform: rotate(90deg) }`
- Native `summary::-webkit-details-marker { display: none }` suppressed
- Mobile-responsive: hint wraps to its own line on narrow viewports
- **Default closed** — sellers see the affordance (the orange pill is
  obvious) but are not visually nagged by content they don't need

**When to wrap.** Any block that contains:
- `azd ` / `az ` / `python ` / `pwsh ` / `kubectl ` commands
- Raw GUIDs (subscription IDs, tenant IDs, resource IDs)
- Bicep / Terraform fragments
- `infra/` / `tests/` paths sellers have no reason to open
- "If something goes wrong..." troubleshooting

**Global dual-mode toggle (mandatory on prep-guide.html).**

Individual `<details>` collapsibles are necessary but not sufficient.
Sellers still see `se-only` section headers and have to scan past them.
The prep-guide MUST include a **sticky mode toggle bar** at the top that
globally shows or hides ALL `se-only` content:

```html
<div class="mode-toggle-bar">
  <span>View mode:</span>
  <button class="mode-toggle-btn is-active" id="btn-seller"
    onclick="setGuideMode('seller')">🎤 Seller</button>
  <button class="mode-toggle-btn" id="btn-se"
    onclick="setGuideMode('se')">🔧 Solution Engineer</button>
</div>
```

**JS pattern:**

```js
function setGuideMode(mode) {
  document.body.classList.remove('mode-seller', 'mode-se');
  document.body.classList.add('mode-' + mode);
  // Toggle button active state
  document.getElementById('btn-seller').classList
    .toggle('is-active', mode === 'seller');
  document.getElementById('btn-se').classList
    .toggle('is-active', mode === 'se');
  // In SE mode, auto-open all se-only details
  if (mode === 'se') {
    document.querySelectorAll('details.se-only')
      .forEach(function(d) { d.open = true; });
  }
  try { sessionStorage.setItem('prep-guide-mode', mode); } catch(e) {}
}
```

**CSS:**

```css
body.mode-seller details.se-only { display: none; }
body.mode-se details.se-only { display: block; }
```

**Rules:**
- Default mode = `seller` (restored from `sessionStorage` on load)
- Seller mode: ALL `se-only` blocks vanish — zero engineering content
- SE mode: ALL `se-only` blocks appear and auto-open
- The toggle bar is `position: sticky; top: 0; z-index: 50`
- Mode persists across page refreshes via `sessionStorage`

##### Pattern 4 — Internal-jargon deny-list (mandatory on customer-facing artifacts)

Customer-facing artifacts (`demo-deck.html`, and `experience.html` if generated) MUST pass a
deny-list grep before declaring done. Battle-scar source: a recent live session,
where the deck leaked `OneAsk`, `Sweden Central`, `v1.0`, `load_skill`, and
an individual contributor's name across three rejection cycles before the
user banned them outright.

> **prep-guide.html is EXEMPT** from this pattern — it's internal-only and
> legitimately references `azd`, region labels, command syntax, etc. inside
> `<details class="se-only">` collapsibles (Pattern 3).

**Deny-list tokens** (case-insensitive grep; zero hits required):

| Category | Sample tokens |
|---|---|
| Microsoft internal product names | `OneAsk`, `OneCRM`, `MyCSS`, `OneMSAccount`, `Substrate`, `MyOrder`, `MTS` |
| Azure region / SKU / engineering metadata | `Sweden Central`, `East US 2`, `S0`, `v1.0`, `Phase 26`, `gpt-5.4-mini-2024-07-18` (the date suffix only — the model name is fine) |
| Individual seller / engineer PII | first+last name of any contributor, `@github_handle`, `@msft alias`, email addresses |
| Fabricated function names | any `_skill` / `_tool` identifier that is NOT in the AGENTS.md `Foundry tools required` table (catches `load_skill`, `customer_knowledge_base_retrieve`, etc.) — see Pattern 6 for the canonical-naming gate |

**Extensible per pilot.** SPEC § 12 assumptions block can carry an
`additional_denied_tokens: [...]` list that gets folded into the grep.
Typical additions: customer-internal codenames, prior-vendor product
names the customer has explicitly distanced from, regulatory boilerplate
they want kept out of the visual narrative.

**Validation.** Before declaring done, grep the customer-facing artifacts
(deck, and experience if generated) for every deny-list token. Any hit → fix → re-grep.
Document the grep result in the auto-review hand-off so the user can
audit it.

##### Pattern 5 — Persona placement rule

Personas (named protagonists in the customer journey — e.g. Sarah / Carl /
Sophie / Rashid in a Care-journey PoC) live in **exactly one** artifact:

- ✅ `specs/experience.html` (the cinematic dossier, if generated) — personas ARE the
  protagonists of the journey; this is where they belong
- ❌ `specs/demo-deck.html` — the deck is the **customer journey**, not
  the customer. Refer to roles instead of names: "the analyst", "the
  agent", "the customer", "the case-handler". The talk-deck audience
  hasn't met the personas; bringing in names mid-talk distracts from
  the journey.
- ❌ `specs/prep-guide.html` § Demo Script "Type this:" prompts — the
  prompts go into the deployed agent as literal strings; the agent's
  surfaces (Workspace / Teams / Foundry playground) don't know the
  personas either. Use roles or generic IDs in prompts.

**Battle-scar source.** A recent live session — the user explicitly banned
persona mentions in the deck after the third rejection cycle:
*"I EXPLICITLY ASKED TO NOT BUG ME ABOUT USER PERSONA!"* The fix was a
strict grep gate for known persona first-names sourced from
`experience.html` itself.

**Validation.** Extract the set of persona first-names from
`experience.html` (parse `<h*>` and `<p class="protagonist">` elements
matching SPEC § 5 persona schema). Grep the deck for any hit on that
set → fail if found. Recommend a fix that swaps the persona name for
its role descriptor from the same SPEC § 5 row.

##### Pattern 6 — Canonical tool-naming gate

Any artifact that depicts the skill chain (deck slide 6, experience trust
panel, prep-guide architecture appendix) MUST use tool names verbatim from
the AGENTS.md `Foundry tools required` table — not paraphrased, not
abbreviated, not fabricated.

**Battle-scar source.** A recent live session — slide 7 of the deck originally
had `customer_knowledge_base_retrieve` (paraphrased) and `load_skill` (entirely
fabricated). The user pointed it out: *"In the skill chain, why
load_skill??"*. Both names were swapped to the canonical
`customer_kb` name from AGENTS.md.

**Validation.** Extract every tool name from the deck/prep-guide (and experience if generated)
(parse `<code>` blocks, pill labels, and skill-chain SVG text nodes).
Set-diff against the AGENTS.md `Foundry tools required` table column 1
→ fail on any name not in the table. If a tool genuinely needs a
display-friendly label, document the alias under `AGENTS.md § Tool
display aliases` and let the diff treat it as canonical.

##### Pattern 7 — No-commitment closing rule

Microsoft GBB engagements cannot commit dates, effort, or follow-up
motions in a customer demo. Customer-facing closing artifacts present
concrete **options**, not **commitments**.

**Battle-scar source.** A recent live session — the deck's first closing slide
read *"Pick one Care journey we'll build together by 12 June."* The user
killed it: *"we can't commit dates or effort, we won't be doing the
follow up likely"*. The fix evolved across v5-v8: first a Discussion slide
(3 open questions), then a **Follow-up Proposal** (3 concrete next steps
framed as options on the table, not promises).

**Banned phrases** (case-insensitive grep over deck slides N-1 and N,
plus the experience.html trust panel):

- `we'll build`, `we will build`, `let's build`, `build together`
- `by {date}`, `by ${MONTH}`, any literal future date within 90 days of
  the deck generation timestamp (regex over ISO + "DD Month" formats)
- `let's commit`, `let's lock`, `let's confirm dates`
- `next month`, `phase 2 dates`, `Q3 milestones`
- `pick one journey`, `pick one process`, `commit to`

**Permitted phrasings** (style guidance for the Follow-up Proposal slide):

- "Pick 5 high-friction journeys" (action, not commitment)
- "Deploy governance hub" (option, not promise)
- "Establish eval baseline" (technical step, not timeline)
- "happy to explore", "happy to dig in"

**Closing shape.** The deck's last two slides MUST follow the **Follow-up
Proposal + Thank-you** bookend pattern (see § 7 slide grammar rows 10
and 11). The follow-up presents 3 concrete next steps using
`<div class="discussion-card">` cards with `<span class="qnum">Step
01/02/03</span>` labels. Each step is an action the customer could take,
framed as an option. Engineer-only commitments (workshop plans, eval
runs, effort estimates) belong in `prep-guide.html § Suggested Next
Steps` wrapped in `<details class="se-only">` collapsibles (Pattern 3).

**Validation.** Grep deck slides N-1 and N for banned phrases → fail if
found. The Thank-you slide MUST contain literal `Thank you.` and the MS
× {Customer} co-brand bar. The Follow-up slide MUST contain ≥ 3
`<div class="discussion-card">` (or equivalent) with step cards; if
any card text matches a banned phrase, fail.

#### 7. `specs/demo-deck.html` — Cinematic Talk Deck (MANDATORY — primary customer-facing artifact)

> **Read `references/demo-deck-template.md` for the full kit-of-parts** — slide
> grammar with "use when SPEC has X" rules, CSS token table, JS controller
> pattern, brandmark substitute recipe, Microsoft 4-color SVG (canonical
> hex), the 18-symbol icon library, and the "Reasons a deck gets rejected"
> anti-pattern list drawn directly from prior live-session pain.

Generate a **single self-contained HTML file** (no external CDNs, no
network dependencies) that the seller projects full-screen during the
live customer talk. Keyboard-paced; speaker notes panel toggled from the
keyboard; ≤ 8 minutes of presentation time.

**This artifact REPLACES the legacy `overview.html`.** A long-form scrollable
"seller pitch page" is the wrong shape for any live customer moment — too
long to skim before the call, too brief and too scrollable to project, and
too generic to compete with the bespoke dossier (experience.html). When
upgrading an existing PoC, collapse the old `overview.html` to a 1.8 KB
meta-refresh redirect → `demo-deck.html` (canonical migration recipe in
`references/demo-deck-template.md` § "Migration"); archive the old content
as `overview.html.bak` (add `specs/*.html.bak` to `.gitignore`).

**Slide grammar — 10 to 13 slides, in order:**

| # | Slide type | Mandatory? | Use when SPEC has |
|---|---|---|---|
| 1 | Cold-open (brandmark + customer journey name + headline) | ✅ Mandatory | Always |
| 2 | Context (customer's stated goal — quote SPEC § 1) | ✅ Mandatory | Always |
| 3 | Friction (3 numeric pain points — pulled from SPEC § 3 BRs implying current state) | ✅ Mandatory | Always |
| 4 | The shift (before/after framing — pulled from SPEC § 9 functional success criteria) | Conditional | SPEC § 9 has a quantified primary KPI |
| 5 | Preview answer (mock Q&A card with citation pill + version badge — visual insurance before the live demo; if the demo wobbles, flip back to this slide) | Conditional | Any PoC with a live demo path |
| 6 | Live-demo cue ("Now let's watch" + optional pure-black holding card for tab-switching) | ✅ Mandatory | Always |
| 7 | Skill chain (canonical tool sequence — verbatim from AGENTS.md `Foundry tools required` table) | ✅ Mandatory | Always |
| 8 | Platform stack (6-7 layer cake: Surfaces · Channel runtime · Agent runtime · Knowledge · Tools+data · Observability · Foundation; each tech pill carries an inline SVG icon from the 18-symbol library) | ✅ Mandatory | Always |
| 9 | Architecture — hub-spoke + governance (Feature→Service format in hub block, governance cards with repo links; see `references/demo-deck-template.md` § "Architecture slide") | Conditional | SPEC § 11 governance posture or scale targets |
| 10 | Follow-up proposal (3 concrete next steps — options on the table, not commitments) | ✅ Mandatory | Always |
| 11 | Close (brandmark echo + "Thank you." + Microsoft × {Customer} co-brand bar) | ✅ Mandatory | Always |

The Follow-up + Close pair on slides N-1 and N is the **canonical closing
shape** for every Microsoft GBB demo. The follow-up slide presents concrete
next steps (not open questions) — "Pick 5 high-friction journeys", "Deploy
governance hub", "Establish eval baseline" — as options, not commitments.
See Cross-cutting Pattern 7 for the banned/permitted phrase enforcement.

**Required interactions:**

- **Keyboard nav** — `Space` / `→` advance · `←` back · `F` fullscreen · `S`
  toggle speaker notes panel · `B` blackout · `0`–`9` jump · `Home`/`End`
  first/last
- **Sub-state reveals** — slides with `data-states="N"` advance through N
  reveal states before going to the next slide (Space-paced); used on the
  cold-open and friction slides for a controlled reveal cadence
- **Progress bar + slide counter** — always visible, auto-derived from
  `slides.length` so adding/removing slides doesn't break the counter
- **Speaker notes panel** — 1:1 mapping `data-for="N"` ↔ slide N; toggled
  by `S`; rendered in a side-panel that does not project (visible only on
  the speaker's screen in extended-display mode)

**Brand respect (Cross-cutting Pattern 1, deeper rules for the deck):**

- **Brand FLOODS** — full-bleed `bg-{brand}-flood` panels: **friction +
  follow-up + close mandatory**, plus ≥ 1 more chosen from {hero,
  the-shift, scale, posture} → ≥ 4 flood panels total. **Dark hero** is
  allowed (and used in the reference deck).
- **Brandmark substitute** when no licensed customer logo is available —
  2-letter monogram on a white circle on the brand-flood panel; echo on
  slide 1 + final slide as bookend (e.g. "BC" for Beacon Communications)
- **Microsoft 4-color SVG co-brand bar** with "Microsoft × {Customer}"
  wordmark on hero AND close — canonical hex `#F25022 #7FBA00 #00A4EF
  #FFB900`
- **Canonical tool naming** — any deck/prep-guide (and experience if generated) tool name MUST appear
  verbatim in the AGENTS.md `Foundry tools required` table (column 1) OR
  in the optional AGENTS.md `Tool display aliases` block. See Cross-cutting
  Pattern 6 for the set-diff gate. Fabricated names (`load_skill`,
  paraphrased MCP transports) fail validation.
- **Convention fallback** — when brand palette isn't explicit in SPEC § 1
  and there's no logo URL, look up `references/brand-palettes.md`; annotate
  `brand_palette_source: convention-fallback` in SPEC § 12

**Style:**

- Single file, no external CDN, fonts, or scripts — everything inline
- Inline `<svg>` symbol library defined in `<defs>` once, referenced via
  `<use href="#ico-XXX">` in each tech pill (18 stock symbols documented
  in `references/demo-deck-template.md` § "Tech-stack icon library")
- Light-inverse slide (`.bg-light` + dark text) inserted mid-deck for a
  rhythm break
- Closing pair (slide N-1 + slide N) uses the **Follow-up + Thank you**
  bookend pattern from Cross-cutting Pattern 7

**Required validation (mandatory before declaring done):** see Step 8
auto-review checklist for the full set; the deck-specific gates include
brand-flood panel count ≥ 4, brandmark substitute markup on slide 1 +
final slide, MS co-brand block on hero + close, persona deny-list zero
hits (Cross-cutting Pattern 5), internal-jargon deny-list zero hits
(Pattern 4), tool-name set ⊆ AGENTS.md tool table (Pattern 6), banned
closing-phrase zero hits (Pattern 7).

> **Polish pass (optional but recommended).** After generating
> `demo-deck.html`, run [`gbb-humanizer`](../gbb-humanizer/) over the
> **speaker-note prose** (the `<div class="note" data-for="N">…</div>`
> blocks at the bottom of the deck). The seller reads these aloud during
> the live talk — even small AI-prose tells degrade credibility. Use the
> pre-canned `gbb-seller-pitch.md` voice sample. **Do not** humanize the
> slide bodies themselves — those are display copy (kickers, headlines,
> numeric data points) where the prose is already disciplined and the
> humanizer adds nothing.

#### 8. `specs/experience.html` — Bespoke Cinematic Customer Journey (OPTIONAL — on request)

A second seller-facing artifact that complements `demo-deck.html`. Where the
deck is a **live talk**, the experience is a **bespoke journey** that makes
the customer feel the pain, the intervention, the outcome, and the trust
posture of *this* process — through visuals native to *its* domain.

> **Generate when requested.** This artifact is optional — produce it when:
> - The user explicitly asks for a "cinematic", "experience", "journey", or
>   "walkthrough"
> - SPEC § 12 assumptions set `experience: true`
> - The process has a clear dramatic moment and a seller will present live
>
> Skip when not requested. The demo-deck.html is the primary customer-facing
> artifact and is sufficient for most engagements.

> ⚠️ **Bespoke per process — not a template.** The single biggest mistake in
> `experience.html` generation is reusing the same 4-act layout for every
> process. The 4-act narrative scroll is the right paradigm for KYC; it is
> *not* the right paradigm for a Kanban-shaped order-fallout flow, a
> graph-shaped network-fault triage, or a geography-shaped supplier-risk
> monitor. Each process gets its own visual paradigm derived from its
> protagonist, artifact, and moment of truth. The cinematic toolkit (GSAP,
> palettes, transitions) is a **kit of parts** — not a recipe to fill.

**The bespoke design discipline:**

1. **Extract the process DNA** from SPEC.md / AGENTS.md / demo-deck.html:
   protagonist, artifact, moment of truth, backlog number, hard guardrail.
2. **Pick the visual paradigm** from the catalog (or invent a new one).
   Examples in the reference doc: 4-act narrative scroll · live topology
   graph · live Kanban pipeline · world dot-density map · dossier binder ·
   dispatch console split · ledger + regulatory clock · editorial campaign
   cover · magazine spread · conveyor belt · tender document compose · CAD
   blueprint annotated · control-room dual-dashboard.
3. **Compose three felt movements:** density that hurts → zoom into one →
   the wave processed (with humans in the loop). Land softly on a trust panel.
4. **Use the cinematic toolkit** (GSAP 3.12.5 + ScrollTrigger from CDN, **no
   `defer`**, inline head gating script with 2.5s fallback, mandatory
   `prefers-reduced-motion: reduce` override) — pick 3-5 motion primitives
   that fit your paradigm (entrance staggers, scroll-scrub, pin-and-scroll,
   SVG path drawing, color crossfade, camera pull-back).
5. **Land on a trust panel** (visual inversion, 6 pillars with BR-XXX badges,
   skill catalog from manifest.json, 3 CTAs to demo-deck/SPEC/back).

**Required validation (mandatory before declaring done):**

- HTMLParser parses with zero errors
- Whitelabel deny-list grep returns zero hits (file is customer-facing) —
  including process-domain vendor or product names for the selected industry
- **Bespoke check:** no `id="act-1"`..`"act-4"` (those are KYC's), no
  `giant-counter` element (KYC's signature), no copy-of-KYC color palette
  unless the process is KYC
- Playwright at 1440×900: the **signature interaction** of your paradigm
  visibly works (counter scrubs / topology heals / pages assemble / dashboard
  transitions / map heats), bidirectional scroll works, reduced-motion
  honored
- `demo-deck.html` slide 5 (live-demo cue) explicitly invites the live agent
  invocation; experience.html stands alone as a post-meeting leave-behind
  (no cross-CTA needed)
- Root catalog `index.html` has "🎬 Experience" button on the process card

**Read the full playbook:** [`references/experience-template.md`](references/experience-template.md) —
includes the bespoke design discipline, the paradigm catalog with 13
exemplars, the cinematic toolkit (CDN scripts, head gating script,
reduced-motion override, color palettes, typography palettes, GSAP motion
vocabulary, transition layer), the whitelabel deny-list, the validation
checklist, and the anti-pattern list (do-not-reuse-act-IDs,
do-not-reuse-giant-counter, do-not-blend-paradigms, etc.).

#### 9. `specs/dashboard/` — Interactive Workshop App (optional)

For deeper workshops, generate a small React app that lets users explore and edit
the spec interactively:

```
specs/dashboard/
├── index.html          # Entry point
├── package.json        # Dependencies (react, react-dom, vite)
├── src/
│   ├── App.jsx         # Main layout
│   ├── FlowDiagram.jsx # Interactive process flow
│   ├── RulesPanel.jsx  # Business rules with search/filter
│   ├── DataModels.jsx  # Entity schemas with field details
│   ├── Systems.jsx     # Integration status (mock/real toggle)
│   └── spec-data.json  # Parsed spec data (from SPEC.md)
```

Run with `npm install && npm run dev`. This is **optional** — only generate when
the user asks for an interactive dashboard or workshop tool.

#### 10. `specs/prep-guide.html` — Seller Prep Guide

> [!WARNING]
> **INTERNAL / MICROSOFT CONFIDENTIAL.** This file is for the seller only — do NOT
> share with the customer or include in any code repository shared externally.
> Add `specs/prep-guide.html` to `.gitignore` if the repo may be shared.

Generate as a **self-contained HTML file** (same delivery shape as `demo-deck.html` — opens in browser,
can be saved as PDF via Print → Save as PDF). Sellers can't read markdown.

A lean companion document for the person presenting the demo. Helps them prepare
for the customer conversation, anticipate questions, and suggest next steps.

**UX requirements (mandatory):**

1. **Dual-mode toggle** — sticky bar at top with 🎤 Seller / 🔧 SE pills.
   Seller mode hides all `se-only` blocks; SE mode shows and auto-opens them.
   See Cross-cutting Pattern 3 for the JS/CSS pattern. Mode persists via
   `sessionStorage`.

2. **Sticky sidebar TOC** — fixed left nav with section links (`§1 Summary`,
   `§2 Demo`, `§3 Questions`, etc.). Scroll-spy highlights the active section
   in the brand accent color. Smooth-scroll on click. Give each `<section>` an
   `id` attribute. Hides on mobile (`@media max-width: 900px`). Main content
   offset with `margin-left: 200px` to clear the TOC.

3. **Font sizing discipline** — the prep-guide is read on a **secondary
   (non-projected) screen** at arm's length. Minimum sizes:
   - Body: ≥ 20px, line-height ≥ 1.6
   - Demo flow steps: ≥ 18px
   - Minimum anywhere in the document: 14px
   - **Exception:** confidentiality banner stays small (12px, compact padding)
     — it's chrome, not content. Do NOT let bulk font-size upgrades inflate it.

4. **Seller-visible product grid** — in the Architecture section, render a
   6-card emoji grid of Azure product names sellers can pitch. These are
   the services they sell, not engineering detail:
   ```
   🤖 Microsoft Foundry    🔍 Azure AI Search    💬 Teams + Copilot
   🗄️ Cosmos DB            📊 App Insights       🔐 Entra ID
   ```
   Each card: emoji + product name + one-line value proposition. The full
   architecture diagram (ACA, MCP, UAMI, Bicep, OTel) goes in a `se-only`
   block below the grid. Sellers see product names; SEs see the wiring.

5. **No tech jargon outside `se-only`** — in Seller mode, the prep-guide
   MUST NOT show: MCP, Responses API, UAMI, DefaultAzureCredential, ACA,
   Bicep, azd, gpt-5.x model names, Container Apps, FastMCP, OTel,
   region labels. These are all legitimate in `se-only` blocks. The seller
   view shows product names (Foundry, AI Search, Teams, Cosmos, Entra)
   and business outcomes only.

6. **Emojis on demo flow steps** — each step in the `<ol class="flow-list">`
   should carry a leading emoji for visual scanning:
   🎯 Open / 🖥️ Workspace / 🗺️ Journey / 🛡️ Vulnerability / 📊 Analytics /
   📋 Audit / 🎬 Close. The prep-guide is a glance-document, not a novel.

**Sections** (in this order; numbering matters because sellers scan top-to-bottom):

0. **Demo Entrypoint** *(placeholder pre-deploy)* — emit as a
   `<section id="demo-entrypoint">` with the literal placeholder text
   *"[populated by `threadlight-deploy` Phase 6.7 once `azd up` returns
   clean: workspace URL, Teams sideload + manifest .zip path, Copilot
   Studio agent ID + install link, Foundry playground URL]"*. Wrap the
   filled-in version in `<details class="se-only">` (cross-cutting
   Pattern 3) so the seller's main view stays clean and only opens
   when they need the URL to share. Without this placeholder section,
   sellers in Cowork pre-deploy have no visual map for where the demo
   actually runs from.

0.5. **What's deployed (MVP capabilities)** — emit as a
    `<section id="mvp-capabilities">` panel above the Demo Script.
    One-screen inventory of what the customer is actually getting:
    channels available (Teams / web / playground), sample data shape
    (*"X customer cases, Y journey documents, Z business rules"* —
    pull literal numbers from the generated mock data and SPEC § 3 BR
    count), the agent's tool surface (one-line per tool from
    AGENTS.md), expected response latency (*"30-60 seconds per
    answer"* — adjust based on tool surface), and any throttle limits
    to demo within (*"5-7 questions per warm period; 5-min cooldown
    between batches"* if the architecture has known platform
    throttles). Without this panel, sellers improvise off the Demo
    Script with no shared mental model of *what's behind the curtain*.

1. **Use Case Summary** — one paragraph: what the agent does, for whom, why it matters
2. **Demo Script** — the seller's runnable script for the call. **Generic by
   construction** (no FQDNs, no commands, no resource names) so it works
   even before `threadlight-deploy` has run, but **concrete enough that the
   seller can run it verbatim** in any agent surface that can accept the
   prompts (Foundry playground, post-deploy Teams, Cowork preview). The
   structure is the same five beats every time:

   1. **Opening hook** (≈30 seconds — say this *before* you type anything).
      One paragraph of customer-facing pain (named persona + the cost of
      *today*) and one tease of the *wow* moment the agent enables. Reuse
      the punchiest line from `specs/demo-deck.html` slide 3 (Friction) or
      slide 4 (The shift) speaker-notes.
      Write it in **direct quotes** so the seller can read it aloud
      verbatim.

   2. **Demo arc — 4–6 acts.** Each act is **one** of two shapes; pick the
      one matching SPEC § 8 Human Interaction:

      - **Chat-style act** (default — agent answers prompts in Teams, web,
        or Foundry playground). Each act MUST contain three labelled
        sub-blocks in this exact order:

        > **Type this:** `<pre><code>{literal prompt the seller types}</code></pre>`
        > **What you'll see:** {1–2 sentences naming **specific** data
        > points the agent will surface — entity names, numbers, deltas,
        > anomalies — drawn from SPEC § 5 sample data and SPEC § 3
        > business rules. NOT generic ("the agent shows performance")
        > but concrete ("JPS share decline 16.8% → 13.2%, distribution
        > 72% → 64%, BAT Pall Mall +4pp").}
        > **Say:** {one sentence the seller says *after* the response
        > lands, anchoring it to the BR-XXX value prop.}

        Source the literal prompt either from a SPEC § 9 happy-path
        scenario (S-XXX, variant=happy) **user input field** verbatim,
        or — once `threadlight-demo-data-factory` has run — from
        `tests/eval_dataset.jsonl`. **Never paraphrase.** The same
        string must score green in the eval run.

      - **Workspace-style act** (event-driven PoCs — adaptive cards,
        cron-triggered queues, no chat). Replace **Type this:** with
        **Click here:** describing the literal UI affordance ("click the
        topmost card in the Inbox", "press *Approve* on the green
        action gate"). Keep **What you'll see:** + **Say:** identical
        in shape and concreteness.

      Tag each act with **the BR-XXX it demonstrates** (small inline
      label) so the seller can cite it on demand. Example structure (do
      not copy the prose verbatim — generate from this PoC's SPEC):

      ```html
      <h3>Act 2 — Drill into the problem <small>BR-001, BR-002</small></h3>
      <div class="card">
        <strong>Type this:</strong>
        <pre><code>Show me Midlands performance in detail</code></pre>
        <strong>What you'll see:</strong> Account-level breakdown,
        JPS share decline (16.8% → 13.2%), distribution gaps
        (weighted distribution 72% → 64%), and BAT's Pall Mall
        gaining +4pp.<br>
        <strong>Say:</strong> "It's surfaced the distribution erosion
        and the competitive threat without being asked — that's the
        anomaly detection running against your business rules."
      </div>
      ```

      Do NOT name Azure resources, FQDNs, or CLI commands inside acts —
      `threadlight-deploy` Phase 6.7 injects a separate **"Live MVP
      Walkthrough"** appendix after `azd up` succeeds, with the workspace
      URL, Teams sideload steps, reset/eval/smoke commands.

   3. **Bonus acts** (≥ 4 extras — "use if time allows or customer asks").
      Group them into one card with short labels for the seller to scan.
      Cover at minimum:
      - 1–2 **competitive / depth prompts** drawn from S-XXX scenarios
        that didn't make the main arc (e.g., *"What are competitors X
        and Y doing in region Z?"*).
      - 1 **cross-cut prompt** that demonstrates a different BR than the
        main arc (e.g., promotion ROI, distribution gap analysis).
      - 1 **edge case — data freshness / provenance** prompt that shows
        the agent citing data vintages (e.g., *"How current are our X
        feeds for Y?"*).
      - 1 **edge case — out-of-scope / guardrail** prompt that shows the
        agent declining or scoping correctly (e.g., *"Which portfolio
        tier does {brand-not-in-portfolio} belong to?"*).
      Each bonus prompt needs only **Type this:** (no See/Say) — the
      seller improvises off the response.

   4. **Reveal moment** (say this after the last main act). One short
      paragraph that **quantifies the saved time** by contrasting
      manual-effort-today (from SPEC § 1 Problem Statement / § 9
      Functional success criteria) with the PoC time the seller just
      demonstrated. Anchor to the **primary KPI** in SPEC § 9. Almost
      always one of: SLA collapse (hours → minutes / days → seconds),
      policy hit-rate (cited rules in every decision), or scale-out
      (one analyst handling 10× the volume). Write in direct quotes.

   5. **Q&A handoff.** One sentence transitioning to the Discovery
      Questions below. Example: *"Now I'd like to understand how this
      would land in **your** environment — can I ask a few things
      about your current workflow?"*

   > **Style guidance.** Speak in second person to the seller ("you'll
   > type", "you'll say"). Each act ≤ 4 sentences across all three
   > sub-blocks. **What you'll see:** must reference at least one
   > entity name + one numeric data point from SPEC § 5 — without that,
   > the seller has no way to know whether the agent's response is
   > "right". Generic phrasing is the single biggest reason a prep-guide
   > fails on the morning of the demo.

3. **Discovery Questions** — 5-8 questions to deepen the conversation with the customer:
   - "What does this process look like today? Where are the bottlenecks?"
   - "Which systems hold the data the agent would need?"
   - "Who approves / escalates? What are the SLAs?"
   - Tailor to the domain and business rules
4. **Expected Objections** — 3-5 likely pushbacks and suggested responses:
   - "How do we trust the agent's decisions?" → point to human-in-the-loop + audit trail
   - "What about our legacy systems?" → point to mock MCP → real swap path
   - "How long to production?" → point to fast-PoC → deploy → eval pipeline
5. **Suggested Next Steps** — what to propose after the demo:
   - Connect real data sources (replace mocks)
   - Run evals with customer-provided test scenarios
   - Deploy to Citadel landing zone (if governed)
   - Expand to additional process variants

6. **Architecture: Microsoft services map** — emit as
   `<section id="ms-services-map">` wrapped in `<details class="se-only">`
   (this is SE/seller-handoff material — not customer-facing). Inventory
   of every Azure / M365 service the deployed PoC uses, with each one
   labelled *"Customer pays for: &lt;SKU&gt;"* so the seller can build
   the commercial conversation directly off the prep-guide. Hot-link
   each service name to the seller's price-list lookup (Azure Calculator
   URL with the SKU pre-selected if known). Without this panel, sellers
   asking *"what do they buy to take this to production?"* have to leave
   the demo and reverse-engineer the architecture from the resource
   group. Typical inventory: Foundry account (hosted agents + project),
   AI Search (KB), Cosmos DB (audit + sample data), ACA (MCP server +
   workspace UI), App Insights + LAW, Entra ID (UAMI), App Configuration.

> [!TIP]
> **For the SE who'll run the deploy or workshop:** `threadlight-local-test` is
> available for fast inner-loop iteration without `azd up`, and
> `threadlight-deploy` handles the full Foundry deployment **and back-fills the
> "Live MVP Walkthrough" section of this prep-guide** with the real URLs +
> commands once `azd up` returns clean. Mention these as options to the
> customer's technical contact — but don't force them; some demos go straight
> from the `demo-deck.html` talk to a steering-committee decision and never
> need the live-walkthrough section at all.

**Style:** Same dark theme as `demo-deck.html` (brand-cascade aware) but with an "INTERNAL USE ONLY" banner
at the top. Print-friendly (saves as clean PDF).

> This is intentionally lean — NOT a 14-section seller enablement deck.
> Just enough to prepare for the conversation.

> **Polish pass (optional but recommended).** Sellers read the prep-guide
> Demo Script aloud — even small AI-prose tells degrade credibility. After
> generating `prep-guide.html`, run [`gbb-humanizer`](../gbb-humanizer/)
> over the prose sections (Use Case Summary, the **Say:** lines inside
> each demo act, Q&A handoff). Use the pre-canned `gbb-seller-pitch.md`
> voice sample. **Do not** humanize the **Type this:** literal prompts,
> the **What you'll see:** data-point lists, BR-XXX tags, command blocks,
> or the live-walkthrough URLs that `threadlight-deploy` Phase 6.7
> back-fills — those are factual scaffolding, not prose.

#### Cross-cutting workspace UX patterns

These patterns apply to the workspace UI (`src/workspace/`) and are
mandatory for customer-facing PoCs with a web workspace surface.

**Streaming responses (mandatory).** The workspace MUST stream agent
responses progressively, not wait for the full response:

- Backend: SSE endpoint (`POST /api/invoke-stream`) that yields
  `data: {"type":"text","chunk":"..."}` deltas, tool-call status
  (`{"type":"tool","name":"...","count":N}`), and a final
  `{"type":"done","citations":[...],"vulnerability":...}` event.
- Frontend: `fetch()` + `ReadableStream` reader that appends text
  chunks to the message bubble as they arrive. Tool-call status
  badges (`🔧 tool_name (3)`) show during the tool phase.
- Fallback: if SSE fails, fall back to the non-streaming
  `/api/invoke` endpoint transparently.
- **Why mandatory:** agent responses take 30–90 seconds. A blank
  "Working..." screen for 60 seconds in 2026 is unacceptable UX.

**Clickable citation modals (mandatory).** Citation pills in the
agent's response MUST be clickable — opening a `<dialog>` modal with
the source ID, retrieval method, and version metadata. In production
the modal would deep-link to the source document in SharePoint or the
KM system; in PoC it shows the citation metadata with a note that
the deep-link is a V2 integration.

- Inline cite-pills: `<span class='cite-pill cite-pill--clickable'>`
- Sidebar source-cards (if present): same click → modal behavior
- Source panel: hidden until first response (no pre-filled placeholders)

**Collapsible visualization panels.** When the agent returns structured
data (journey flow, pain-point maps, score breakdowns), the workspace
renders an inline visualization (SVG diagram, chart, table). These
MUST be collapsible — a toggle bar shows the title + summary, click
to expand/collapse. Starts expanded on first render, stays in the
user's last toggle state.

### Step 6.5: Phase C — Demo Polish (mandatory for customer-facing PoCs)

> **Trigger**: SPEC § 12 does NOT carry `internal-no-demo: true`. The
> default is on. Phase C exists because a recent PoC discovered that
> "shipping a Foundry agent" is necessary-but-not-sufficient for landing
> the demo — the polish layer (deck + killer prompts + rehearsal + score
> card) is what turns a working agent into a successful customer moment.
> If you skip Phase C, the user will discover the gap mid-demo. Don't
> skip Phase C.

Phase C generates four artifacts in addition to the durable agent layer:

| # | Artifact | Audience | Section below |
|---|---|---|---|
| § 7 | `specs/demo-deck.html` | Live customer talk | already covered above |
| § 11 | `tests/killer-prompts.md` | Sellers (drives `STARTER_N` env vars) | next |
| § 12 | `specs/demo-rehearsal.md` | The seller delivering the talk | next |
| § 13 | `tests/eval-summary.md` | Compliance / FCA-style reviewers | next |

#### 11. `tests/killer-prompts.md` — Curated Wow-Prompts (MANDATORY)

5–10 hand-picked prompts that surface the highest-impact behaviour of the
deployed agent, ranked K1/K2/K3/… by demo wow-factor. They're the demo's
emotional payload — generic starter prompts ("Tell me about X") burn the
opening seconds; killer prompts trigger the "oh — *that's* what this
thing does" reaction in the first 15 seconds of each beat.

**Source.** Highest-scoring happy-path scenario per BR-XXX in
`tests/eval_dataset.jsonl` — same literal string that scored green in
evals, copied verbatim. **Do not invent prompts.** Eval-validated prompts
are pre-tested for citation count, latency, and refusal rate.

**Row schema** (markdown table):

| Field | Purpose |
|---|---|
| `Rank` | K1, K2, K3, … in order of expected wow-factor |
| `Prompt` | Verbatim literal text — same string scored green in evals |
| `BR-XXX` | Which business rule it demonstrates (one only — the dominant one) |
| `Expected anchors` | ≥ 1 named entity + ≥ 1 numeric data point the response must surface |
| `Wow line` | The single sentence the seller says after the agent finishes (anchored to the BR — e.g. "*That citation is the FCA pack*") |
| `Surfaces` | Demo surfaces this prompt should be tried on — Teams · Workspace · Foundry playground · M365 Copilot Chat |

**Auto-wiring.** This file feeds `agent.yaml` env vars
`STARTER_{1,2,3}_TITLE` + `STARTER_{1,2,3}_PROMPT` (Teams chip rendering
limits titles to ~30 chars). Use the keeper script
`infra/scripts/refresh_killer_prompts.py` (emitted by this skill) — it
parses `tests/killer-prompts.md` and writes the env-var block into
`agent.yaml` idempotently. The keeper script is wired into
`threadlight-deploy` Phase 6.7 ("Live MVP Walkthrough" back-fill) so the
deployed agent's home surface picks up changes automatically on the next
`azd up`. Wow-prompts can then evolve post-demo without hand-editing the
deploy manifest.

> **Target file clarification.** The `STARTER_{1,2,3}` env vars are injected into
> `agent.yaml` (the ContainerAgent definition under `environment_variables:`), NOT
> into `azure.yaml` (the azd project config). The `azure.yaml` `config.deployments`
> block does not carry runtime environment variables for hosted agents — those live
> in `agent.yaml`. The refresh script must target `agent.yaml` accordingly.

> **Shell portability.** Default to `shell: sh` (not `shell: pwsh`) for
> postprovision hooks that only run Python commands (`python scripts/...`).
> macOS development machines rarely have PowerShell installed, and `azd`
> silently fails extension loading when hooks reference an unavailable shell.
> Use `shell: pwsh` only when the hook contains PowerShell-specific syntax
> (e.g., `$env:VAR`, `Set-Content`, `-replace`). If the hook must run
> cross-platform, prefer Python scripts invoked via `python script.py`.

**Validation.** ≥ 3 rows (K1 minimum + K2 + K3 — the deck's live-demo
arc), each `Prompt` literal exists in `tests/eval_dataset.jsonl` (set
membership), each `BR-XXX` exists in `specs/SPEC.md` § 3 (set
membership), each `Expected anchors` row has ≥ 1 entity + ≥ 1 digit.

#### 12. `specs/demo-rehearsal.md` — Run-of-Show (MANDATORY)

Beat-by-beat stopwatch script for the seller delivering the live talk.
The deck (§ 7) is the *visual*; the rehearsal is the *choreography*.

**Required beats** (in order, each timestamped):

| Time | What | Purpose |
|---|---|---|
| **T-24h** | Bench check — `healthz` probe, `curl K1`, Teams ping, M365 picker | Catch overnight breakage early |
| **T-15 min** | Tab list — open every demo surface in a separate browser tab in the right order | One-glance "everything is up" |
| **T-5 min** | Agent warm-up — invoke each killer prompt once to clear cold-start cost | The audience never sees the first-token-after-cold-start delay |
| **T-0** | Hero → K1 → K2 → K3 → close | ≤ 8 minute total budget |
| **Backup paths** | When primary surface fails | Terminal `azd ai agent invoke` fallback + pre-rendered MP4 (see `auto-demo-producer` skill) |
| **Ship checklist** | Deck open, notes off, blackout key tested, lighting, mic, water | Pre-flight, ~T-2 min |

Each T-0 beat names the killer prompt verbatim, the slide it lands on,
the expected anchors the agent will return, and **one** spoken line the
seller delivers as the agent finishes (the "wow line" from
killer-prompts.md). This is the artifact the seller actually reads during
rehearsal — not the deck, not the prep-guide.

**Validation.** All six beat rows present, each killer prompt referenced
verbatim by rank, total T-0 beat budget ≤ 8 minutes, at least one backup
path documented per surface.

#### 13. `tests/eval-summary.md` — Human-Readable Scorecard (MANDATORY when evals have run)

A 1-page markdown scorecard derived from `tests/eval-results-*.jsonl`
that any non-engineer reviewer (compliance, FCA-style auditor, exec
sponsor) can read. The eval dataset is generated by this skill (in SPEC
§ 9.4) and run by `foundry-evals`; this scorecard is the *summary* of
that run, hand-curated because heuristic scorers produce false-negatives
that an experienced operator must adjudicate.

**Required sections:**

| Section | Content |
|---|---|
| Top-line | pass/fail per scenario class (happy / edge / error), latency P50/P95, zero-citation rate, refusal rate on in-corpus questions |
| K1/K2/K3 transcripts | Inline (full request + full response + citations panel) — the demo arc, evidence-grade |
| Adjudicated scenarios | Any scenario where the heuristic scorer disagreed with hand-review (with one-line rationale) |
| Sev-1 hypothesis | "What would Carl-grade fail look like" — e.g. cited but wrong version date = Sev-1 |
| Dataset hygiene | Any rows that need rewriting before next run (typos, ambiguous queries) |

**Validation.** Top-line numbers present, at least 3 transcripts inline,
no engineering jargon in the prose layer (a non-developer compliance
reviewer should be able to read the whole document).

### Step 7: Review

Walk through the generated structure with the user:
1. Explain each skill and which business rules it implements
2. Highlight mock systems that need real integration later
3. Explain the spec↔implementation boundary:
   - **`specs/`** = WHAT the business needs (reviewable by stakeholders)
   - **`src/agent/skills/` + `AGENTS.md`** = HOW the agent implements it
   - **Deploy artifacts** = generated separately by `threadlight-deploy`
4. Suggest next steps (test locally with `threadlight-local-test` if iterating; deploy with `threadlight-deploy` when ready; then evaluate with `foundry-evals`)

### Step 8: Auto-Review (mandatory)

After all files are generated, **automatically run a self-review** before presenting
the final summary. This is not optional — the skill generates a lot of content and
must catch its own mistakes.

**Review checklist:**

- [ ] **Visual validation (MANDATORY — not replaceable by code checks).** Open `specs/demo-deck.html` in a browser at 1440×900. Advance through all 11 slides with Space. Verify: no text overflow or card overlap, every slide readable at arm's length, big numbers visible as anchors, no cramped multi-column layouts with dense text. If Playwright is available (see `runtime.playwright_available` in SPEC § 12, set by the **Runtime capability probe** earlier in this skill), take a screenshot of slides 1 and 3 and inspect; otherwise this gate is **manual** and the contributor MUST do it before declaring done. **Battle-scar:** code-level validation (HTML parsing, class counting, grep patterns) is necessary but NOT sufficient — a recent PoC passed every automated gate but was visually broken (overlapping grids, walls of text, no breathing room). The browser is the final gate.
- [ ] Every BR-XXX in `specs/SPEC.md` § 3 is referenced by at least one skill's procedure
- [ ] Every tool contract in spec § 6 has a matching tool in AGENTS.md
- [ ] Every mocked system in spec § 5 has sample data in `specs/sample-data/`
- [ ] Every eval scenario (S-XXX) in spec § 9 references valid BR-XXX rules
- [ ] AGENTS.md skills table matches the actual `src/agent/skills/` directories
- [ ] `specs/manifest.json` matches the generated skills list and BR counts
- [ ] **`specs/demo-deck.html` exists** (mandatory unless SPEC § 12 carries `internal-no-demo: true`): HTMLParser passes, 10–13 `<section class="slide">` elements, speaker notes count == slide count (1:1 `data-for` mapping), all 4 keyboard chords wired (Space / F / S / B), `bg-{brand}-flood` panels ≥ 4 (friction + follow-up + close are the 3 mandatory; hero may be dark-cinematic), brandmark substitute present on slide 1 AND final slide (bookend), MS co-brand bar present on hero AND close, 18-symbol icon library present and all referenced via `<use href="#ico-XXX">`. See § 7 generation block + `references/demo-deck-template.md` for the full pattern.
- [ ] **`specs/overview.html` is either absent OR a redirect-only stub.** If a legacy `specs/overview.html` exists from an older generation, it MUST contain the literal markers `<meta http-equiv="refresh"` AND `location.replace('demo-deck.html')` and be ≤ 3 KB (the canonical migration stub). Divergent narrative content in overview.html FAILS — collapse it to the meta-refresh redirect per `references/demo-deck-template.md` § "Migration".
- [ ] **Migration grep (when upgrading from legacy `overview.html`).** Run `grep -rn 'overview.html' specs/ src/ README.md AGENTS.md` and verify zero hits outside of `specs/overview.html` itself. Common missed references: `experience.html` CTA links, `prep-guide.html` opening hook source, `README.md` architecture section. All must point to `demo-deck.html` after migration.
- [ ] **`specs/experience.html` if generated** (optional — only when user requested or SPEC § 12 sets `experience: true`): HTMLParser passes, whitelabel grep zero hits, **bespoke check passes (no `id="act-N"` reuse, no `giant-counter` reuse unless KYC)**, Playwright validates the paradigm's signature interaction (counter scrubs / topology heals / pages assemble / dashboard transitions / map heats) bidirectionally, `demo-deck.html` slide N-1 (Discussion) or N (Close) has a 🎬 reference link to the experience dossier, catalog index.html has Experience button
- [ ] **`specs/prep-guide.html` § "Demo Script" exists** with all five beats (Opening hook in direct quotes · Demo arc 4–6 acts · Bonus acts ≥ 4 · Quantified Reveal moment · Q&A handoff). For chat-style PoCs, **every** main-arc act must contain all three sub-blocks `<strong>Type this:</strong>` + `<strong>What you'll see:</strong>` + `<strong>Say:</strong>` (or `<strong>Click here:</strong>` for workspace-style). **What you'll see** must reference at least one entity name AND one numeric data point per act (grep each act for a digit; zero-digit acts fail). Each act tagged with the BR-XXX it demonstrates. **Bonus acts** card present with ≥ 4 prompts including ≥ 1 freshness/provenance edge case AND ≥ 1 out-of-scope/guardrail edge case. Reveal moment quantifies manual-effort-today vs PoC-time and cites the SPEC § 9 primary KPI. **Zero deploy-specific tokens** anywhere (no FQDNs, no `azd ` / `az ` / `python ` commands, no resource names) — those are reserved for `threadlight-deploy` Phase 6.7's "Live MVP Walkthrough" appendix.
- [ ] **Brand cascade rule applied** (Cross-cutting Pattern 1) — if a customer brand palette was declared in SPEC § 1 or captured during discovery (or sector-convention fallback from `references/brand-palettes.md`), grep that the brand accent hex IS present in the CSS of `demo-deck.html` AND `prep-guide.html` (and `experience.html` if generated). Structural neutrals (parchment, charcoal, navy, brass) must remain untouched. Deck-specific deep checks (Pattern 1 § "Deeper rules for demo-deck.html") additionally enforced: `bg-{brand}-flood` ≥ 4 panels with friction + follow-up + close mandatory (hero may be dark-cinematic), brandmark substitute markup, MS co-brand bar present.
- [ ] **Markdown modal pattern present** (Cross-cutting Pattern 2) — every `<a href="*.md">` in any generated HTML artefact has been rewritten to `<a data-md="*.md">` AND the host artefact contains the modal markup (`<script type="text/markdown">` blobs + JS registry + click delegate + renderer with fallback). No raw `.md` href links remain.
- [ ] **SE-only collapsibles applied** (Cross-cutting Pattern 3) — in `prep-guide.html`, every `<pre><code>` block containing `azd ` / `az ` / `python ` commands MUST be wrapped in `<details class="se-only">` with an audience pill summary. Sellers should see no engineering content in the default closed state.
- [ ] **Internal-jargon deny-list zero hits** (Cross-cutting Pattern 4) — grep `demo-deck.html` (and `experience.html` if generated) for every token in the baseline deny-list (MS internal product names, region/SKU labels, contributor PII, fabricated `_skill` / `_tool` identifiers) PLUS any `additional_denied_tokens` from SPEC § 12. Zero hits required. `prep-guide.html` is exempt. Record the grep result in the auto-review summary so the user can audit it.
- [ ] **Persona placement** (Cross-cutting Pattern 5) — if `experience.html` was generated, extract the set of persona first-names from it (the dossier where they belong). Grep `demo-deck.html` AND `prep-guide.html § Demo Script "Type this:"` prompts for any hit on that set. Zero hits required. Suggested fix: swap persona name → role descriptor from the same SPEC § 5 persona row. If `experience.html` was not generated, extract personas from SPEC § 5 directly for the same check.
- [ ] **Canonical tool naming** (Cross-cutting Pattern 6) — extract every tool name from `<code>` blocks, pill labels, and skill-chain SVG text nodes across `demo-deck.html`, `prep-guide.html` (and `experience.html` if generated). Set-diff against the AGENTS.md `Foundry tools required` table column 1 (plus any AGENTS.md § Tool display aliases). Zero out-of-set names required. Fabricated names (e.g. `load_skill`, `customer_knowledge_base_retrieve`) are the highest-frequency battle-scar — catch them here.
- [ ] **No-commitment closing** (Cross-cutting Pattern 7) — grep deck slides N-1 and N (Follow-up proposal + Thank you) (and the `experience.html` trust panel if generated) for banned phrases (`we'll build`, `by {date}`, `let's commit`, `next month`, `pick one journey`, any literal future date within 90 days of the generation timestamp). Zero hits required. The Thank-you slide MUST contain literal `Thank you.` and the MS × {Customer} co-brand bar; the Follow-up slide MUST have ≥ 3 step cards with concrete actions (not open questions); if any card text matches a banned phrase, fail.
- [ ] **`tests/killer-prompts.md` exists** (mandatory unless SPEC § 12 carries `internal-no-demo: true`) with ≥ 3 ranked rows (K1, K2, K3 minimum). Each `Prompt` literal exists verbatim in `tests/eval_dataset.jsonl` (the eval-validated set). Each `BR-XXX` exists in SPEC § 3. Each `Expected anchors` row has ≥ 1 named entity + ≥ 1 digit. `agent.yaml` carries `STARTER_{1,2,3}_TITLE` + `STARTER_{1,2,3}_PROMPT` env vars synced from this file by `infra/scripts/refresh_killer_prompts.py`.
- [ ] **`specs/demo-rehearsal.md` exists** (mandatory unless SPEC § 12 carries `internal-no-demo: true`) with all six required beat rows (T-24h, T-15min, T-5min, T-0, backup paths, ship checklist). T-0 budget ≤ 8 minutes total. Each killer prompt referenced verbatim by rank with its wow-line.
- [ ] **`tests/eval-summary.md` exists** when an eval run has produced `tests/eval-results-*.jsonl` (skip the gate gracefully if no eval results file exists yet — the dataset can be run later via `foundry-evals`). Top-line numbers present, ≥ 3 inline transcripts (K1/K2/K3), adjudicated scenarios documented when present.
- [ ] **`prep-guide.html` contains the three required structural placeholders** — `id="demo-entrypoint"` (filled by `threadlight-deploy` Phase 6.7), `id="mvp-capabilities"` (filled by this skill from the SPEC), `id="ms-services-map"` (filled by this skill from the deployment_manifest module selectors).
- [ ] **`prep-guide.html` dual-mode toggle present** — the file MUST contain a sticky mode-toggle bar with 🎤 Seller / 🔧 SE buttons, the `setGuideMode()` JS function, and CSS rules for `body.mode-seller details.se-only { display: none }`. In Seller mode, zero engineering tokens (MCP, Responses API, UAMI, azd, Bicep, DefaultAzureCredential, ACA, OTel, Container Apps, FastMCP, region labels, gpt-5.x model names) should be visible — grep the rendered Seller view.
- [ ] **`prep-guide.html` sidebar TOC present** — a `<nav class="toc">` with `position: fixed` links to each `<section id="sec-*">`. Scroll-spy JS highlights the active section. Main content offset with `margin-left` to clear the TOC.
- [ ] **`prep-guide.html` font sizing** — body font ≥ 20px, flow-list items ≥ 18px, no element below 14px. Exception: confidentiality banner (≤ 12px). The prep-guide is a second-screen document.
- [ ] **`prep-guide.html` seller product grid** — Architecture section has a seller-visible emoji card grid (6 cards: Foundry, AI Search, Teams+Copilot, Cosmos DB, App Insights, Entra ID). Full architecture diagram is inside a `se-only` block below the grid.
- [ ] **Workspace streaming endpoint exists** — `POST /api/invoke-stream` SSE endpoint present in `src/workspace/main.py`. Frontend uses `ReadableStream` progressive rendering with tool-call status badges. Fallback to `/api/invoke` on error.
- [ ] No hardcoded secrets, API keys, or personal data in any file
- [ ] Assumptions in spec § 12 are flagged clearly (especially fast-PoC defaults)

**If any check fails:** fix it before presenting the output to the user. Do not
ask the user to fix generated content — that's the skill's responsibility.

---

## Spec ↔ Agent Boundary

| Layer | Location | Audience | Purpose |
|-------|----------|----------|---------|
| **Specification** | `specs/` | Business stakeholders, architects | WHAT the process does — business rules, data models, success criteria |
| **Implementation** | `src/agent/skills/`, `AGENTS.md` | Developers, agent runtime | HOW the agent does it — skills, tools, operational contracts |
| **Deployment** | `container.py`, `Dockerfile`, etc. | DevOps, platform | WHERE it runs — generated by `threadlight-deploy`, not this skill |

The spec is durable and runtime-agnostic. You can derive different implementations
(Foundry hosted agent, GHCP SDK, standalone scripts) from the same spec.

---

## Reference Files

| File | Purpose | Status |
|------|---------|--------|
| `references/speckit-template.md` | Template for SpecKit specification documents (12 sections + abstract-vs-pure-coding contracts) | ✅ Included |
| `references/process-traits.md` | Composable trait catalog for process pattern detection | ✅ Included |
| `references/experience-template.md` | Bespoke cinematic `experience.html` design discipline + paradigm catalog | ✅ Included |
| `references/demo-deck-template.md` | Cinematic `demo-deck.html` talk-deck kit-of-parts (slide grammar, CSS tokens, JS controller, brandmark substitute, MS 4-color SVG, 18-symbol icon library, rejection anti-patterns) | ✅ Included |
| `references/brand-palettes.md` | Sector-convention fallback table (~30 well-known industry brand hex codes with citations) for Cross-cutting Pattern 1 when no logo URL captured | ✅ Included |
| `references/data-realism/README.md` | Per-industry demo-data realism rules (FSI, Retail, Telco, Mfg) | ✅ Included |
| `references/domains/` | Optional domain primers for industry-specific acceleration | ✅ Included |
| `references/skill-template.md` | Template for generated SKILL.md files | 📎 From the upstream reference set |
| `references/agents-template.md` | Template for generated AGENTS.md | 📎 From the upstream reference set |
| `references/compliance-checklist.md` | Privacy/legal/regulatory screening checklist | 📎 From the upstream reference set |

> **📎 Upstream references:** Some reference files live in the full reference set
> and are loaded when the skill is installed there. For standalone use from this repo,
> follow the SpecKit template structure — it embeds the compliance questions inline.

---

## Input contract / Output artifacts

**Input contract** — what this skill consumes:
- A free-form user description of a business process or use case (interview-driven Phase A)
- Optional domain primer at `references/domains/{domain}.md` (cherry-pick during interview)

**Output artifacts** — what this skill produces (the contract surface for every downstream skill):

| File | Consumed by | Purpose |
|------|-------------|---------|
| `specs/SPEC.md` § 5b | `foundry-mcp-aca` | External Systems & Mocks (MCP contract) — endpoint shape, tools, mock data scale, reset semantics |
| `specs/SPEC.md` § 7 | `foundry-iq` | Knowledge Sources — which corpora become Knowledge Bases |
| `specs/SPEC.md` § 7b | `foundry-doc-vision-speech` + `azure.yaml` | AI Services & Model Selection — model + version + capacity |
| `specs/SPEC.md` § 8 | `threadlight-hitl-patterns` | Action gates — Adaptive Card generation |
| `specs/SPEC.md` § 8b | `threadlight-workspace-ui` | Workspace shape — case-list / dashboard / console / kanban |
| `specs/SPEC.md` § 9 KPI table | `foundry-evals` continuous loop | BR → KPI mapping for week-over-week dashboards |
| `specs/SPEC.md` § 10b | `threadlight-event-triggers` | Receiver type + idempotency + dead-letter rule |
| `specs/SPEC.md` § 11b | `threadlight-deploy` Citadel handoff + `citadel-spoke-onboarding` | Governance posture — citadel.required flag |
| `specs/SPEC.md` § 11c | `azd-patterns` Bicep module library + `threadlight-deploy` composer | Tech stack module selectors — which Bicep modules to wire |
| `specs/SPEC.md` § 11d | `threadlight-demo-data-factory` | Demo data realism rules — volumes, distribution, golden cases |
| `specs/sample-data/{entity}.json` | `foundry-mcp-aca` Option D + `threadlight-demo-data-factory` | Seed data for mock MCP server |
| `specs/manifest.json` | `threadlight-deploy` | Machine-readable deployment contract |
| `specs/prep-guide.html` § "Demo Script" | `threadlight-deploy` Phase 6.7 | Runnable seller demo script (acts contain literal prompts + concrete expected data points + seller narration); deploy back-fills a separate "Live MVP Walkthrough" appendix with workspace URL / Teams sideload / reset / eval / smoke commands |
| `AGENTS.md` + `src/agent/skills/` | `threadlight-deploy` | Skill catalog + behavioral guidelines |

> If a section is missing or under-specified, the corresponding downstream skill
> will either fail or fall back to defaults. **Always populate every input contract
> at least minimally** — even if just `Citadel required: no` or `Triggers: on-demand only`.

---

## Design Principles

1. **Spec-first**: Always produce a durable specification before implementation artifacts
2. **Trait-based**: Detect process patterns dynamically from composable traits, not fixed archetypes
3. **Business rules are king**: Every skill, every eval scenario traces back to numbered BR-XXX rules
4. **Mock what you can't reach**: For inaccessible systems, define data models + sample data in the spec
5. **Clear boundaries**: Specs are business-facing; agents+skills are implementation-facing; deploy is separate
6. **Progressive discovery**: Start simple, branch by detected traits — don't overwhelm with questions
7. **Compliance by default**: Always screen for PII, secrets, regulatory, and retention
8. **Evidence-first**: All extracted data should include source references for auditability

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-deploy**](../threadlight-deploy/) | Consumes the SPEC + AGENTS.md + skills produced by this skill; turns them into a deployable Foundry hosted-agent project |
| [**threadlight-local-test**](../threadlight-local-test/) | **Optional fast inner-loop for SEs.** Run the design output locally (FoundryChatClient + FastMCP + workspace) without `azd up` — Cowork-friendly for iterating on tools and prompts before a customer workshop |
| [**threadlight-safe-check**](../threadlight-safe-check/) | Reads the `deployment_manifest{}` block authored under SPEC § 11c (this skill's responsibility) and gates design / pre-deploy / post-deploy completeness |
| [**foundry-observability**](../foundry-observability/) | Always layered into deploy from day one — App Insights + OTel telemetry across hosted agents, MCP, ACA jobs, workspace; closes the silent gap where `azd up` returns 0 but AppIn stays empty |
| [**foundry-iq**](../foundry-iq/) | **Default knowledge retrieval pattern** — every SPEC § 7 should declare a Knowledge Base with `Backing service: foundry-iq` unless the process has zero domain documents |
| [**foundry-doc-vision-speech**](../foundry-doc-vision-speech/) | Consumes SPEC § 7b AI Services & Model Selection — wires vision / DocIntel / Speech tools |
| [**threadlight-workspace-ui**](../threadlight-workspace-ui/) | Consumes SPEC § 8b Workspace UX — generates the operator workspace |
| [**threadlight-hitl-patterns**](../threadlight-hitl-patterns/) | Consumes SPEC § 8 Action Gates — generates Adaptive Cards + audit trail for the seven canonical gates |
| [**threadlight-event-triggers**](../threadlight-event-triggers/) | Consumes SPEC § 10b Triggers — generates ACA Job / Function / consumer receivers |
| [**threadlight-demo-data-factory**](../threadlight-demo-data-factory/) | Consumes SPEC § 11d Demo Data + the `references/data-realism/` industry rules — generates realistic demo data |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | Consumes SPEC § 5 / § 5b — wraps mocked systems behind MCP |
| [**foundry-evals**](../foundry-evals/) | Consumes SPEC § 9 KPI table — runs continuous evaluation loop |
| [**citadel-spoke-onboarding**](../citadel-spoke-onboarding/) | Consumes SPEC § 11b Governance Posture — opt-in Citadel handoff after initial deploy |
| [**azd-patterns**](../azd-patterns/) | Composable Bicep module library that all module-emitting skills above feed into |
| [**gbb-pptx**](../gbb-pptx/) | **When a 1-slider PPTX leave-behind is requested** after the deck-led demo (exec brief, steering committee handout, asynchronous follow-up to non-attendees). Complements the deck, not a replacement. |
| [**auto-demo-producer**](../auto-demo-producer/) | **When a narrated 90s MP4 backup is needed** — pre-rendered video that survives flaky agent surfaces, hotel wifi, and last-minute outages. Lists in `specs/demo-rehearsal.md` § "Backup paths". |
| [**gbb-humanizer**](../gbb-humanizer/) | **Polish pass** for the prose-heavy artifacts this skill generates (`demo-deck.html` speaker-note prose, `experience.html` lede paragraphs, `prep-guide.html` Demo Script narration). 29 patterns from Wikipedia's "Signs of AI writing" + GBB-specific section-aware mode + density-preserving guardrail so domain rule-of-three lists survive |
