---
name: threadlight-design
description: >
  Spec out any business process or customer use case, then generate agent architecture
  (AGENTS.md + Skills). Produces a durable SpecKit specification first (process flow,
  business rules, data models, tool contracts, mock data), then derives implementation
  artifacts from the spec. Works for any domain — CX front desks, document processing,
  content research, backend automation, monitoring, reporting, and beyond.
  USE FOR: design a process, spec out a use case, create agent architecture, automate a
  workflow, threadlight design, skill factory, business process specification, speckit,
  define a customer scenario, mock backend systems, design an agent for any workflow.
  DO NOT USE FOR: running existing skills, executing code, deploying (use threadlight-deploy),
  general Q&A.
---

# Threadlight Design

Turn any business process or customer use case into a **durable specification** (SpecKit)
and then derive **AGENTS.md + Skills** from it — ready for development and deployment.

## When to Use

Invoke this skill when the user wants to:
- Spec out a business process or customer scenario (any domain)
- Design agent architecture for a workflow
- Create a structured skill folder with formal specification
- Mock backend systems they can't access yet (SAP, CRM, corporate DBs)
- Turn vague requirements into a concrete, reviewable spec

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

   > **Fast-PoC default:** If the user doesn't know yet, assume **stateless** and
   > flag in spec § 12 Assumptions: "Assumed stateless — review for case lifecycle needs."

8. **Does the agent take consequential actions?** (Action Criticality trait)
   - Read-only — only reads/analyzes data
   - Reversible writes — creates/updates data that can be undone
   - Irreversible actions — payments, approvals, notifications, external writes

   > **Fast-PoC default:** If the user doesn't know yet, assume **read-only** and
   > flag in spec § 12: "Assumed read-only — review before adding write/approval actions."

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
3. **Business Rules** — numbered BR-XXX, each with condition/action/exception
4. **Data Models** — all entities with field-level schemas and system of record
5. **System Integrations** — each external system, direction, auth, availability (including **mock** flag)
6. **Tool Contracts** — abstract tool definitions (not bound to any runtime)
7. **Knowledge Sources** — reference documents, policies, search indexes
8. **Human Interaction Points** — approvals, escalations, conversational flows (if any)
9. **Success Criteria** — functional, performance, quality targets + evaluation scenarios (S-XXX linked to BR-XXX)
10. **Trigger & Run Model** — how/when the process executes, volume, SLA
11. **Security, Compliance & Governance** — PII, auth, retention, regulatory, audit
12. **Assumptions & Open Questions** — what's given, what needs stakeholder input

#### `specs/sample-data/{entity}.json` — Mock data (for systems marked "mock")

For each entity in § 4 Data Models where the backing system is marked "mock" in § 5:
- Generate 5-10 realistic sample records matching the schema
- Include varied data (different values, edge cases, some optional fields missing)
- Add a `_meta` field with generation date and schema version

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

2. **Create an orchestrator when:**
   - There are 3+ domain skills
   - The process flow has decision branches or parallel paths
   - There's a defined order of operations across skills

3. **Human interaction points → dedicated handling:**
   - Each approval/escalation flow from spec § 8 maps to approval logic in the relevant skill
   - Conversational interaction points may warrant a dedicated skill

4. **Knowledge sources → Foundry IQ or MCP:**
   - **Documents, policies, regulations, product docs** (spec § 7) → **Foundry IQ**
     (Azure AI Search with agentic retrieval — query planning, multi-hop, citations).
     See `foundry-iq` skill.
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
   - [ ] No orphan skills — every skill is reachable from the orchestrator or a user trigger

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
  - {skill-3}: {purpose} (orchestrator)

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
  }
}
```

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

#### 8. `specs/dashboard/` — Interactive Workshop App (optional)

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

### Step 7: Review

Walk through the generated structure with the user:
1. Explain each skill and which business rules it implements
2. Highlight mock systems that need real integration later
3. Explain the spec↔implementation boundary:
   - **`specs/`** = WHAT the business needs (reviewable by stakeholders)
   - **`src/agent/skills/` + `AGENTS.md`** = HOW the agent implements it
   - **Deploy artifacts** = generated separately by `threadlight-deploy`
4. Suggest next steps (test locally, deploy, iterate)

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
| `references/speckit-template.md` | Template for SpecKit specification documents | ✅ Included |
| `references/process-traits.md` | Composable trait catalog for process pattern detection | ✅ Included |
| `references/domains/` | Optional domain primers for industry-specific acceleration | ✅ Included |
| `references/skill-template.md` | Template for generated SKILL.md files | 📎 From upstream `threadlight-skills` repo |
| `references/agents-template.md` | Template for generated AGENTS.md | 📎 From upstream `threadlight-skills` repo |
| `references/compliance-checklist.md` | Privacy/legal/regulatory screening checklist | 📎 From upstream `threadlight-skills` repo |

> **📎 Upstream references:** Some reference files live in the full `threadlight-skills` repo
> and are loaded when the skill is installed there. For standalone use from this repo,
> follow the SpecKit template structure — it embeds the compliance questions inline.

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
