# Retail / CPG demo-data realism rules

> Status: **📋 Placeholder.** Extend during the Retail PIM enrichment pilot.

## Quick rules (until canonized)

- **SKUs**: `DEMO-SKU-XXXXX` — internal-format SKUs that obviously aren't real.
- **Brand names**: shift well-known brands (e.g. `Patagonia` → `Glacier Outpost`,
  `Allbirds` → `Sandbird`). Never use a real brand verbatim.
- **Product images**: AI-generated or stock photography with explicit license.
  Never scrape competitor product photos.
- **Customer reviews / ratings**: synthesize with Faker; distribution skews
  positive (mean 4.2/5, std 0.8) with a few low-star outliers for the demo.
- **Price distributions**: log-normal, category-specific (apparel mean $80,
  electronics mean $400, grocery mean $7).
- **Inventory levels**: include zero-stock cases and replenishment-in-flight
  cases — the demo needs to show the agent reasoning about stockouts.

## To canonize during PIM pilot

- Brand-guideline document corpus (fictional brand book)
- Photo enrichment golden cases (brand-compliant vs not, vision-critical edge cases)
- Returns triage golden cases (visible damage, "wear and tear" disputes)
- Loyalty / tier rules realistic to the demo persona retailer
