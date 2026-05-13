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
  specification, speckit, define a customer scenario, mock backend systems.
  DO NOT USE FOR: running existing skills, executing code, deploying (use threadlight-deploy),
  general Q&A, internal Microsoft tooling automation, generic chatbot prototyping.
metadata:
  version: "1.1.0"
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
  stats, and a customer-facing `specs/overview.html` you can screen-share on the
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
> abstract to generic "the customer"); attach the generated `specs/overview.html`
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
- ✅ **`specs/overview.html`** — seller pitch page (always)
- ✅ **`specs/experience.html`** — bespoke cinematic customer journey (always — every PoC is a demo by definition; **see Step 6 § 8**). Skip ONLY when spec § 12 assumptions explicitly flag `internal-no-demo: true`.

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

#### 7. `specs/overview.html` — Seller Pitch Page

Generate a **single self-contained HTML file** (no dependencies, opens in any browser)
that visualizes the SpecKit spec for non-technical audiences. Use for seller pitches,
customer walkthroughs, and stakeholder alignment.

**Narrative arc** — the page should tell a story, not just list spec content:

1. **The Pain** — open with the customer's current problem (from spec § 1 goals + § 3 pain points implied by business rules). Make it specific to their domain.
2. **The Process** — show the step-by-step flow as a visual diagram (from spec § 2). Color-code by actor type (agent / human / system).
3. **The Agents at Work** — show which skills handle which steps (from the generated skills). This is the "watch the team solve the problem" moment.
4. **The Architecture** — reveal the tools, integrations, and data sources that make it possible (from spec § 5, § 6, § 7). Show mock vs real status.
5. **The Outcomes** — connect to success criteria and expected improvements (from spec § 9). Quantify if possible.

**If target persona was captured**, adapt emphasis:
- CIO/CTO → expand architecture section, add governance notes
- CFO → lead with outcomes/ROI, show cost of current vs automated
- COO → expand the process flow, show before/after
- CISO → highlight compliance (spec § 11), audit trail, data boundaries

**Must include:**
- Process name, domain, and one-line description as hero section
- Process flow as a visual step diagram (boxes + arrows, color-coded by actor type)
- Business rules count and summary (collapsible detail)
- Data models as entity cards (field names, types — no validation details)
- System integrations table (name, direction, status badge: ✅ available / 🔶 mock)
- Eval scenarios count with category breakdown (happy-path / edge-case / error)
- Skill catalog with purposes

**Style:**
- Dark professional theme (dark navy background, accent blues/cyans)
- Responsive layout — works on laptop screens and projector
- No external CDN, fonts, or scripts — everything inline
- Print-friendly (can be saved as PDF from browser)

#### 8. `specs/experience.html` — Bespoke Cinematic Customer Journey (MANDATORY)

A second seller-facing artifact that complements `overview.html`. Where the
overview is a **brief**, the experience is a **bespoke journey** that makes
the customer feel the pain, the intervention, the outcome, and the trust
posture of *this* process — through visuals native to *its* domain.

> **Generate this for every PoC, period.** Threadlight's curation premise
> ("we deliver fewer processes, but reliably and beautifully") demands a
> cinematic artifact for every process — there is no such thing as a
> threadlight PoC without an `experience.html`. The skill must NOT wait
> for the user to say "demo" / "cinematic" / "walkthrough" — those words
> are implicit in the request to design a threadlight process.
>
> **The only valid skip** is when SPEC § 12 assumptions explicitly carry
> `internal-no-demo: true` (e.g., a pure backend automation with no
> seller motion). Even then, log the skip in your hand-off message so
> the user can override.

> ⚠️ **Bespoke per process — not a template.** The single biggest mistake in
> `experience.html` generation is reusing the same 4-act layout for every
> process. The 4-act narrative scroll is the right paradigm for KYC; it is
> *not* the right paradigm for a Kanban-shaped order-fallout flow, a
> graph-shaped network-fault triage, or a geography-shaped supplier-risk
> monitor. Each process gets its own visual paradigm derived from its
> protagonist, artifact, and moment of truth. The cinematic toolkit (GSAP,
> palettes, transitions) is a **kit of parts** — not a recipe to fill.

**The bespoke design discipline:**

1. **Extract the process DNA** from SPEC.md / AGENTS.md / overview.html:
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
   skill catalog from manifest.json, 3 CTAs to overview/SPEC/back).

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
- `overview.html` has hero CTA linking to `experience.html`
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

Generate as a **self-contained HTML file** (same as overview.html — opens in browser,
can be saved as PDF via Print → Save as PDF). Sellers can't read markdown.

A lean companion document for the person presenting the demo. Helps them prepare
for the customer conversation, anticipate questions, and suggest next steps.

**Sections:**

