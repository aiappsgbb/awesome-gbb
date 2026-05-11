# Per-process accent palette catalog

> Each threadlight process gets ONE accent color. Status and semantic colors are
> universal across processes (so operators don't have to relearn).

## Universal semantic colors (do not override per process)

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--ok` | `#16a34a` | `#4ade80` | Approved, healthy, in-target |
| `--warn` | `#f59e0b` | `#fbbf24` | Within ±20% of threshold, awaiting action |
| `--bad` | `#dc2626` | `#f87171` | Declined, breached, alert |
| `--info` | `#0078d4` | `#4da6ff` | Informational link |
| `--escalated` | `#7c3aed` | `#a78bfa` | Escalated to higher authority |

## Per-process accents

| Process | Industry | Accent (light) | Accent (dark) | Mood |
|---------|----------|----------------|---------------|------|
| KYC onboarding | FSI | `#0a2e5c` (deep navy) | `#7eb6ff` | Trust, regulatory weight |
| SMB credit memo | FSI | `#1f4e3a` (deep teal) | `#7fd6b3` | Banking, conservative |
| Insurance FNOL triage | FSI | `#c0392b` (signal red) | `#ff8a7a` | Urgency, claims |
| PIM catalog enrichment | Retail | `#b35aed` (creative violet) | `#d1a4ff` | Creative, brand |
| Returns triage | Retail | `#0d7c66` (sea green) | `#5fd9b4` | Operational |
| Order fallout | Telco | `#ff6e00` (signal orange) | `#ffa65a` | Live ops, alerts |
| Network fault triage | Telco | `#0066cc` (network blue) | `#5fb0ff` | Infra, control |
| Supplier risk | Mfg | `#5f6b3a` (deep olive) | `#bfcb88` | Industry, supply chain |

## Why these specific colors

- **One accent per process** so operators recognize "I'm in the KYC
  workspace" by chrome alone.
- **Avoids generic "AI blue"** — every demo using purple gradients and
  teal accents looks indistinguishable.
- **Status colors are universal** so an SME who's worked with one
  threadlight workspace can read another at a glance.
- **Each color has a defined dark-mode variant** so the accent stays
  legible in both schemes.

## Adding a new process palette

1. Pick an accent that resonates with the *industry* (not the agent or the
   AI brand)
2. Verify WCAG AA contrast against `--cp-bg` and `--cp-bg` dark
3. Add row to the table above
4. Wire into `workspace.css` as `--accent: <hex>;`
