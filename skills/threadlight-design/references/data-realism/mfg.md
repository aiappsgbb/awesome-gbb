# Manufacturing demo-data realism rules

> Status: **📋 Placeholder.** Extend during the Mfg Supplier Risk pilot.

## Quick rules (until canonized)

- **Part numbers**: `DEMO-PART-XXXX` — never reuse a customer's actual BOM.
- **Supplier names**: synthesize from "place + thing" pattern — `Adriatic
  Casting Co.`, `Yarra Electronics Pty`, `Tegucigalpa Components`.
- **Plant / site names**: real cities + fictional facility number — `Stuttgart Plant 4`.
- **Quality codes**: use ISO 9001 / IATF 16949 nonconformance code structure
  but with synthetic codes (e.g. `NC-2026-00042` not real customer codes).
- **Shipment data**: realistic transit times by mode (sea ~30d, air ~3d,
  truck ~5d) with tail-risk events (port congestion, customs hold).
- **Geographic distribution**: weight by realistic supplier hubs (Yangtze
  Delta, Pearl River Delta, North Italy, Bavaria, Mexico Bajío) but use
  fictional company names located in those hubs.

## Risk corpus (Foundry IQ for supplier risk)

- **Public sources only**: news from Reuters/AP/Bloomberg style sources,
  publicly-filed regulatory documents (SEC, FTSE, etc.). Never use a
  customer's internal supplier-scoring framework or risk database.
- **Synthesize fictional risk events**: e.g. `Tegucigalpa Components — labor
  strike June 2026 — 14-day production halt impact on Q3 deliveries`. The
  cinematic moment is the agent connecting news → BOM → impact.

## To canonize during Supplier Risk pilot

- Supplier dependency chain golden case (depth-3 propagation)
- Risk event golden case (the "Tuesday morning supplier news" that becomes the demo hook)
- BOM impact math (one supplier → N parts → M finished goods → revenue at risk)
