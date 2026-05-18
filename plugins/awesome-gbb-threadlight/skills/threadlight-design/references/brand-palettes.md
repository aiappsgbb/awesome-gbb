# Brand Palettes — Sector Convention Fallback Table

> **Read this first.** This table is a **fallback**, not a substitute for the
> customer's actual brand guidelines. When `customer.brand_palette.primary`
> is captured during discovery (SPEC § 1) OR the customer's logo URL is
> available for live colour sampling, use those first. Reach for this table
> only when neither is available AND the sector convention is so strong
> ("they're red like the well-known UK telco") that a defensible default
> beats a guess.
>
> Every row carries a **citation** so the seller can defend the choice in
> the call. The hex codes are drawn from the brand's own public guidelines
> or from the sector's universally-recognised primary. They are **not**
> trademarked use — they're inputs to a brand-flood substrate behind a
> Microsoft × {Customer} co-brand bar.

## How this table is consumed

Cross-cutting Pattern 1 (Brand Cascade) detection order:

1. **Explicit** — `SPEC § 1 → customer.brand_palette.{primary, secondary, tertiary}` set during discovery
2. **Logo URL** — fetch + sample dominant non-neutral hex (offline if possible)
3. **This table** — sector convention lookup by `domain + customer name`
4. **Neutral fallback** — slate grey palette (no brand) + amber accent — only when none of 1-3 apply

When this table is the source, the generator MUST annotate the SPEC § 12
assumptions block:

```yaml
brand_palette_source: convention-fallback
brand_palette_cited: "see references/brand-palettes.md → UK Telco · Vodafone"
brand_palette_confirmed: false   # set true when customer confirms in next call
```

## Seeded sector conventions

> **Format:** `Sector · Brand → Primary (hex) · Secondary (hex) — citation`
>
> **Coverage rule:** when a new pilot uses a customer not on this list, add
> a row in the same shape. Keep this table to ≤30 rows long — beyond that,
> spin out a per-sector child file (e.g. `brand-palettes-fsi.md`).

### Telco

| Sector | Brand | Primary | Secondary | Citation |
|---|---|---|---|---|
| UK Telco | Vodafone | `#E60000` | `#FFFFFF` | brand.vodafone.com (public brand portal) |
| US Telco | Verizon | `#CD040B` | `#000000` | verizon.com brand guidelines (footer) |
| US Telco | AT&T | `#00A8E0` | `#067AB4` | att.com brand pages |
| Spanish Telco | Telefónica | `#0066FF` | `#FFFFFF` | telefonica.com identity refresh 2024 |
| Nordic Telco | Telenor | `#00ADEF` | `#FFFFFF` | telenor.com brand portal |
| German Telco | Deutsche Telekom | `#E20074` | `#FFFFFF` | telekom.com magenta brand (universally recognised) |

### Financial services

| Sector | Brand | Primary | Secondary | Citation |
|---|---|---|---|---|
| UK Retail Banking | HSBC | `#DB0011` | `#FFFFFF` | hsbc.com brand standards |
| UK Retail Banking | Barclays | `#00AEEF` | `#1D1D1B` | home.barclays brand guidelines |
| UK Retail Banking | Lloyds | `#006A4D` | `#FFFFFF` | lloydsbankinggroup.com brand assets |
| US Retail Banking | JPMorgan Chase | `#117ACA` | `#002D72` | jpmorganchase.com brand standards |
| Global Card Network | Visa | `#1A1F71` | `#F7B600` | visa.com brand portal |
| Global Card Network | Mastercard | `#EB001B` | `#F79E1B` | mastercardconnect.com brand assets (two-circle mark) |

### Healthcare

| Sector | Brand | Primary | Secondary | Citation |
|---|---|---|---|---|
| UK Public Health | NHS | `#005EB8` | `#FFFFFF` | service-manual.nhs.uk → identity → colour |
| Global Pharma | GSK | `#F36633` | `#15396C` | gsk.com brand portal |
| Global Pharma | AstraZeneca | `#830051` | `#C4D600` | astrazeneca.com identity (mulberry + lime) |
| US Health Insurer | UnitedHealth Group | `#002677` | `#FF612B` | unitedhealthgroup.com brand pages |

### Retail

| Sector | Brand | Primary | Secondary | Citation |
|---|---|---|---|---|
| Global Retail | Walmart | `#0071CE` | `#FFC220` | corporate.walmart.com brand portal |
| Global Retail | Target | `#CC0000` | `#FFFFFF` | corporate.target.com brand standards |
| UK Grocery | Tesco | `#EE1C2E` | `#00539F` | tescoplc.com brand guidelines |
| Coffee Chain | Starbucks | `#006241` | `#FFFFFF` | stories.starbucks.com brand colours (Siren Green) |
| Furniture | IKEA | `#0058A3` | `#FFDB00` | ikea.com brand portal |

### Manufacturing & Energy

| Sector | Brand | Primary | Secondary | Citation |
|---|---|---|---|---|
| German Auto | BMW | `#1C69D4` | `#0653B6` | bmwgroup.com brand portal |
| German Auto | Mercedes-Benz | `#00ADEF` | `#000000` | mercedes-benz.com brand standards |
| Industrial | Siemens | `#009999` | `#003E52` | siemens.com brand portal (petrol primary) |
| Aero/Defence | Boeing | `#1D4886` | `#FFFFFF` | boeing.com brand pages |
| Energy | BP | `#009900` | `#FFD700` | bp.com brand identity (helios flower colours) |
| Energy | Shell | `#FBCE07` | `#DD1D21` | shell.com brand standards |

### Public sector

| Sector | Brand | Primary | Secondary | Citation |
|---|---|---|---|---|
| UK Gov | GOV.UK | `#1D70B8` | `#0B0C0C` | design-system.service.gov.uk → styles → colour |
| EU Institutions | European Commission | `#003399` | `#FFCC00` | ec.europa.eu visual identity |

## What to do when the customer is not on this list

1. **Try the logo URL first.** Most companies publish a brand portal or
   styleguide PDF. A 60-second search usually yields a defensible primary
   hex.
2. **Check the sector convention.** If the customer is a regional bank, a
   tier-2 telco, or a sector player, the sector primary (e.g. Mastercard
   red for card networks, NHS blue for UK healthcare delivery) is usually
   acceptable as a stand-in until they confirm.
3. **Use the neutral fallback.** If nothing is defensible, use the
   threadlight default slate-grey palette (`#1F2937` primary, `#F59E0B`
   amber accent). Annotate `brand_palette_source: neutral-fallback` in
   SPEC § 12 so the next iteration replaces it.
4. **Never invent.** Do not pick a colour because "it looks nice for a
   utility". The seller has to defend every visual choice — undocumented
   palettes turn into trust debt in the first call.

## Citations note

Brand portal URLs change. The intent of the citation column is to record
**where the hex came from at time of seeding**, not to maintain a live
link. When updating a row, replace the citation; do not chain
citation-of-citation.
