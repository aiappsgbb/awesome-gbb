---
name: gbb-pulse
description: Draft signals for the weekly AI GBB Pulse. Use this skill when asked to write, draft, or create a pulse signal, GBB signal, customer win, customer loss, customer escalation, compete signal, product signal, IP initiative, skills/people signal, or any field insight intended for the AI GBB Pulse weekly collection. Helps structure field observations into actionable signals for product groups (PG) and go-to-market teams, feeding into MSR and MTR reviews.
---

# GBB Pulse Signal Drafter

Draft structured signals for the weekly AI GBB Pulse — a mechanism for the GBB team to feed field insights (patterns, trends, competitive intelligence) back to product groups (PG) and go-to-market teams. These signals complement the blockers reporting process and feed into monthly reviews like MSR (sales) and MTR (tech).

## Signal Categories

Every pulse signal belongs to exactly one category. Pick the best-fitting template within that category.

### 1. Customer Wins & Losses
Customer deal outcomes, adoption milestones, churn, escalations, or expansion signals.

| Template | When to use |
|----------|-------------|
| [customer-wins.md](./templates/customer-wins.md) | Customer win — deal closed, workload adopted, expansion |
| [customer-losses.md](./templates/customer-losses.md) | Customer loss, blocked deal, or significant challenge |
| [customer-escalation.md](./templates/customer-escalation.md) | Top 2-3 largest customer escalations that SLT needs to be aware of (not for UAT/tech blockers) |

### 2. Compete & Product Signals
Competitive intelligence, product gaps, feature requests, or market trends observed in the field.

| Template | When to use |
|----------|-------------|
| [compete-signals.md](./templates/compete-signals.md) | Competitive signal — new entrant, pricing change, feature difference, strategy shift |
| [product-signals.md](./templates/product-signals.md) | Product feedback — feature request, bug, performance issue, integration gap |

### 3. IP Initiatives & Others
Intellectual Property assets (code samples, demos, repeatable solution accelerators), best practices, or other notable initiatives.

| Template | When to use |
|----------|-------------|
| [ip-initiatives-others.md](./templates/ip-initiatives-others.md) | IP being scaled, new initiative/program, or a best practice worth sharing |

### 4. Skills & People Signals
People, skills, and resource-related observations from the field.

| Template | When to use |
|----------|-------------|
| [skills-people.md](./templates/skills-people.md) | Hiring need, skill gap, training requirement, or resource request |

## Workflow

1. **Gather input** from the user about their customer engagement or market observation.
2. **Use WorkIQ to enrich context** — Query Microsoft 365 Copilot using the workiq skill to gather additional details from recent emails, Teams conversations, meetings, and documents related to the signal. This helps identify:
   - Customer names and specific accounts involved
   - Quotes and supporting evidence from conversations
   - Timeline and context from recent interactions
   - Related threads or discussions that validate the pattern
3. **Classify** the signal into one of the four categories above based on the content.
4. **Select the matching template** from the tables above. If the signal could fit multiple templates, pick the most specific one and confirm with the user.
5. **Load the template** and review all required fields.
6. **Check for missing information** — If any required field from the template cannot be filled with the provided input or WorkIQ data, **ask the user** before drafting. Never guess or leave required fields blank.
7. **Draft the signal** following the template structure exactly, incorporating evidence gathered from WorkIQ.
8. **Save the output file** in the `signals/` folder using the naming convention: `signals/YYYY-MM-DD-<signal-name>.md` where:
   - YYYY-MM-DD is the current date
   - signal-name is a descriptive kebab-case name for the signal
   - Example: `signals/2026-02-06-compete-signal-anthropic-datazone.md`

## Guidelines

- Always use WorkIQ to gather context from recent Microsoft 365 conversations, emails, and meetings before drafting — this provides concrete customer names, quotes, and evidence to strengthen the signal.
- Always ask clarifying questions when input is incomplete — do not fabricate details.
- Keep signals concise and actionable; product groups should be able to act on them.
- Use specific customer names, product names, and metrics where available (the user is responsible for confidentiality decisions).
- One signal per draft — if the user describes multiple signals, draft them separately.
- Always create the output file in the `signals/` folder with date-prefixed naming: `signals/YYYY-MM-DD-<signal-name>.md`