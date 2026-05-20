# Domain Primers

Optional reference files that accelerate discovery for common industry scenarios.
The skill detects the domain during Phase 1 and loads the relevant primer to **seed**
discovery — not replace it.

## How Primers Work

1. During Phase 1 (Clarify Purpose), the skill identifies the domain
2. If a matching primer exists, it's loaded as context alongside the discovery
3. The primer suggests typical business rules, data models, integrations, and regulatory
   requirements — the user confirms, modifies, or rejects each suggestion
4. Anything not confirmed is discarded — primers are additive, never mandatory

## Primer Structure

Each primer follows the same format:

```markdown
# Domain Primer: [Domain Name]

## Regulatory Landscape
- Key regulations and compliance requirements
- Governing bodies and standards

## Typical Business Rules
- BR-style rules common to this domain (user confirms/adapts)

## Common Data Models
- Entities typically involved, with key fields

## Common System Integrations
- External systems, APIs, data sources typical in this domain

## Typical Process Patterns
- Common process flows and decision points

## Domain Vocabulary
- Key terms and their meanings (helps the agent speak the domain language)
```

## Available Primers

| Primer | Domain | Scenarios |
|--------|--------|-----------|
| [fsi-kyc-aml.md](fsi-kyc-aml.md) | Financial Services — KYC/AML | Customer onboarding, due diligence, sanctions screening, SAR filing |

> **Contributing a primer:** Add a new `.md` file following the structure above.
> Keep it concise (suggestions, not encyclopedias) and domain-expert-reviewed.
