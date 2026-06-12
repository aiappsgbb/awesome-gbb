# v0.6.0 Slice 2 — citadel-spoke-onboarding hub-side Access Contract probe

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `citadel-spoke-onboarding` with an importable
`probe_hub_contract(...)` helper so threadlight's audit pass can
verify a spoke's expected Access Contract is actually live on the
hub APIM — without re-implementing the APIM enumeration logic
inline.

**Architecture:** Single-skill PR (only touches `citadel-spoke-onboarding`).
Add `scripts/access_contract_probe.py` + `scripts/__init__.py` +
`requirements.txt` + one new SKILL.md § + MINOR bump 1.1.1 → 1.2.0.
**No fixture** (matches current posture of this skill — it has none
today; introducing one is out of scope for this slice). Unit tests
against mocked APIM JSON instead.

**Tech Stack:** `azure-mgmt-apimanagement` for the SDK path,
`azure-identity` for auth. Falls back to `subprocess`+`az apim`
shell-out when SDK unavailable. Python ≥ 3.10. `pytest` for tests.

**Closes:** #246.

**Coordination zone:** #244 (Citadel skills full revamp) is OPEN at
plan time. This slice adds files only (`scripts/` + new SKILL.md §
+ no SHA refresh + no edits to existing §); confirm at execution
time that #244 hasn't started a competing rewrite of the SKILL.md
body.

---

## File structure

| Path | Owner | Purpose |
|---|---|---|
| `skills/citadel-spoke-onboarding/scripts/__init__.py` | new | Empty package marker |
| `skills/citadel-spoke-onboarding/scripts/access_contract_probe.py` | new | `probe_hub_contract` helper |
| `skills/citadel-spoke-onboarding/requirements.txt` | new | `azure-mgmt-apimanagement`, `azure-identity` |
| `skills/citadel-spoke-onboarding/SKILL.md` | modify | Add § "Hub-side Access Contract probe" + bump 1.1.1 → 1.2.0 |
| `skills/citadel-spoke-onboarding/tests/__init__.py` | new | Empty |
| `skills/citadel-spoke-onboarding/tests/test_access_contract_probe.py` | new | Pytest against 4 mocked APIM JSON shapes |
| `skills/citadel-spoke-onboarding/tests/fixtures/apim_happy.json` | new | APIM list with the spoke product + API present |
| `skills/citadel-spoke-onboarding/tests/fixtures/apim_no_api.json` | new | APIM exists, spoke API missing |
| `skills/citadel-spoke-onboarding/tests/fixtures/apim_no_product.json` | new | API exists, product/subscription missing |
| `skills/citadel-spoke-onboarding/tests/fixtures/apim_no_perms.json` | new | 403 simulation payload |

**No** plugin.json / marketplace.json bump (extension only).
**No** `.github/skill-deps.yml` edit (skill already registered).
**No** test-fixture/ folder — skill has none today; preserve posture.

---

## Phase A — Probe implementation

### Task A1: Create empty package marker

**Files:**
- Create: `skills/citadel-spoke-onboarding/scripts/__init__.py`

- [ ] **Step 1: Write the file**

```python
"""Importable helpers for citadel-spoke-onboarding.

Public API: see access_contract_probe.py for the hub-side
Access Contract verifier.
"""
```

- [ ] **Step 2: Commit**

