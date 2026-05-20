# Industry Primer — Retail

> **Canon — see [AGENTS.md § 2.2](../../../../AGENTS.md#22--reference-data-files-are-canon--do-not-normalize).**
> *Stub — to be expanded next time `research-company` is run against a retail target.*

## Sub-segments

- Grocer (national supermarket chains, hypermarkets, hard-discount)
- General-merch (mass-market general retailers, warehouse clubs)
- Fashion / apparel (fast-fashion, vertically-integrated specialty)
- Pure-play e-commerce (marketplace, vertical pure-play)
- DIY / home (national DIY chains, big-box home improvement)
- QSR (quick-service restaurant franchises — treat as franchise model)

## Canonical vertical entity kinds

`Product`, `Range`, `Promotion`, `FloorPlan`, `Store`, `SKU`,
`Supplier`, `DistributionCentre`, `Shrinkage`, `Cohort`, `Order`,
`Replenishment`.

## Canonical regulators

| id | country | domain |
|---|---|---|
| `cma-uk` | GB | anti-trust |
| `dg-comp` | EU | anti-trust |
| `ftc` | US | anti-trust |
| `fda` | US | food-safety |
| `bvl` | DE | food-safety |
| `efsa` | EU | food-safety |

## Canonical KPIs

`like_for_like`, `gross_margin`, `inventory_turnover`,
`stockout_rate`, `shrinkage_rate`, `nps`, `basket_size`,
`online_share`, `dso`.

## TODO

Expand on first retail run.
