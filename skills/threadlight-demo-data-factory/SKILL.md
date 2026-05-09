---
name: threadlight-demo-data-factory
description: >
  Generate per-domain Faker-style synthetic data + Cosmos seed/reset
  scripts for a threadlight process. Reads spec § 11d Demo Data and
  industry realism rules from threadlight-design, then produces
  scripts/seed_data.py and scripts/reset_data.py plus the seed JSON
  files in specs/sample-data/.
  USE FOR: generate demo data, synthetic data, Faker generators,
  Cosmos seed script, demo reset, mock data factory, threadlight
  demo data, populate sample-data, golden cases, idempotent reset.
  DO NOT USE FOR: indexing real customer data (use foundry-iq for
  that), live data ingestion (use threadlight-event-triggers), MCP
  server scaffold (use foundry-mcp-aca).
---

# Threadlight Demo Data Factory

Generate per-domain synthetic demo data + idempotent reset/seed scripts for
a threadlight process. The output drives both the mock MCP server (via
`foundry-mcp-aca` Option D) and the workspace UI (via
`threadlight-workspace-ui`) — every demo surface reads the same seed.

> **Why a separate skill?** `foundry-mcp-aca` knows how to *serve* mock
> data via FastMCP; `threadlight-design` knows how to *declare* what
> entities and shapes are needed. This skill bridges them: it generates
> the actual JSON files (with realistic distributions, golden cases, and
> reset semantics) that the MCP server returns and the workspace renders.

## When to Use

- Process spec has at least one system marked `availability: mock` in § 5
- Process spec has § 11d Demo Data populated
- Demo needs reset-to-pristine for live recovery (every customer-facing
  demo does)
- Pilot is the canonization opportunity for an industry's realism rules

## When NOT to Use

- Customer's real backend is already accessible (no mocks needed)
- Demo data is so tiny it's hand-authored faster (e.g. 3 records total)
- Process talks only to public APIs (no synthetic data needed)

---

## Input contract / Output artifacts

**Input contract**:

- `specs/SPEC.md` § 4 **Data Models** — entity schemas
- `specs/SPEC.md` § 5 **System Integrations** — which systems are `mock`
- `specs/SPEC.md` § 11d **Demo Data (Realism rules)** — required:
  - Per-entity volumes
  - Distribution rules
  - Named golden cases
  - Reset semantics (`idempotent` / `append-only` / `none`)
  - Industry realism reference (e.g. `industry: fsi-banking` → loads
    `threadlight-design/references/data-realism/fsi.md`)
- `threadlight-design/references/data-realism/{industry}.md` — the
  per-industry rule book (universal rules + industry-specific overrides)

**Output**:

```
specs/sample-data/
├── {entity1}.json       # Generated, includes _meta block
├── {entity2}.json
└── README.md            # Generation date + golden case list

scripts/
├── seed_data.py         # Faker-driven generator (regenerates JSON files)
├── reset_data.py        # Wipes Cosmos + reloads from JSON
├── pyproject.toml       # uv-managed (faker, azure-cosmos, etc.)
└── README.md            # How to run + golden case scripts

src/mcp/data/            # COPIED from specs/sample-data/ at deploy time
├── {entity1}.json       # (handled by threadlight-deploy / foundry-mcp-aca)
└── {entity2}.json
```

---

## The realism stack

```
Universal rules
   ↓ (always applied)
Industry rules (e.g. fsi.md)
   ↓ (industry-specific overrides)
Spec § 11d (per-process tweaks)
   ↓ (process-specific overrides)
Generated data
```

Each layer can override the layer above it. The factory composes them
deterministically (with a seeded RNG) so two runs of the same spec
produce byte-identical output.

---

## Generation procedure

### Step 1: Read inputs

```python
industry = spec["demo_data"]["industry"]                      # "fsi-banking", "retail-cpg", "telco", "mfg"
realism_rules = load_realism(f"data-realism/{industry}.md")
volumes = spec["demo_data"]["volumes"]                        # {"customers": 50, "orders": 200, ...}
distributions = spec["demo_data"]["distributions"]            # per-entity skew rules
golden_cases = spec["demo_data"]["golden_cases"]              # named hand-curated records
reset_mode = spec["demo_data"]["reset_semantics"]             # "idempotent" / "append-only" / "none"
entities = spec["data_models"]                                # field schemas from § 4
```

