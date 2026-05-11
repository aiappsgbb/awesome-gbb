# Per-industry data generators — placeholder index

Each module owns the per-entity Faker generators for its industry.
SKILL.md describes the expected interface. These modules are canonized
during the corresponding pilot.

| Industry | Module | Status |
|----------|--------|--------|
| `_universal.py` | Shared utilities (shifted-name, valid-format-fake, log-normal helpers) | 📋 To draft alongside FSI |
| `fsi.py` | FSI banking + insurance (customers, accounts, transactions, sanctions, claims) | 🔶 Draft during KYC pilot |
| `retail.py` | Retail / CPG (products, SKUs, orders, returns, reviews) | 📋 During PIM pilot |
| `telco.py` | Telco (customers, MSISDNs, orders, faults, network elements) | 📋 During Order Fallout pilot |
| `mfg.py` | Mfg (suppliers, parts, BOMs, shipments, quality events) | 📋 During Supplier Risk pilot |

## Module interface

Each generator module exports:

```python
def generators() -> dict[str, Callable[[int, dict], list[dict]]]:
    """Return entity-name → generator-function mapping.

    Each generator function takes:
      n: int                 # how many records to generate
      overrides: dict        # spec § 11d per-entity overrides

    Returns: list of dict records matching spec § 4 schema.
    """
    return {
        "customers": gen_customers,
        "accounts": gen_accounts,
        # ...
    }
```

## How `threadlight-demo-data-factory` selects a module

```python
industry = spec["demo_data"]["industry"]  # e.g. "fsi-banking"
module_name = industry.split("-")[0]      # "fsi"
mod = importlib.import_module(f"references.generators.{module_name}")
generators = mod.generators()
```

## Universal utilities (shared across all generators)

`_universal.py` provides these helpers — every industry generator imports them:

- `shifted_name(industry, kind)` — produces a synonym-shifted brand/company name
- `valid_format_fake(kind)` — produces a format-valid but fake regulatory ID
  (SSN, IBAN, EIN, etc.)
- `log_normal(mean, std, clip)` — log-normal distributed sample
- `bimodal(modes, weights)` — bimodal cluster sample
- `splice_golden(records, golden_cases, key)` — replaces records by ID with
  the hand-curated golden cases

## Adding a new industry generator

1. Add a file `references/generators/{industry}.py`
2. Implement `generators()` with one function per entity in the spec
3. Use `_universal.py` helpers for distributions and naming
4. Add the corresponding `references/data-realism/{industry}.md` (in
   `threadlight-design`) with industry-specific rules
5. Test with a sample spec: `uv run scripts/seed_data.py --industry {industry}`
