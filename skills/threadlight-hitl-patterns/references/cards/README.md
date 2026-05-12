# Adaptive Card templates — placeholder index

The seven canonical action gates each get an Adaptive Card 1.5 template
under this directory:

| Gate | File | Status |
|------|------|--------|
| `approve` | `approve.json` | 📋 Placeholder — full template inlined in SKILL.md |
| `edit-and-approve` | `edit-and-approve.json` | 📋 Placeholder |
| `reject` | `reject.json` | 📋 Placeholder |
| `escalate` | `escalate.json` | 📋 Placeholder |
| `signoff` | `signoff.json` | 📋 Placeholder |
| `audit-view` | `audit-view.json` | 📋 Placeholder |
| `request-info` | `request-info.json` | 📋 Placeholder |

The SKILL.md inlines the canonical `approve` shape; the others follow the
same structure with gate-specific Input fields and Action buttons.

## Canonization order (during pilots)

1. **KYC pilot** — canonize `approve`, `edit-and-approve`, `escalate`
   (the three gates KYC analyst needs)
2. **Future operations pilot** — canonize `escalate`, `signoff`, `audit-view`
   (NOC operator gates)
3. **Supplier risk pilot** — canonize `request-info` (supplier outreach)
4. **PIM pilot** — canonize `reject` with reason picker (brand violation)

The card JSON should validate against Adaptive Cards 1.5 schema:
https://adaptivecards.io/explorer/