1. **Use Case Summary** — one paragraph: what the agent does, for whom, why it matters
2. **Demo Script (high-level)** — the narrative arc the seller will follow on the call.
   This is **generic by construction** — no URLs, no commands, no resource names. It must
   be useful even when `threadlight-deploy` hasn't run yet (Cowork seller, steering-
   committee deck export, sandbox not yet provisioned). The four beats:

   1. **Opening hook (≈30s)** — one line of customer-facing pain (the named persona +
      the cost of *today*) and one line teasing the *wow* moment the agent enables.
      Reuse the punchiest line from `specs/overview.html` § "Why this matters".
   2. **Demo arc (3–5 acts)** — derive each act from a SPEC § 9 happy-path scenario
      (S-XXX where variant=happy) crossed with a SPEC § 8 Human Interaction channel.
      Phrase each act as **what to click + what to say**, not as commands. Example:
      - *Act 1 — Trigger:* "Open the workspace and drop in a fresh case (or wait
        for the cron to fire)." Say: "the agent picks this up the same way it would
        in production — no manual prompt."
      - *Act 2 — Reasoning:* "Show the workspace as the agent reads the case,
        calls its tools, and updates the timeline." Say: "every step traces back
        to BR-{NNN} — nothing magical."
      - *Act 3 — Action gate:* "Approve / reject the adaptive card in Teams." Say:
        "the agent never acts without a human in the loop on the hard calls."
   3. **Reveal moment** — the single beat that proves the BR-XXX value prop. Almost
      always one of: SLA collapse (hours → minutes), policy hit-rate (cited rules in
      every decision), or scale-out (one analyst handling 10× the volume). Pick the
      one that maps to the **primary KPI** in SPEC § 9.
   4. **Q&A handoff** — one sentence transitioning to the Discovery Questions below.
      Example: "Now I'd like to understand how this would land in *your* environment —
      can I ask a few things?"

   > **Style guidance for the generated acts:** speak in second person to the seller
   > ("you'll click", "you'll say"), keep each act ≤ 3 sentences, tag each act with
   > the BR-XXX it demonstrates so the seller can cite it on demand. Do NOT name
   > Azure resources, FQDNs, or CLI commands here — `threadlight-deploy` Phase 6.7
   > injects a separate **"Live MVP Walkthrough"** section after `azd up`
   > succeeds, with the concrete URLs / sample queries / sideload steps. Keeping
   > this section deploy-agnostic is what lets the seller use the prep-guide on
   > calls before any infrastructure exists.

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

> [!TIP]
> **For the SE who'll run the deploy or workshop:** `threadlight-local-test` is
> available for fast inner-loop iteration without `azd up`, and
> `threadlight-deploy` handles the full Foundry deployment **and back-fills the
> "Live MVP Walkthrough" section of this prep-guide** with the real URLs +
> commands once `azd up` returns clean. Mention these as options to the
> customer's technical contact — but don't force them; some demos go straight
> from `overview.html` to a steering-committee decision and never need the
> live-walkthrough section at all.

**Style:** Same dark theme as overview.html but with an "INTERNAL USE ONLY" banner
at the top. Print-friendly (saves as clean PDF).

> This is intentionally lean — NOT a 14-section seller enablement deck.
> Just enough to prepare for the conversation.

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

- [ ] Every BR-XXX in `specs/SPEC.md` § 3 is referenced by at least one skill's procedure
- [ ] Every tool contract in spec § 6 has a matching tool in AGENTS.md
- [ ] Every mocked system in spec § 5 has sample data in `specs/sample-data/`
- [ ] Every eval scenario (S-XXX) in spec § 9 references valid BR-XXX rules
- [ ] AGENTS.md skills table matches the actual `src/agent/skills/` directories
- [ ] `specs/manifest.json` matches the generated skills list and BR counts
- [ ] `specs/overview.html` renders without errors (valid HTML structure)
- [ ] **`specs/experience.html` exists** (mandatory unless SPEC § 12 carries `internal-no-demo: true`): HTMLParser passes, whitelabel grep zero hits, **bespoke check passes (no `id="act-N"` reuse, no `giant-counter` reuse unless KYC)**, Playwright validates the paradigm's signature interaction (counter scrubs / topology heals / pages assemble / dashboard transitions / map heats) bidirectionally, overview.html has 🎬 CTA, catalog index.html has Experience button
- [ ] **`specs/prep-guide.html` § "Demo Script (high-level)" exists** with all four beats (Opening hook · Demo arc · Reveal moment · Q&A handoff), 3–5 acts, each act tagged with the BR-XXX it demonstrates, **and contains zero deploy-specific tokens** (no FQDNs, no `azd ` / `az ` / `python ` commands, no resource names) — those are reserved for `threadlight-deploy` Phase 6.7's "Live MVP Walkthrough" injection
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
| `specs/prep-guide.html` § "Demo Script (high-level)" | `threadlight-deploy` Phase 6.7 | Generic seller demo script — deploy back-fills a separate "Live MVP Walkthrough" section with concrete URLs / sample queries / sideload steps |
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