### Step 2: Generate `scripts/seed_data.py`

```python
"""Synthetic data generator — driven by spec § 11d.
Run: uv run scripts/seed_data.py [--seed 42]
Output: specs/sample-data/*.json (deterministic with --seed)
"""
import json, random
from pathlib import Path
from faker import Faker

# Deterministic seeding so two runs produce identical output
random.seed(42)
fake = Faker(["en_US"])
fake.seed_instance(42)

DATA_DIR = Path(__file__).parent.parent / "specs" / "sample-data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def gen_customers(n: int) -> list:
    """Generates n customer records per universal + FSI rules."""
    out = []
    for i in range(n):
        out.append({
            "customer_id": f"DEMO-CUST-{i:05d}",
            "name": _shifted_company_name(),  # never a real bank
            "incorporation_date": fake.date_between(start_date="-30y", end_date="-1y").isoformat(),
            # ... fields from spec § 4 Customer entity ...
        })
    # Splice in golden cases by ID
    for golden in [g for g in GOLDEN_CASES if g["entity"] == "customers"]:
        out = [g for g in out if g["customer_id"] != golden["data"]["customer_id"]]
        out.append(golden["data"])
    return out

# ... one gen_* function per entity ...

if __name__ == "__main__":
    for entity in ENTITIES:
        records = ENTITY_GENERATORS[entity](VOLUMES[entity])
        path = DATA_DIR / f"{entity}.json"
        # Always include _meta for traceability
        meta = {"_meta": {"generated_at": datetime.utcnow().isoformat(), "seed": 42, "version": "1.0", "entity": entity, "count": len(records)}}
        path.write_text(json.dumps([meta] + records, indent=2))
        print(f"  wrote {path} ({len(records)} records)")
```

### Step 3: Generate `scripts/reset_data.py`

For `idempotent` reset:

```python
"""Reset Cosmos containers from specs/sample-data/.
Safe to run while the agent is up — completes in <30s for live demo recovery.

Usage: uv run scripts/reset_data.py [--container <name>]
"""
import asyncio, json
from pathlib import Path
from azure.identity.aio import DefaultAzureCredential
from azure.cosmos.aio import CosmosClient

DATA_DIR = Path(__file__).parent.parent / "specs" / "sample-data"

async def reset_container(client, db_name: str, container_name: str, entity_file: str):
    db = client.get_database_client(db_name)
    container = db.get_container_client(container_name)
    # Delete all items (chunked)
    async for item in container.read_all_items():
        await container.delete_item(item["id"], partition_key=item.get("partition_key", item["id"]))
    # Reload from JSON
    records = json.loads((DATA_DIR / entity_file).read_text())
    records = [r for r in records if not r.get("_meta")]
    await asyncio.gather(*[container.upsert_item(r) for r in records])
    print(f"  reset {container_name}: {len(records)} records")

async def main():
    async with DefaultAzureCredential() as cred:
        async with CosmosClient(COSMOS_ENDPOINT, cred) as client:
            await asyncio.gather(*[
                reset_container(client, DB_NAME, name, file)
                for name, file in CONTAINER_MAP.items()
            ])

if __name__ == "__main__":
    asyncio.run(main())
```

For `append-only`: delete only items with `_meta.demo: true` — preserve
human-introduced records.

For `none`: skip generating reset_data.py (read-only datasets).

### Step 4: Generate `specs/sample-data/README.md`

```markdown
# Sample data

> Generated by `threadlight-demo-data-factory` from spec § 11d.
> Industry realism: `{industry}` (see `threadlight-design/references/data-realism/{industry}.md`)

## Files

| Entity | Records | Notes |
|--------|---------|-------|
| customers.json | 50 | log-normal distribution; 3 golden cases |
| orders.json | 200 | mean $1,200, p99 $50K |

## Golden cases

Hand-curated records the demo script narrates around. **Do not delete or rename.**

| ID | Entity | Story beat |
|----|--------|------------|
| `DEMO-CUST-00007` | customers | Sanctioned-entity hit (KYC dramatic moment) |
| `DEMO-CUST-00042` | customers | Premium onboarding happy path (anchor case) |

## Regenerating

```bash
uv run scripts/seed_data.py            # default seed 42 — deterministic
uv run scripts/seed_data.py --seed 99  # different distribution, same structure
```

## Reset (live demo recovery)

```bash
uv run scripts/reset_data.py           # wipe Cosmos + reseed from JSON in <30s
```
```

