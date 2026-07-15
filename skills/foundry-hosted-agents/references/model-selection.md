# Model selection for Foundry hosted agents

Choose **which model, in which region, at what capacity** before you run
`azd provision`. The deployment *mechanics* are in SKILL.md — the
`azure.yaml` `services.ai-project.deployments:` block (§ *azure.yaml
(unified hosted-agent configuration)*), the version pin (§ *Model
Version Lookup*), the `azd env` wiring (§ *azd env variables for the
azure.ai.agents extension*), and region support (§ *Region
Availability*). This file is the *decision* that feeds them.

## When to read this

You're standing up a hosted agent and must pick a model deployment. The
classic pilot failure is "I picked a region and the model or quota
wasn't there." Decide the four axes below **before** committing a region
in `main.bicep` / `azure.yaml`.

## 1 — Capability selection

Match the workload to the cheapest family that clears the capability
bar. Use the version pins from § *Model Version Lookup* — that table is
the single source of truth for versions; do not restate them here.

| Workload | Start with | Why |
|---|---|---|
| Deep multi-step reasoning / agentic planning | `gpt-5.4` | Top capability tier in the pinned table |
| Code generation / repair | `gpt-5.3-codex` | Code-specialized |
| Balanced general + tool/function calling | `gpt-5.4-mini` | Cheaper/faster; keeps structured-output + tool calling |
| High-volume classify / extract / route | `gpt-5.4-nano` | Cheapest/fastest of the pinned family |
| Legacy / compat baseline | `gpt-4.1` / `gpt-4.1-mini` | When a consumer pins the 4.x surface |

Cross-cutting checks before you commit a family:

- **Tool / function calling + structured outputs** — required for most
  agent patterns (MCP tools, `@tool`, JSON output). Confirm the chosen
  family supports it for your API surface.
- **Context window** — long-context RAG needs headroom for retrieved
  chunks + history. Confirm the exact token limit for the pinned version
  on MS Learn (limits differ across the family — don't assume).
- **Latency vs cost** — smaller suffixes (`-mini`, `-nano`) trade
  capability for lower latency and cost; size to the task, not the
  ceiling. Per-call cost drivers live in `foundry-cost-monitoring`.

## 2 — Region & availability

Model availability is **per region** and independent of hosted-agent
region support. Both gates must hold:

1. Hosted-agent support in the region — see § *Region Availability*.
2. The model + version is deployable there — check **before** committing:

```bash
# Models deployable for an existing account's region:
az cognitiveservices account list-models \
  --resource-group <rg> --name <account> -o table

# Models available in a region (pre-account planning):
az cognitiveservices model list \
  --location <region> -o table
```

If either gate fails, fall back per § 4.

## 3 — Capacity & quota (TPM)

A deployment's `sku.capacity` is its throughput ceiling in **units of
1,000 TPM** (tokens-per-minute): `capacity: N` provisions N×1,000 TPM
(e.g. `capacity: 120` = 120K TPM). `sku.name` sets the residency/scale
class (§ 4). Check regional headroom before you pick a number:

```bash
az cognitiveservices usage list --location <region> -o table
# Find the model's *-GlobalStandard (or *-Standard) usage row. limit and
# currentValue are in the same 1,000-TPM units as sku.capacity, so
# (limit - currentValue) = the capacity units still assignable in that region.
```

- Size `sku.capacity` so its N×1,000 TPM covers expected peak **with
  headroom**: too low → `429`s under load; too high → wasted quota that
  blocks other deployments in the region.
- Request increases via the account's quota experience **before** deploy
  day — regional ceilings are shared across every deployment in that
  region/subscription.
- Deeper capacity economics (PAYGO vs PTU) are in
  `paygo-ptu-cost-analyzer`.

## 4 — Data-residency & fallback

`sku.name` is your residency lever — a ladder from widest reach to
tightest locality:

| `sku.name` | Data-processing locality | Use when |
|---|---|---|
| `GlobalStandard` | May process in any region worldwide | No residency constraint; widest model + capacity availability |
| `DataZoneStandard` | Stays within the geo / data zone (e.g. EU) | EU (or US) data-zone residency is sufficient |
| `Standard` (regional) | Single region only | Strict single-region residency |

**EU-residency path:** prefer `DataZoneStandard` in an EU data zone, or
regional `Standard` in an EU region. When your primary EU region lacks
the model or capacity, `swedencentral` is the pragmatic fallback — a
known-working hosted-agent region (§ *Region Availability*) with broad
model coverage.

> **Caveat (verified):** in `swedencentral`, embedding deployments
> (e.g. `text-embedding-3-small`) require `GlobalStandard` — regional
> `Standard` is rejected there. If an EU-residency design needs
> embeddings in Sweden Central, that specific deployment cannot use a
> regional SKU; plan the residency story around it.

The residency ↔ SKU choice also has a cost dimension (regional SKUs can
cost more than `GlobalStandard` where residency isn't needed) — see the
`foundry-cost-monitoring` optimization table.

## 5 — Wiring the decision in

The four axes land in one place — the `azure.yaml`
`services.ai-project.deployments:` block (§ *azure.yaml (unified
hosted-agent configuration)*):

| Decision | `azure.yaml` field |
|---|---|
| Model family (§ 1) | `deployments[].model.name` |
| Version (§ *Model Version Lookup*) | `deployments[].model.version` |
| Capacity / TPM (§ 3) | `deployments[].sku.capacity` |
| Residency class (§ 4) | `deployments[].sku.name` |

Region is set by where you `azd provision` (the account location in
`main.bicep`); the project endpoint / ID flow through the `azd env`
vars in § *Required azd env variables for the azure.ai.agents
extension*.
