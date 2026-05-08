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

### BR-002: [Rule Name]
- **Condition**:
- **Action**:
- **Exception**:

> Business rules are the backbone of the spec. Every skill procedure and
> evaluation scenario should trace back to one or more BR-XXX rules.

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

> Not all processes have human interaction points. Skip this section for
> fully automated flows.

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

---

## 10. Trigger & Run Model

How and when the process executes.

- **Trigger**: [on-demand / scheduled / event-driven / continuous]
- **Schedule**: [If scheduled — cron expression or cadence]
- **Event source**: [If event-driven — what triggers it]
- **Expected volume**: [Requests per hour/day]
- **Latency/SLA**: [Max acceptable response time]
- **Concurrency**: [Parallel execution expected?]

---

## 11. Security, Compliance & Governance

- **PII involved**: yes / no — [if yes, what fields]
- **Auth model**: [How users/systems authenticate]
- **Data retention**: [How long to keep data, deletion policy]
- **Regulatory**: [GDPR, HIPAA, SOX, industry-specific — or none]
- **Access control**: [Who can run this, who can see results]
- **Audit requirements**: [What must be logged for auditability]

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