### Step 5: Wire into the deploy

Notify `threadlight-deploy` that `scripts/seed_data.py` and
`scripts/reset_data.py` exist. The deploy adds a postdeploy step that runs
the seed script once after first provision (so the Cosmos containers come
up populated). The reset script is operator-invoked (deliberately not
automated — humans should know they're wiping demo state).

### Step 6: Validate

```
✅ scripts/seed_data.py runs, produces specs/sample-data/*.json
✅ Two runs with same --seed produce byte-identical output (deterministic)
✅ Golden cases are spliced in by ID and present in output
✅ Per-entity volumes match spec § 11d
✅ Distributions visually match expected (run a quick stats check)
✅ scripts/reset_data.py wipes + reloads in <30s on a small Cosmos
✅ Sample data passes industry realism deny-list (e.g. no real bank names)
✅ _meta block present in every output file
✅ scripts/README.md documents the golden cases and reset procedure
```

---

## Per-industry generators

The factory ships generators per industry. Each one lives in
`references/generators/{industry}.py` and inherits universal rules.

| Industry | Generator | Status |
|----------|-----------|--------|
| `fsi-banking` | `references/generators/fsi.py` — customers, accounts, transactions, sanctions hits | 🔶 Draft (canonized during KYC pilot) |
| `fsi-insurance` | reuses `fsi.py` with insurance-specific entities (policies, claims) | 🔶 Draft |
| `retail-cpg` | `references/generators/retail.py` — products, SKUs, orders, returns, reviews | 📋 Placeholder |
| `telco` | `references/generators/telco.py` — customers, MSISDNs, orders, faults, network elements | 📋 Placeholder |
| `mfg` | `references/generators/mfg.py` — suppliers, parts, BOMs, shipments, quality events | 📋 Placeholder |

Each generator is a Python module with one `gen_{entity}(n)` function per
entity it knows how to generate. The factory imports and calls them; if an
entity is in the spec but no generator exists, the factory falls back to a
naive Faker rendering and emits a warning ("Add a generator to elevate
realism").

---

## Reference files

| File | Purpose |
|------|---------|
| `references/generators/fsi.py` | FSI banking + insurance generators (canonized during KYC pilot) |
| `references/generators/retail.py` | Retail / CPG generators (canonized during PIM pilot) |
| `references/generators/telco.py` | Telco generators (canonized during Order Fallout pilot) |
| `references/generators/mfg.py` | Mfg generators (canonized during Supplier Risk pilot) |
| `references/generators/_universal.py` | Shared utilities — shifted-name, valid-format-fake, log-normal helpers |
| `references/generators/README.md` | How to write a new industry generator |
| `references/cosmos-bootstrap.md` | First-time Cosmos container creation (called by reset_data.py first run) |

---

## Anti-patterns

- ❌ **Use random.uniform() for everything.** Real distributions are skewed.
  Plausible-looking data needs the right distribution per field.
- ❌ **Forget the _meta block.** Future-you will not know what generated
  this data without it.
- ❌ **Generate data without golden cases.** A demo without named hero
  cases is a demo without a script.
- ❌ **Use a non-deterministic seed.** Two runs MUST be reproducible —
  customers will ask "where did Acme Aerospace go?" after a regen.
- ❌ **Skip the reset script.** Every demo will eventually go off-rails.
  Reset is the only thing standing between you and a 5-minute restart.
- ❌ **Skip the realism deny-list.** One real bank name slipping through
  is one customer SME caught mid-demo. Run the deny-list grep every time.
- ❌ **Bake in customer-shared internal data.** If a customer shared their
  policy doc for context, that data stays with them — never seed it into
  a demo dataset.

---

## See Also

| Skill | Use When |
|-------|----------|
| [`threadlight-design`](../threadlight-design/) | Produces spec § 4 + § 11d + the per-industry realism references |
| [`foundry-mcp-aca`](../foundry-mcp-aca/) | Serves the generated JSON via FastMCP (Option D) |
| [`threadlight-workspace-ui`](../threadlight-workspace-ui/) | Renders the same JSON in the operator workspace |
| [`foundry-iq`](../foundry-iq/) | If the spec also needs a Knowledge Base, that's separate — this skill is for transactional/relational data only |
| [`threadlight-deploy`](../threadlight-deploy/) | Wires seed + reset scripts into the deploy lifecycle |
