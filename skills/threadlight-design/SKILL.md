---
name: threadlight-design
description: >
  Take a business process or personal automation request and produce a properly-structured
  folder with AGENTS.md, flat GitHub Copilot Skills (.github/skills/*/SKILL.md), and a
  Foundry deployment manifest. Designed for Microsoft Foundry hosted agent deployment.
  USE FOR: design a process, automate a workflow, create skills for X, build an agent for Y,
  turn this process into skills, threadlight design, process automation, skill factory,
  agent design, workflow automation, competitive intelligence setup, data pipeline design,
  monitoring system design, reporting automation.
  DO NOT USE FOR: running existing skills, executing code, general Q&A.
---

# Threadlight Design

Turn any business process or personal automation need into a properly-structured folder of
GitHub Copilot Skills + AGENTS.md, ready for Microsoft Foundry hosted agent deployment.

## When to Use

Invoke this skill when the user wants to:
- Design a new process automation from scratch
- Turn an existing manual workflow into agent-powered skills
- Create a structured skill folder for a business task
- Design an agent system for competitive intelligence, monitoring, reporting, etc.
- Set up a Foundry-deployable agent workflow

## Workflow Overview

```
Clarify Purpose → Discover → Feasibility + Architecture → Generate + Review
```

---

## Phase 1: Clarify Purpose

**Goal**: Understand what the user wants to automate. Be helpful, not gatekeeping.

### Ask the user:

> What process or workflow would you like to automate? Give me a brief description
> of what it does, what triggers it, and what outcome you expect.

### Guidance:
- Accept any business process, personal automation, or workflow systematization request
- Help the user articulate their need if they start vague — ask clarifying follow-ups
- Only gently redirect if the ask is clearly unrelated (e.g., "write a poem", "solve this math problem")
- It's fine to be broad at this stage — discovery will sharpen scope

### Capture:
- **Process name** (suggest one if user doesn't provide)
- **One-line description**
- **Domain** (competitive intelligence, HR, finance, operations, marketing, R&D, etc.)

---

## Phase 2: Discover

**Goal**: Progressive interview to understand the full process. Start simple, branch as needed.

### Core Questions (always ask):

1. **What triggers this process?**
   - Schedule (daily, weekly, on-demand)?
   - Event (new data, user request, webhook)?
   - Manual invocation?

2. **Where does data come from?**
   - Websites (→ Browser Automation / Playwright)
   - APIs (→ OpenAPI tool)
   - Databases (→ MCP or Azure AI Search)
   - Files/documents (→ File Search)
   - Manual input from user
   - Corporate systems (SharePoint, Teams, etc.)

3. **What's the data availability?**
   - **Public & accessible** — data is freely available, no auth needed
   - **Auth required** — APIs or sites that need credentials/tokens
   - **Internal only** — corporate databases, SharePoint, internal APIs
   - **No data yet** — need to mock data for development and testing

   > **If user has no real data sources yet:** Offer to generate mock data as JSON
   > files in `config/mock-data/` with realistic sample records matching the expected
   > schema. This lets the agent be developed and tested locally before real sources
   > are connected.
   >
   > **Mock data files:**
   > - `config/mock-data/{source-name}.json` — sample records per data source
   > - `config/mock-data/README.md` — explains the mock data structure and how to
   >   replace it with real data or an MCP server connection
   >
   > **Migration note:** When real data becomes available, skills can be updated to
   > call an MCP server instead of reading local JSON files. The skill's procedure
   > section should document both paths (local file fallback vs MCP tool call).

4. **What happens to the data?**
   - Extract specific fields
   - Compare across sources
   - Summarize / condense
   - Transform / normalize
   - Detect changes from last run
   - Generate visualizations

5. **What gets produced?**
   - Reports (Markdown, PPTX, PDF)
   - Structured data (JSON, CSV)
   - Notifications / alerts
   - Dashboard updates
   - API calls to other systems

6. **Who consumes the output?**
   - Internal team / stakeholders
   - External clients
   - Other systems / APIs
   - Dashboard / BI tool

### Archetype Detection

Based on answers, identify the primary pattern (see `references/process-archetypes.md`):

| If data comes from... | And the goal is... | Primary archetype |
|-----------------------|--------------------|--------------------|
| Websites | Extract & compare | **Web Intelligence** |
| Websites / APIs | Detect changes & alert | **Data Monitoring** |
| Documents / files | Extract & summarize | **Document Processing** |
| APIs / systems | Transform & sync | **API Integration** |
| Multiple sources | Analyze & report | **Reporting & Analysis** |
| Web + databases | Research & synthesize | **Customer/Market Research** |

Then ask **archetype-specific branching questions**:

#### Web Intelligence branches:
- What websites/domains need to be scraped?
- Are any geo-restricted, age-gated, or behind logins?
- What languages are the target sites in?
- What data structure do you need from each site?

#### Data Monitoring branches:
- How often should sources be checked?
- What constitutes a "change" worth alerting on?
- Where should alerts go (email, Teams, webhook)?

#### Document Processing branches:
- What document formats (PDF, Word, HTML)?
- What entities/data to extract?
- Is summarization needed or just extraction?

#### API Integration branches:
- What APIs are involved? Do you have OpenAPI specs?
- What's the sync direction (pull, push, bidirectional)?
- Rate limits or throttling constraints?

#### Reporting branches:
- What metrics / KPIs to track?
- Report format and distribution channel?
- What's the reporting cadence?

### Compliance Screen (always run)

Reference: `references/compliance-checklist.md`

At minimum, confirm:
1. **Data sources**: All public, or some require auth?
2. **PII**: Any personal data involved?
3. **Secrets**: Any API keys or credentials needed?
4. **Regulatory**: Any legal/regulatory constraints? (GDPR, industry-specific)
5. **Retention**: How long to keep data?
6. **Access**: Who can run this and see results?

---

## Phase 3: Feasibility + Architecture

**Goal**: Design the skill structure, validate tool availability, present for approval.

### Step 1: Map to Foundry Tools

Reference: `references/foundry-tools-catalog.md`

For each capability needed, map to a Foundry built-in tool:

| Capability | Foundry Tool |
|-----------|-------------|
| Web scraping | **Browser Automation** ⭐ |
| Web search / news | **Grounding with Bing Search** or **Web Search** |
| Scoped domain search | **Bing Custom Search** |
| Document analysis | **File Search** |
| Data processing | **Code Interpreter** |
| API integration | **OpenAPI** |
| Custom functions | **Function Calling** |
| Persistent storage | **Azure AI Search** |
| Corporate docs | **SharePoint** |
| Multi-agent | **Agent2Agent** |
| Scheduled tasks | **Azure Functions** |
| Custom tools | **MCP** (only if built-ins insufficient) |

### Step 2: Design Skill Decomposition

Follow the 3-layer pattern:

1. **Primitives** — Reusable extraction/handling logic
   - e.g., `handle-blockers`, `extract-products`, `transform-data`

2. **Domain Skills** — Source/topic-specific procedures
   - e.g., `scan-competitor-x`, `monitor-price-feed`, `ingest-patents`

3. **Orchestrators** — Coordination and workflow management
   - e.g., `scan-all`, `generate-weekly-report`, `run-full-pipeline`

### Step 3: Validate Feasibility

Check against `references/foundry-constraints.md`:

- [ ] All required Foundry tools available in target region?
- [ ] Selected model supports all needed tools?
- [ ] Any custom code required? → Flag with developer warning
- [ ] Runtime storage strategy defined? (no local files for persistence!)
- [ ] Authentication patterns identified for all data sources?
- [ ] Rate limiting / throttling strategy for web sources?

### Step 4: Present Architecture

Present the proposed architecture to the user before generating:

```
📋 Process: {name}
📌 Primary archetype: {archetype} + {secondary capabilities}

🔧 Foundry Tools:
  - Browser Automation (web scraping)
  - Code Interpreter (data processing)
  - Azure AI Search (storage)
  - ...

📁 Skill Structure:
  Primitives:
    - {skill-1}: {purpose}
    - {skill-2}: {purpose}
  Domain:
    - {skill-3}: {purpose}
  Orchestrators:
    - {skill-4}: {purpose}

💾 Storage: Azure AI Search (indexed data) + {other}
⚠️ Custom code needed: {yes/no — if yes, what and why}
```

**Wait for user approval before proceeding to generation.**

---

## Phase 4: Generate + Review

**Goal**: Create the complete folder structure with all files.

### Step 1: Choose Location

Ask the user:
> Where should I create the project folder?
> - Use the current directory (`{cwd}`)
> - Create a new folder (provide name)

### Step 2: Generate Files

Create in this order:

#### 1. `config/{name}.json`
Configuration file with source URLs, parameters, thresholds, etc. based on discovery.

#### 1b. `config/mock-data/` (if user chose mock data)

Generate mock data files when the user has no real data sources:

- One JSON file per data source: `config/mock-data/{source-name}.json`
- Each file contains 5-10 realistic sample records matching the expected schema
- Include varied data (different values, edge cases, missing fields where appropriate)
- Add a `_meta` field with generation timestamp and schema version

Also generate `config/mock-data/README.md` explaining:
- What each mock file represents
- The expected schema for real data
- How to replace mock data with an MCP server connection
- Example MCP tool call that would replace the file read

#### 2.`.github/skills/{skill-name}/SKILL.md` (for each skill)

> **Convention:** `.github/skills/` is the canonical skill format. The deploy skill
> will copy these to `skills/` when packaging for Foundry runtime. Never create a
> separate `skills/` directory at design time — that's a deploy artifact only.

Use the template from `references/skill-template.md`. Each skill MUST have:
- YAML frontmatter with `name` and `description` (include USE FOR / DO NOT USE FOR)
- Operational contract (inputs, outputs, deps, idempotency, failure behavior, Foundry tools)
- Step-by-step procedure
- Output schema
- Known issues & workarounds

#### 3. `AGENTS.md`

Use the template from `references/agents-template.md`. Must include:
- Agent identity and purpose
- Available skills table
- Foundry tools required (with justification)
- Custom MCP servers (only if needed)
- Data & storage strategy
- Behavioral guidelines
- Compliance & constraints
- Deployment notes

#### 4. `mcp-config.json` (MCP server configuration)

Generate MCP config files so GitHub Copilot CLI and VS Code auto-discover required tools.
Refer to `references/local-development.md` for the template and rules.

**MUST generate both:**
- `.copilot/mcp-config.json` — for GitHub Copilot CLI
- `.vscode/mcp.json` — for VS Code Agent Mode

Only include MCP servers the process actually needs. Map capabilities to local MCP first:

| Need | Local MCP Server |
|------|-----------------|
| Web scraping / browser automation | `@playwright/mcp` (local) |
| Azure AI Search queries | `@azure/mcp` with `--namespace search` (local) |
| Blob storage / Cosmos DB / SQL | `@azure/mcp` with relevant namespace (local) |
| Fabric data | `@microsoft/fabric-mcp` (local) |
| Web search | Tavily MCP (remote HTTP) |
| Foundry agent/model management | `https://mcp.ai.azure.com` (remote HTTP) |

If a capability has NO local MCP equivalent (Code Interpreter, File Search, Bing Grounding,
Agent2Agent, etc.), note it in AGENTS.md as "Foundry-deployment only" and suggest local workarounds.

#### 5. `skill-manifest.json`

Machine-readable deployment contract:

```json
{
  "name": "{process-name}",
  "version": "1.0.0",
  "description": "{one-line description}",
  "archetype": {
    "primary": "{archetype}",
    "secondary": ["{secondary-1}", "{secondary-2}"]
  },
  "foundry_tools": {
    "required": ["browser_automation", "code_interpreter", "azure_ai_search"],
    "optional": ["bing_search", "openapi"]
  },
  "custom_mcp": [],
  "mcp_servers": {
    "local": ["@playwright/mcp", "@azure/mcp"],
    "remote": ["https://mcp.ai.azure.com"]
  },
  "skills": [
    {"name": "{skill-1}", "type": "primitive"},
    {"name": "{skill-2}", "type": "domain"},
    {"name": "{skill-3}", "type": "orchestrator"}
  ],
  "storage": {
    "runtime_state": "{e.g., azure_ai_search}",
    "output_artifacts": "{e.g., sharepoint}",
    "configuration": "config/"
  },
  "custom_code_required": false,
  "compliance": {
    "pii": false,
    "auth_required_sources": [],
    "regulatory": [],
    "retention_days": null
  },
  "recommended_region": "swedencentral",
  "recommended_model": "gpt-5.4-mini"
}
```

#### 6. `README.md`

Project documentation covering:
- What this agent does
- Architecture diagram (text-based)
- Skill catalog with purposes
- Configuration guide
- Deployment instructions (Foundry)
- Usage examples

### Step 3: Review

Walk through the generated structure with the user:
1. Explain each skill and its purpose
2. Highlight any custom code requirements (⚠️ developer callouts)
3. Explain the **local vs remote tool split** — reference `references/local-development.md`:
   - Which tools work locally via MCP (Playwright, Azure MCP, Fabric MCP)
   - Which are Foundry-deployment only (Code Interpreter, Bing, File Search, Agent2Agent)
   - Local workarounds for remote-only tools
4. Walk through the generated `mcp-config.json` — explain each server and why it's included
5. Explain Foundry deployment migration path (local MCP → Foundry built-in tools)
6. Suggest improvements or extensions

---

## Reference Files

This skill includes reference files that are auto-loaded for context:

| File | Purpose |
|------|---------|
| `references/skill-template.md` | Template for generated SKILL.md files |
| `references/agents-template.md` | Template for generated AGENTS.md |
| `references/foundry-tools-catalog.md` | Foundry Agent Service built-in tools catalog |
| `references/foundry-constraints.md` | Foundry deployment constraints |
| `references/process-archetypes.md` | Process pattern definitions with starter structures |
| `references/compliance-checklist.md` | Privacy/legal/regulatory screening checklist |
| `references/local-development.md` | Local dev & testing with Foundry tools (Entra ID auth, SDK examples) |

---

## Design Principles

1. **Foundry-native**: Map to built-in Foundry tools first. Only use custom MCP when built-ins are insufficient.
2. **Browser Automation first**: For any web scraping need, Browser Automation (Playwright) is the primary tool.
3. **Remote-first state**: Never rely on local filesystem for persistent data. Use Azure AI Search, SharePoint, or MCP-backed storage.
4. **Operational contracts**: Every skill declares inputs, outputs, dependencies, and failure behavior.
5. **Progressive discovery**: Don't overwhelm users with questions. Start simple, branch by need.
6. **Compliance by default**: Always screen for PII, secrets, regulatory, and retention requirements.
7. **Developer transparency**: If custom code is needed, say so clearly with requirements.
8. **Evidence-first**: All extracted data should include source URLs, timestamps, and raw text for auditability.
