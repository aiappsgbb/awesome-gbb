# Telco demo-data realism rules

> Status: **📋 Placeholder.** Extend during the Telco Order Fallout pilot.

## Quick rules (until canonized)

- **MSISDNs (phone numbers)**: use `+1-555-01XX-XXXX` (US documentation range)
  or per-country reserved ranges.
- **IMSI / IMEI**: use test ranges (`9999XXX...` for IMEI test).
- **Carrier names**: never use real carrier names. Use `Orbis Telecom`,
  `Meridian Mobile`, `Pacific Telecom` etc.
- **Network elements** (BTS, eNodeB, gNB, CMTS): synthetic IDs prefixed `DEMO-`.
- **Order IDs**: `ORD-2026-NNNNNN` — six-digit running counter scoped to the demo.
- **Fault codes / runbooks**: synthesize from publicly published telco fault
  taxonomies (3GPP, ITU-T) — never use a customer's internal NetCracker /
  Amdocs / Genie playbooks. Even sanitized, those are confidential.

## Reserved name list (do NOT use, even as inspiration)

- `NetCracker`, `Amdocs`, `Genie`, `Sigma`, `Tecnotree`, `BSCS`, `Singl.eView`
  — these are real BSS/OSS vendor names. Customer SMEs will recognize them
  and assume the demo was built from their stack.

## To canonize during Order Fallout pilot

- Order lifecycle state machine (golden case for the kanban demo)
- Network topology golden case (the "Tuesday morning fault" that's the demo hook)
- Customer-impact fan-out math (X faults → Y customers affected)