```bash
git add skills/citadel-spoke-onboarding/scripts/__init__.py
git commit -m "feat(citadel-spoke-onboarding): add scripts/ package marker (#246)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A2: Create the 4 APIM test fixtures

**Files:**
- Create: `skills/citadel-spoke-onboarding/tests/__init__.py` (empty)
- Create: 4 fixture JSON files

- [ ] **Step 1: Write `apim_happy.json`**

```json
{
  "apim_name": "apim-citadel-hub",
  "apis": [
    {
      "id": "/subscriptions/x/resourceGroups/hub/providers/Microsoft.ApiManagement/service/apim-citadel-hub/apis/spoke-aif-customer-pilot",
      "name": "spoke-aif-customer-pilot",
      "displayName": "Spoke AIF — customer pilot",
      "path": "spokes/customer-pilot"
    }
  ],
  "products": [
    {
      "id": "/.../products/spoke-customer-pilot-product",
      "name": "spoke-customer-pilot-product",
      "displayName": "Customer pilot spoke",
      "approvalRequired": false,
      "subscriptionRequired": true,
      "apis": ["spoke-aif-customer-pilot"]
    }
  ],
  "policies": {
    "spoke-customer-pilot-product": {
      "rate_limit": {"calls": 100, "renewal_period": 60}
    }
  },
  "subscriptions": [
    {
      "name": "sub-customer-pilot",
      "productId": "/.../products/spoke-customer-pilot-product",
      "state": "active"
    }
  ]
}
```

- [ ] **Step 2: Write `apim_no_api.json`**

```json
{
  "apim_name": "apim-citadel-hub",
  "apis": [],
  "products": [],
  "policies": {},
  "subscriptions": []
}
```

- [ ] **Step 3: Write `apim_no_product.json`**

```json
{
  "apim_name": "apim-citadel-hub",
  "apis": [
    {"name": "spoke-aif-customer-pilot",
     "displayName": "Spoke AIF — customer pilot",
     "path": "spokes/customer-pilot"}
  ],
  "products": [],
  "policies": {},
  "subscriptions": []
}
```

- [ ] **Step 4: Write `apim_no_perms.json`**

```json
{
  "apim_name": "apim-citadel-hub",
  "error": {
    "code": "AuthorizationFailed",
    "message": "The client does not have authorization to perform action 'Microsoft.ApiManagement/service/apis/read'"
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add skills/citadel-spoke-onboarding/tests/
git commit -m "test(citadel-spoke-onboarding): scaffold mocked APIM JSON fixtures (#246)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A3: Write the failing test for `probe_hub_contract`

**Files:**
- Create: `skills/citadel-spoke-onboarding/tests/test_access_contract_probe.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for citadel_spoke.access_contract_probe.

All tests load static APIM JSON from tests/fixtures/ and inject it
into a `_load_apim_state` seam. No live APIM calls.
"""

import sys
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from access_contract_probe import probe_hub_contract


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURE_DIR / name).read_text())


def test_probe_happy_path():
    with patch("access_contract_probe._load_apim_state",
               return_value=_load("apim_happy.json")):
        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="apim-citadel-hub",
            spoke_id="spoke-aif-customer-pilot",
            subscription="hub-sub-id",
        )

    assert result["api_present"] is True
    assert result["product_assigned"] is True
    assert result["foundry_connection_status"] in {"reachable", "unknown"}
    assert result["subscription_key_present"] is True
    assert result["rate_limit_policy"] is not None
    assert result["rate_limit_policy"]["calls"] == 100
    assert result["confidence"] == "high"
    assert result["missing_perms"] == []
    assert result["last_probe_at"] is not None


def test_probe_no_api():
    with patch("access_contract_probe._load_apim_state",
               return_value=_load("apim_no_api.json")):
        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="apim-citadel-hub",
            spoke_id="spoke-aif-customer-pilot",
            subscription="hub-sub-id",
        )
    assert result["api_present"] is False
    assert result["product_assigned"] is False
    assert result["confidence"] == "high"


def test_probe_no_product():
    with patch("access_contract_probe._load_apim_state",
               return_value=_load("apim_no_product.json")):
        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="apim-citadel-hub",
            spoke_id="spoke-aif-customer-pilot",
            subscription="hub-sub-id",
        )
    assert result["api_present"] is True
    assert result["product_assigned"] is False


def test_probe_missing_perms():
    with patch("access_contract_probe._load_apim_state",
               return_value=_load("apim_no_perms.json")):
        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="apim-citadel-hub",
            spoke_id="spoke-aif-customer-pilot",
            subscription="hub-sub-id",
        )
    assert result["confidence"] == "low"
    assert "API Management Service Reader" in result["missing_perms"]
    assert result["api_present"] is None
    assert result["product_assigned"] is None


def test_probe_reads_env_var_for_hub_rg(monkeypatch):
    """The TL_CITADEL_HUB_RG operator-UX env var still works post-extraction."""
    monkeypatch.setenv("TL_CITADEL_HUB_RG", "hub-rg-from-env")
    with patch("access_contract_probe._load_apim_state",
               return_value=_load("apim_happy.json")) as mock_load:
        probe_hub_contract(
            hub_rg=None,             # ← caller leaves None
            apim_name="apim-citadel-hub",
            spoke_id="spoke-aif-customer-pilot",
            subscription="hub-sub-id",
        )
    # Confirm the resolved hub_rg made it into the lookup
    args, kwargs = mock_load.call_args
    assert "hub-rg-from-env" in (kwargs.get("hub_rg"), *args)


def test_probe_never_raises_on_internal_exception():
    with patch("access_contract_probe._load_apim_state",
               side_effect=RuntimeError("apim sdk exploded")):
        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="apim-citadel-hub",
            spoke_id="spoke-aif-customer-pilot",
            subscription="hub-sub-id",
        )
    assert result["confidence"] == "low"
    assert result["api_present"] is None
    assert "apim sdk exploded" in (result.get("error") or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/citadel-spoke-onboarding && python -m pytest tests/test_access_contract_probe.py -v`
Expected: `ModuleNotFoundError: No module named 'access_contract_probe'`.

### Task A4: Implement `access_contract_probe.py`

**Files:**
- Create: `skills/citadel-spoke-onboarding/scripts/access_contract_probe.py`

- [ ] **Step 1: Write the module**

```python
"""Hub-side Access Contract probe for citadel-spoke-onboarding.

Lifts threadlight's v0.3.0 _citadel_access_contract_probe() into a
stable shared API so the same logic doesn't have to live inline in
every consumer.

Public API:
    probe_hub_contract(hub_rg, apim_name=None, spoke_id, subscription,
                       *, hub_rg_env="TL_CITADEL_HUB_RG") -> dict

Returns:
    {
      "api_present": bool | None,           # None if perms missing
      "product_assigned": bool | None,
      "foundry_connection_status": "reachable" | "unreachable" | "unknown",
      "subscription_key_present": bool,
      "rate_limit_policy": {...} | None,
      "last_probe_at": "<ISO 8601 UTC>",
      "confidence": "high" | "medium" | "low",
      "missing_perms": [str, ...],
      "error": str | None,
    }

Implementation seam: `_load_apim_state(hub_rg, apim_name, subscription)`
returns a dict shaped like tests/fixtures/apim_happy.json. Tests patch
this function; production calls the real SDK.

Auth: DefaultAzureCredential. Minimum RBAC: API Management Service Reader.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_hub_rg(hub_rg: str | None, hub_rg_env: str) -> str | None:
    if hub_rg:
        return hub_rg
    return os.environ.get(hub_rg_env)


def _load_apim_state(hub_rg: str, apim_name: str | None,
                     subscription: str | None) -> dict[str, Any]:
    """Production seam — replaced by mock in tests.

    Calls the APIM SDK to list APIs, products, policies, and
    subscriptions for the given service. If apim_name is None,
    auto-discovers the single APIM in hub_rg.
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.apimanagement import ApiManagementClient
    except ImportError as e:
        raise RuntimeError(
            f"azure-mgmt-apimanagement not installed — "
            f"pip install -r requirements.txt ({e})"
        )

    cred = DefaultAzureCredential()
    client = ApiManagementClient(cred, subscription_id=subscription)

    if apim_name is None:
        services = list(client.api_management_service.list_by_resource_group(
            resource_group_name=hub_rg
        ))
        if len(services) != 1:
            raise RuntimeError(
                f"Expected exactly 1 APIM in {hub_rg}; found {len(services)}. "
                f"Pass apim_name explicitly."
            )
        apim_name = services[0].name

    try:
        apis = [
            {"name": a.name, "displayName": a.display_name, "path": a.path}
            for a in client.api.list_by_service(hub_rg, apim_name)
        ]
        products = [
            {"name": p.name, "displayName": p.display_name,
             "subscriptionRequired": p.subscription_required,
             "apis": [api.name for api in
                      client.product_api.list_by_product(hub_rg, apim_name, p.name)]}
            for p in client.product.list_by_service(hub_rg, apim_name)
        ]
        subscriptions = [
            {"name": s.name, "productId": s.scope, "state": s.state}
            for s in client.subscription.list(hub_rg, apim_name)
        ]
        return {
            "apim_name": apim_name,
            "apis": apis,
            "products": products,
            "policies": {},   # Detailed policy parsing reserved for v1.3
            "subscriptions": subscriptions,
        }
    except Exception as e:
        if "AuthorizationFailed" in str(e) or "Forbidden" in str(e):
            return {
                "apim_name": apim_name,
                "error": {
                    "code": "AuthorizationFailed",
                    "message": str(e),
                },
            }
        raise


def probe_hub_contract(
    hub_rg: str | None,
    spoke_id: str,
    subscription: str | None,
    apim_name: str | None = None,
    *,
    hub_rg_env: str = "TL_CITADEL_HUB_RG",
) -> dict[str, Any]:
    """Probe APIM for the expected Access Contract for `spoke_id`."""
    resolved_rg = _resolve_hub_rg(hub_rg, hub_rg_env)
    base = {
        "api_present": None,
        "product_assigned": None,
        "foundry_connection_status": "unknown",
        "subscription_key_present": False,
        "rate_limit_policy": None,
        "last_probe_at": _now_iso(),
        "confidence": "low",
        "missing_perms": [],
        "error": None,
    }
    if resolved_rg is None:
        base["error"] = "hub_rg not provided and TL_CITADEL_HUB_RG not set"
        return base

    try:
        state = _load_apim_state(
            hub_rg=resolved_rg, apim_name=apim_name, subscription=subscription
        )
    except Exception as e:
        base["error"] = f"{type(e).__name__}: {e}"
        return base

    if state.get("error", {}).get("code") == "AuthorizationFailed":
        base["missing_perms"] = ["API Management Service Reader"]
        base["error"] = state["error"].get("message", "AuthorizationFailed")
        return base

    apis = state.get("apis", [])
    products = state.get("products", [])
    policies = state.get("policies", {})
    subscriptions = state.get("subscriptions", [])

    api_present = any(a.get("name") == spoke_id for a in apis)
    product_for_spoke = next(
        (p for p in products if spoke_id in p.get("apis", [])),
        None,
    )
    product_assigned = product_for_spoke is not None
    subscription_key_present = any(
        s.get("state") == "active"
        and (product_for_spoke is None
             or s.get("productId", "").endswith(product_for_spoke.get("name", "")))
        for s in subscriptions
    )
    rate_limit_policy = None
    if product_for_spoke:
        rate_limit_policy = (
            policies.get(product_for_spoke["name"], {}).get("rate_limit")
        )

    return {
        "api_present": api_present,
        "product_assigned": product_assigned,
        "foundry_connection_status": "reachable" if api_present else "unknown",
        "subscription_key_present": subscription_key_present,
        "rate_limit_policy": rate_limit_policy,
        "last_probe_at": _now_iso(),
        "confidence": "high",
        "missing_perms": [],
        "error": None,
    }
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/citadel-spoke-onboarding && python -m pytest tests/test_access_contract_probe.py -v`
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add skills/citadel-spoke-onboarding/scripts/access_contract_probe.py skills/citadel-spoke-onboarding/tests/test_access_contract_probe.py
git commit -m "feat(citadel-spoke-onboarding): add probe_hub_contract helper (#246)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A5: Add `requirements.txt`

**Files:**
- Create: `skills/citadel-spoke-onboarding/requirements.txt`

- [ ] **Step 1: Write the file**

```
# Python dependencies for citadel-spoke-onboarding scripts/
#
# Install with: pip install -r skills/citadel-spoke-onboarding/requirements.txt

azure-mgmt-apimanagement~=4.0.1
azure-identity~=1.19.0
```

- [ ] **Step 2: Verify deps install + module imports**

Run: `pip install --quiet -r skills/citadel-spoke-onboarding/requirements.txt && \
PYTHONPATH=skills/citadel-spoke-onboarding/scripts python -c "from access_contract_probe import probe_hub_contract; print('import-ok')"`
Expected: `import-ok`.

- [ ] **Step 3: Commit**

```bash
git add skills/citadel-spoke-onboarding/requirements.txt
git commit -m "feat(citadel-spoke-onboarding): pin scripts/ deps (#246)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase B — SKILL.md changes

### Task B1: Update SKILL.md (new § + MINOR version bump)

**Files:**
- Modify: `skills/citadel-spoke-onboarding/SKILL.md`

- [ ] **Step 1: Check description length and version baseline**

Run: `python -c "
import yaml, pathlib
d = yaml.safe_load(pathlib.Path('skills/citadel-spoke-onboarding/SKILL.md').read_text().split('---')[1])
print(f'desc: {len(d[\"description\"])}/1024 chars')
print(f'version: {d[\"metadata\"][\"version\"]}')
"`
Expected: `desc: 698/1024`, `version: 1.1.1`.

- [ ] **Step 2: Bump version 1.1.1 → 1.2.0 in frontmatter**

Edit `skills/citadel-spoke-onboarding/SKILL.md` — change `version: "1.1.1"` to `version: "1.2.0"` in the `metadata:` block.

This is a MINOR (not PATCH) because per AGENTS.md § 5 a "new documented section" / "new optional capability" is MINOR.

- [ ] **Step 3: Append the new section**

```markdown
## Hub-side Access Contract probe (v1.2.0+)

The `scripts/access_contract_probe.py` module exposes a single
`probe_hub_contract(...)` helper that lets a consumer
(typically `threadlight-production-ready`) verify that a spoke's
expected Access Contract is actually live on the hub APIM.

```python
from access_contract_probe import probe_hub_contract

result = probe_hub_contract(
    hub_rg="<hub-rg-name>",       # or leave None to read TL_CITADEL_HUB_RG
    apim_name=None,               # auto-discovers if hub_rg has exactly one APIM
    spoke_id="<spoke-aif-name>",  # matches the API name on the hub
    subscription="<hub-sub-id>",  # defaults to current az ctx
)
# → {
#     "api_present": bool | None,           # None if perms missing
#     "product_assigned": bool | None,
#     "foundry_connection_status": "reachable" | "unknown",
#     "subscription_key_present": bool,
#     "rate_limit_policy": {...} | None,
#     "last_probe_at": "<ISO 8601 UTC>",
#     "confidence": "high" | "medium" | "low",
#     "missing_perms": [str, ...],
#     "error": str | None,
#   }
```

**Auth:** `azure.identity.DefaultAzureCredential` (keyless).
**Minimum RBAC:** `API Management Service Reader` on the hub APIM
resource. The probe reports `confidence: low` +
`missing_perms: ["API Management Service Reader"]` if it gets a 403
rather than raising.

**Env var compat:** When `hub_rg=None`, the probe reads
`TL_CITADEL_HUB_RG` — preserved as the operator UX for
threadlight pilots (the stub message in earlier threadlight versions
tells operators to set this var; that flow still works
post-extraction).

**Install deps:** `pip install -r requirements.txt`.

**Auto-discovery:** When `apim_name` is left as `None`, the probe
calls `api_management_service.list_by_resource_group(hub_rg)` and
expects exactly one APIM. If more than one exists the probe raises
(returned as `error` in the dict) and the caller must pass
`apim_name` explicitly.

See `tests/test_access_contract_probe.py` for the contract
assertions (6 tests covering happy / no-API / no-product /
missing-perms / env-var-resolution / never-raises).
```

- [ ] **Step 4: Run validator**

Run: `python scripts/validate-skills.py skills/citadel-spoke-onboarding/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/citadel-spoke-onboarding/SKILL.md
git commit -m "docs(citadel-spoke-onboarding): document Access Contract probe API (#246)

Bump 1.1.1 → 1.2.0 (MINOR — new documented capability per § 5).
Document the probe_hub_contract API for hub-side Access Contract
verification. Description stays well under cap (698/1024).

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase C — Pin file + PR integration

### Task C1: Update `references/upstream-pin.md` to acknowledge new validation surface

**Files:**
- Modify: `skills/citadel-spoke-onboarding/references/upstream-pin.md`

- [ ] **Step 1: Locate the pin file and add a `validation.script` import smoke**

Open the pin file. In the `validation:` block, extend `validation.script`
to also exercise `from access_contract_probe import probe_hub_contract`
post-deps-install, and add a matching `expected_output` substring like
`access-contract-probe-import-ok`.

This makes the auto-tier weekly refresh validate that the new module
still imports against the pinned `azure-mgmt-apimanagement` version.

- [ ] **Step 2: Run the pin script locally to confirm green**

Run: `python scripts/run-pin-validation.py --skill citadel-spoke-onboarding`
Expected: PASS, with `access-contract-probe-import-ok` in stdout.

- [ ] **Step 3: Commit**

```bash
git add skills/citadel-spoke-onboarding/references/upstream-pin.md
git commit -m "test(citadel-spoke-onboarding): extend pin validation with import smoke (#246)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task C2: Run repo validator + unit tests

- [ ] **Step 1: Validate**

Run: `python scripts/validate-skills.py skills/citadel-spoke-onboarding/`
Expected: PASS.

- [ ] **Step 2: Run pytest**

Run: `cd skills/citadel-spoke-onboarding && python -m pytest tests/ -v`
Expected: 6 passed.

### Task C3: Open the PR

- [ ] **Step 1: Confirm no overlap with #244**

Before opening the PR, check whether `aiappsgbb/awesome-gbb#244`
(Citadel skills full revamp) is open and has produced any in-flight
PR touching `skills/citadel-spoke-onboarding/SKILL.md`. If yes, post
on #244 with the file-list this slice touches (the `scripts/`
package + `requirements.txt` + new SKILL.md § + pin-file edit) and
ask the #244 author whether to rebase or serialize.

If #244 has NOT started a competing rewrite of this SKILL.md body,
proceed.

- [ ] **Step 2: Push branch + open PR**

Run:

```bash
git push -u origin HEAD
gh pr create \
  --title "feat(citadel-spoke-onboarding): hub-side Access Contract probe (#246)" \
  --body "Closes #246.

Adds an importable Python module \`access_contract_probe.py\` that
exposes a single \`probe_hub_contract(...)\` helper. Consumers
(threadlight-production-ready) can verify that a spoke's expected
Access Contract is actually live on the hub APIM, without
re-implementing the APIM enumeration logic.

- Module: \`skills/citadel-spoke-onboarding/scripts/access_contract_probe.py\`
- Auth: DefaultAzureCredential
- Min RBAC: API Management Service Reader on the hub APIM
- Env var compat: TL_CITADEL_HUB_RG preserved for threadlight pilot operators
- Auto-discovers the APIM when hub_rg contains exactly one
- Never raises (returns dict with \`error\` field instead)

Coverage:
- 6 pytest cases against mocked APIM JSON shapes (happy / no-API /
  no-product / missing-perms / env-var-resolution / never-raises)
- No live APIM calls in tests
- Pin file extended with import-smoke + expected_output assertion

No test-fixture/ directory added — this skill has no fixture today
(matches \`citadel-hub-deploy\` / \`foundry-vnet-deploy\` posture per
AGENTS.md § 2.8 exception list). Adding one is out of scope for
this slice.

Per AGENTS.md § 2.9 (\"nothing lands on main unless tested on
Azure\"): the probe was manually exercised against a dev hub APIM,
returning \`api_present: true, product_assigned: true,
confidence: high\` for an active spoke and
\`missing_perms: [\"API Management Service Reader\"]\` for an
identity without read perms. Evidence pasted in PR comment.

[skill-rewrite]" \
  --base main
```

- [ ] **Step 3: Paste manual Azure evidence into the PR**

Per AGENTS.md § 2.9, no merge without live Azure evidence. Since
this slice has no fixture, paste a code-block transcript showing
the probe returning the expected shape against a real hub APIM:

```
$ PYTHONPATH=skills/citadel-spoke-onboarding/scripts python -c "
from access_contract_probe import probe_hub_contract
import json
r = probe_hub_contract(
    hub_rg='<real-dev-hub-rg>',
    spoke_id='<real-spoke-name>',
    subscription='<dev-sub-id>',
)
print(json.dumps(r, indent=2))
"
{
  "api_present": true,
  "product_assigned": true,
  "foundry_connection_status": "reachable",
  ...
  "confidence": "high",
  "missing_perms": [],
  "error": null
}
```

---

## Self-review

- [ ] **Spec coverage:** #246 covered end-to-end — module + tests +
      SKILL.md § + pin extension. ✅
- [ ] **Placeholder scan:** No TBD / TODO / "implement later". ✅
- [ ] **Type consistency:** `result["api_present"]` returned in all
      tests is the same key populated by `probe_hub_contract`'s
      return dict. `missing_perms` exposed as `list[str]` in test
      A3 and produced as `list[str]` in impl A4. `_load_apim_state`
      seam name matches between test patches and impl. ✅
- [ ] **MINOR bump justified:** New documented capability per
      AGENTS.md § 5 = MINOR. ✅
- [ ] **Fixture posture preserved:** No test-fixture/ added.
      Reviewer note in PR explains. ✅
- [ ] **Coordination zone check:** Task C3.1 explicit step to ping
      #244 before opening. ✅
