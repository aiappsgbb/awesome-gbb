# Process Traits

Use these as **composable building blocks**, not a closed list. Real processes combine
multiple traits. Detect traits from discovery answers and compose dynamically.

## How to Use

1. During discovery, identify which traits apply to the use case
2. Combine traits to form the process profile
3. Use trait-specific branching questions to deepen discovery
4. Map traits to typical tool shapes and skill patterns

A single process usually combines 2-4 traits.

---

## Trait: Data Sourcing

How the process acquires its input data.

| Variant | Description | Typical Tools | Discovery Questions |
|---------|-------------|---------------|---------------------|
| **Web scraping** | Extract data from websites | Browser Automation, Playwright MCP | What sites? Auth needed? Geo-restricted? Languages? |
| **API integration** | Call external APIs | OpenAPI, MCP, Function Calling | Which APIs? OpenAPI specs available? Rate limits? |
| **Document intake** | Process uploaded/stored documents | File Search, SharePoint | What formats (PDF, DOCX, images)? What to extract? Volume? |
| **Database query** | Read from corporate databases | MCP, custom tools | Which DB (SQL, Cosmos, SAP)? Read-only or read-write? Access available or mock? |
| **Search / research** | Find information across sources | Bing Search, AI Search, Web Search | What topics? How broad? Freshness requirements? |
| **User input** | Conversational data gathering | Agent chat | What info from user? Structured or freeform? Validation needed? |
| **Event-driven** | React to webhooks, messages, signals | Azure Functions, Event Grid | What triggers? Frequency? Payload format? |

---

## Trait: Processing Style

What the process does with the data.

| Variant | Description | Typical Skills | Discovery Questions |
|---------|-------------|----------------|---------------------|
| **Extraction** | Pull specific fields/entities from unstructured data | `extract-*` skills | What fields? What accuracy? |
| **Transformation** | Convert, normalize, enrich data | `transform-*` skills | Source → target format? Rules? |
| **Comparison** | Diff, rank, score across items | `compare-*`, `rank-*` skills | What dimensions? Weighting? |
| **Analysis** | Compute metrics, detect patterns, assess risk | `analyze-*`, `assess-*` skills | What KPIs? Thresholds? Business rules? |
| **Synthesis** | Combine multiple sources into new content | `synthesize`, `summarize` skills | What output format? Depth? Citation needs? |
| **Validation** | Check data against rules, policies, schemas | `validate-*`, `check-*` skills | What rules? What happens on failure? |
| **Routing** | Direct items to the right handler based on criteria | `route-*`, `triage-*` skills | What criteria? How many routes? Fallback? |

---

## Trait: Output Mode

What the process produces.

| Variant | Description | Typical Delivery | Discovery Questions |
|---------|-------------|-----------------|---------------------|
| **Report** | Structured document (Markdown, PPTX, PDF) | File output, email, SharePoint | Format? Cadence? Audience? |
| **Structured data** | JSON, CSV, database records | API, storage, downstream system | Schema? Destination? Append or replace? |
| **Notification** | Alert, message, summary | Teams, email, webhook | Who? What threshold triggers it? Channel? |
| **Decision** | Approval, recommendation, score | Agent response, human approval flow | Who decides? What data supports the decision? SLA? |
| **Conversation** | Interactive response to user | Chat, Teams, portal | Tone? Domain constraints? Escalation path? |
| **Action** | Side effect in an external system | API call, DB write, ticket creation | Which system? Idempotent? Retry policy? |

---

## Trait: Interaction Model

How humans participate in the process.

| Variant | Description | Discovery Questions |
|---------|-------------|---------------------|
| **Fully automated** | No human in the loop | What triggers? What monitoring/alerting if it fails? |
| **Human-in-the-loop** | Human approves/reviews at key points | Who approves? What do they see? SLA? Escalation? |
| **Conversational** | Agent and human collaborate in real-time | What channel (Teams, web, API)? Session length? Memory needs? |
| **Supervised** | Agent proposes, human confirms before execution | What's the blast radius? Undo possible? |
| **Periodic review** | Agent runs autonomously, human reviews output periodically | Cadence? What's reviewed? How to flag issues? |

---

## Trait: Temporal Pattern

When and how often the process runs.

| Variant | Description | Discovery Questions |
|---------|-------------|---------------------|
| **On-demand** | User triggers explicitly | What's the expected usage pattern? |
| **Scheduled** | Runs on a timer (hourly, daily, weekly) | Exact schedule? Time zone? Dependencies? |
| **Event-driven** | Triggered by external event | What event? Source? Latency requirements? |
| **Continuous** | Always running, monitoring a stream | Volume? Backpressure strategy? |
| **Batch** | Processes a queue of items periodically | Batch size? Ordering? Failure handling per item? |

---

## Trait: State Model

How the process manages state across steps and over time.

| Variant | Description | Discovery Questions |
|---------|-------------|---------------------|
| **Stateless** | Each invocation is independent, no memory | Any caching useful? |
| **Session-based** | State within a conversation/session, discarded after | Session timeout? What's stored? |
| **Case-based** | Long-lived case/ticket with lifecycle (open → in-progress → resolved) | Case lifecycle stages? Who can update? SLA per stage? |
| **Pipeline** | Items flow through ordered stages with checkpointing | What happens if a stage fails? Retry? Skip? Queue? |

---

## Trait: Action Criticality

How consequential the process's actions are — drives approval and safety patterns.

| Variant | Description | Discovery Questions |
|---------|-------------|---------------------|
| **Read-only** | Only reads/analyzes data, no side effects | N/A — lowest risk |
| **Reversible write** | Creates/updates data that can be undone | Undo mechanism? Soft delete? |
| **Irreversible write** | Financial transactions, notifications, external system writes | Human approval needed? Confirmation step? Audit trail? |
| **Mixed** | Some actions are safe, some are critical | Which actions need approval? What's the blast radius? |

---

## Example: Combining Traits

### Insurance Claims Processing
- **Data Sourcing**: Document intake (claim forms) + Database query (policy DB) + API integration (fraud detection)
- **Processing**: Extraction → Validation → Analysis → Routing
- **Output**: Decision + Action (create claim record) + Notification (adjuster assignment)
- **Interaction**: Human-in-the-loop (adjuster reviews complex claims)
- **Temporal**: Event-driven (new claim submitted)

### Competitive Intelligence Dashboard
- **Data Sourcing**: Web scraping + Search/research
- **Processing**: Extraction → Comparison → Synthesis
- **Output**: Report + Structured data (dashboard)
- **Interaction**: Periodic review
- **Temporal**: Scheduled (weekly)

### Customer Service Front Desk
- **Data Sourcing**: User input + Database query (CRM, KB) + API integration (order system)
- **Processing**: Routing → Analysis → Synthesis
- **Output**: Conversation + Action (create ticket, update CRM)
- **Interaction**: Conversational
- **Temporal**: On-demand
