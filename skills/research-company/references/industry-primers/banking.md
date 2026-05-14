# Industry Primer — Banking (FSI)

> **Canon — see [AGENTS.md § 2.2](../../../../AGENTS.md#22--reference-data-files-are-canon--do-not-normalize).**
> *Stub — to be expanded next time `research-company` is run against a bank target.*

## Sub-segments

- Universal / G-SIB (global systemically important banks, FSB G-SIB list)
- Retail / high-street (national high-street incumbents, building societies)
- Investment-only (bulge-bracket investment banks, boutique advisory)
- Challenger / neobank (mobile-first, digital-only retail banks)
- Custodian (major asset-servicing custodians)

## Canonical vertical entity kinds

`Product`, `Cohort`, `Mandate`, `TreasuryBook`, `Counterparty`,
`Branch`, `Mortgage`, `Card`, `Position`, `Limit`, `Account`, `Trade`,
`Settlement`.

## Canonical regulators

| id | country | domain |
|---|---|---|
| `pra` | GB | banking |
| `fca` | GB | finance |
| `ecb-ssm` | EU | banking |
| `bafin` | DE | banking |
| `acpr` | FR | banking |
| `finma` | CH | banking |
| `fed` | US | banking |
| `occ` | US | banking |
| `sec` | US | securities |
| `finra` | US | securities |
| `hkma` | HK | banking |
| `mas` | SG | banking |

## Canonical KPIs

`cet1_ratio`, `nim`, `cost_income_ratio`, `npl_ratio`, `lcr`, `nsfr`,
`fraud_loss_bps`, `aml_alert_volume`, `kyc_cycle_days`.

## TODO

Expand on first bank run.
