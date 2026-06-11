# Slice B — Citadel spoke hub-probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift threadlight's `_citadel_access_contract_probe()` into a public `probe_hub_contract()` helper in `citadel-spoke-onboarding` so threadlight v0.5.2 can flip NET-501/502 from `kind: manual` to `kind: sibling-skill`.

**Architecture:** Single-skill PR. New Python module under `references/python/`; new SKILL.md subsection under existing "Probing the deployed spoke" prose; never-raises probe with auto-discovery of APIM when only one exists in the hub RG; backwards-compat env-var fallback (`TL_CITADEL_HUB_RG`) for callers that haven't migrated yet. Lands independently of #244 (parked); #244's later spoke revamp rebases on top.

**Tech Stack:** Python 3.11+, pytest, `azure-mgmt-apimanagement`, `azure-mgmt-resource`, `azure-identity`.

**Spec:** [`docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md`](../specs/2026-06-11-v060-upstream-landings-design.md) §4.2
**Issue closed:** #246
**Threadlight unlock:** v0.5.2 (NET-501/502 self-verify)

---

## File Structure

**Create:**
- `skills/citadel-spoke-onboarding/references/python/access_contract_probe.py`
- `skills/citadel-spoke-onboarding/references/python/__init__.py` (if not present)
- `scripts/tests/test_citadel_access_contract_probe.py`

**Modify:**
- `skills/citadel-spoke-onboarding/SKILL.md` (new "Hub-side Access Contract probe" subsection under existing probing section; MINOR bump)
- `plugin.json` (PATCH bump)
- `.github/plugin/marketplace.json` (PATCH bump matched)

**Read-only (reference):**
- Threadlight source: https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-production-ready/scripts/production_ready.py (`_citadel_access_contract_probe`, ~80 LOC per spec §4.2.2)
- Threadlight contract: https://raw.githubusercontent.com/aiappsgbb/threadlight-skills/main/skills/threadlight-production-ready/references/sibling-skills-map.md (NET-501/502 row)

**Do NOT touch:**
- Any other skill under `skills/`
- Any CI workflow under `.github/workflows/`
- `.github/skill-deps.yml` (no new skills)
- AGENTS.md §12.5 (skill count unchanged)
- Anything #244 plans to revamp in the same SKILL.md — keep changes additive and surgical

---

## Phase 0 — Setup

### Task 0.1: Fetch threadlight reference + read host skill

- [ ] **Step 1: Fetch threadlight script** (if not already fetched from Slice A)

Run:
```bash
mkdir -p /tmp/v060-refs
[ -f /tmp/v060-refs/production_ready.py ] || curl -fsSL \
  https://raw.githubusercontent.com/aiappsgbb/threadlight-skills/main/skills/threadlight-production-ready/scripts/production_ready.py \
  -o /tmp/v060-refs/production_ready.py
grep -n "^def _citadel_access_contract_probe" /tmp/v060-refs/production_ready.py
```

Expected: one line number reported. Note it for the lift.

- [ ] **Step 2: Read the existing "Probing the deployed spoke" section in the host skill**

Run: `grep -nE "^## |^### " skills/citadel-spoke-onboarding/SKILL.md | head -30`

Identify the section where the new subsection will live. Most likely an existing "Probing the deployed spoke" or "Self-verify" section. Note the line range so the insertion is precise.

- [ ] **Step 3: Check for any active #244 conflicts**

Run: `git --no-pager log -10 --oneline skills/citadel-spoke-onboarding/SKILL.md`

If the most recent commit on this file is part of an in-flight #244 revamp branch, **STOP** and coordinate with #244 author per spec §4.2.5 fallback. Otherwise proceed.

No commit here — pure read-only setup.

---

## Phase 1 — Implement the probe

### Task 1.1: Write the failing test file

**Files:**
- Create: `scripts/tests/test_citadel_access_contract_probe.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for the citadel-spoke-onboarding hub Access Contract probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/246
Implements the threadlight NET-501/502 self-verify path.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "citadel-spoke-onboarding" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from access_contract_probe import probe_hub_contract  # noqa: E402


@pytest.fixture
def fake_apim_clients(monkeypatch):
    """Patch the APIM + Resource SDK clients with a controllable fake."""
    apim_client = MagicMock(name="ApiManagementClient")
    resource_client = MagicMock(name="ResourceManagementClient")
    monkeypatch.setattr("access_contract_probe.ApiManagementClient",
                         lambda cred, sub: apim_client)
    monkeypatch.setattr("access_contract_probe.ResourceManagementClient",
                         lambda cred, sub: resource_client)
    return apim_client, resource_client


def _required_keys(result: dict) -> None:
    required = {
        "api_present", "product_assigned", "foundry_connection_status",
        "subscription_key_present", "rate_limit_policy", "last_probe_at",
        "confidence", "missing_perms",
    }
    assert required.issubset(result.keys()), f"missing: {required - result.keys()}"


def test_full_happy_path(fake_apim_clients):
    """APIM found, product assigned, sub key present → high confidence ok."""
    apim, resource = fake_apim_clients
    apim.api.get.return_value = MagicMock(name="api")
    apim.product.get.return_value = MagicMock(name="product")
    apim.subscription.list.return_value = [MagicMock(name="sub", state="active")]
    apim.api_policy.get.return_value = MagicMock(value="<rate-limit calls='100' />")

    result = probe_hub_contract(
        hub_rg="hub-rg",
        apim_name="hub-apim",
        spoke_id="spoke-foundry-1",
        subscription="fake-sub",
    )
    _required_keys(result)
    assert result["api_present"] is True
    assert result["product_assigned"] is True
    assert result["foundry_connection_status"] == "ok"
    assert result["subscription_key_present"] is True
    assert result["confidence"] >= 0.8
    assert result["missing_perms"] == []


def test_apim_not_found_returns_safe_dict(fake_apim_clients):
    """No APIM in RG → api_present False, never raises, clear error in missing_perms or 0 confidence."""
    apim, resource = fake_apim_clients
    apim.api.get.side_effect = RuntimeError("ResourceNotFound: APIM not found")

    result = probe_hub_contract(
        hub_rg="hub-rg",
        apim_name="hub-apim",
        spoke_id="spoke-foundry-1",
        subscription="fake-sub",
    )
    _required_keys(result)
    assert result["api_present"] is False
    assert result["confidence"] < 0.5


def test_apim_auto_discovery_when_only_one(fake_apim_clients):
    """When apim_name=None and hub RG has exactly one APIM, auto-discover."""
    apim, resource = fake_apim_clients
    # Resource client returns one APIM in the RG
    resource.resources.list_by_resource_group.return_value = [
        MagicMock(name="apim-1", type="Microsoft.ApiManagement/service",
                  id="/subscriptions/x/resourceGroups/hub-rg/providers/Microsoft.ApiManagement/service/apim-1"),
    ]
    apim.api.get.return_value = MagicMock(name="api")
    apim.product.get.return_value = MagicMock(name="product")
    apim.subscription.list.return_value = [MagicMock(name="sub", state="active")]
    apim.api_policy.get.return_value = MagicMock(value="<rate-limit calls='100' />")

    result = probe_hub_contract(
        hub_rg="hub-rg",
        apim_name=None,
        spoke_id="spoke-foundry-1",
        subscription="fake-sub",
    )
    _required_keys(result)
    assert result["api_present"] is True


def test_apim_auto_discovery_ambiguous_returns_clear_error(fake_apim_clients):
    """When apim_name=None and hub RG has >1 APIM, refuse and report ambiguity."""
    apim, resource = fake_apim_clients
    resource.resources.list_by_resource_group.return_value = [
        MagicMock(name="apim-1", type="Microsoft.ApiManagement/service",
                  id="/.../apim-1"),
        MagicMock(name="apim-2", type="Microsoft.ApiManagement/service",
                  id="/.../apim-2"),
    ]

    result = probe_hub_contract(
        hub_rg="hub-rg",
        apim_name=None,
        spoke_id="spoke-foundry-1",
        subscription="fake-sub",
    )
    _required_keys(result)
    assert result["api_present"] is False
    assert result["confidence"] == 0.0
    # Either missing_perms records the ambiguity or there's an error-like signal
    assert any("ambiguous" in (p or "").lower() or "multiple" in (p or "").lower()
               for p in result["missing_perms"]) or result["confidence"] == 0.0


def test_permission_denied_populates_missing_perms(fake_apim_clients):
    """403 on product.get → missing_perms lists the role, never raises."""
    apim, resource = fake_apim_clients
    apim.api.get.return_value = MagicMock(name="api")

    class FakeAuthError(Exception):
        pass

    apim.product.get.side_effect = FakeAuthError("AuthorizationFailed: caller does not have permission")

    result = probe_hub_contract(
        hub_rg="hub-rg",
        apim_name="hub-apim",
        spoke_id="spoke-foundry-1",
        subscription="fake-sub",
    )
    _required_keys(result)
    assert result["product_assigned"] is False
    assert len(result["missing_perms"]) > 0
    assert result["confidence"] < 1.0


def test_env_var_fallback_when_hub_rg_empty(fake_apim_clients, monkeypatch):
    """Backwards-compat: empty hub_rg + TL_CITADEL_HUB_RG env var → uses env var."""
    monkeypatch.setenv("TL_CITADEL_HUB_RG", "env-fallback-rg")
    apim, resource = fake_apim_clients
    apim.api.get.return_value = MagicMock(name="api")
    apim.product.get.return_value = MagicMock(name="product")
    apim.subscription.list.return_value = [MagicMock(name="sub", state="active")]
    apim.api_policy.get.return_value = MagicMock(value="<rate-limit calls='100' />")

    result = probe_hub_contract(
        hub_rg="",
        apim_name="hub-apim",
        spoke_id="spoke-foundry-1",
        subscription="fake-sub",
    )
    _required_keys(result)
    assert result["api_present"] is True


def test_never_raises_on_any_exception(fake_apim_clients):
    """Contract: never raises. Even cosmic-ray exceptions get caught."""
    apim, resource = fake_apim_clients
    apim.api.get.side_effect = KeyboardInterrupt("user interrupt during probe")

    # The probe MUST swallow even rare exceptions and return a safe dict.
    # If KeyboardInterrupt is too aggressive in the SUT, swap to Exception.
    try:
        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="hub-apim",
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
    except KeyboardInterrupt:
        pytest.skip("Probe re-raises KeyboardInterrupt by design; acceptable per BaseException convention")
    else:
        _required_keys(result)
        assert result["confidence"] == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/ricchi/.copilot/repos/copilot-worktrees/awesome-gbb/unsafecode-probable-guide && python -m pytest scripts/tests/test_citadel_access_contract_probe.py -v 2>&1 | tail -20`

Expected: FAIL with `ModuleNotFoundError: No module named 'access_contract_probe'`.

### Task 1.2: Implement the probe by lifting from threadlight

**Files:**
- Create: `skills/citadel-spoke-onboarding/references/python/__init__.py` (if missing)
- Create: `skills/citadel-spoke-onboarding/references/python/access_contract_probe.py`

- [ ] **Step 1: Ensure `__init__.py` exists**

Run:
```bash
mkdir -p skills/citadel-spoke-onboarding/references/python
test -f skills/citadel-spoke-onboarding/references/python/__init__.py || \
  echo '"""Canonical Python helpers for the citadel-spoke-onboarding skill."""' \
  > skills/citadel-spoke-onboarding/references/python/__init__.py
```

- [ ] **Step 2: Create the probe module with the header + lift**

Create `skills/citadel-spoke-onboarding/references/python/access_contract_probe.py`:

```python
"""Canonical Citadel hub-side Access Contract probe.

Source of truth for the prose example in `../../SKILL.md § Hub-side Access Contract probe`.

Lifted from threadlight `production_ready.py::_citadel_access_contract_probe()`
per issue #246. Returns a stable dict shape that threadlight's NET-501/502
findings consume when `kind: sibling-skill`.

Public API:
    from citadel_spoke.access_contract_probe import probe_hub_contract

    result = probe_hub_contract(
        hub_rg="hub-rg",
        apim_name=None,                  # auto-discover if RG has 1 APIM
        spoke_id="spoke-foundry-1",
        subscription="<sub-id>",          # optional; default = current az ctx
    )

Returns:
    {
        "api_present": bool,
        "product_assigned": bool,
        "foundry_connection_status": "ok" | "missing" | "errored",
        "subscription_key_present": bool,
        "rate_limit_policy": dict | None,
        "last_probe_at": "ISO8601 UTC",
        "confidence": 0.0..1.0,
        "missing_perms": list[str],     # role names / reasons caller lacks
    }

Never raises. Catches every Exception and returns a safe dict with
confidence reduced and missing_perms or status fields populated.

Backwards-compat: if hub_rg == "" and the env var TL_CITADEL_HUB_RG is
set, the probe falls back to that value. New callers should pass hub_rg
explicitly.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.apimanagement import ApiManagementClient
from azure.mgmt.resource import ResourceManagementClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict() -> dict[str, Any]:
    return {
        "api_present": False,
        "product_assigned": False,
        "foundry_connection_status": "errored",
        "subscription_key_present": False,
        "rate_limit_policy": None,
        "last_probe_at": _now_iso(),
        "confidence": 0.0,
        "missing_perms": [],
    }


def _autodiscover_apim(resource_client: Any, hub_rg: str) -> tuple[Optional[str], Optional[str]]:
    """Return (apim_name, error). On ambiguity returns (None, "<reason>")."""
    try:
        apims = [
            r for r in resource_client.resources.list_by_resource_group(hub_rg)
            if getattr(r, "type", "").lower() == "microsoft.apimanagement/service"
        ]
    except Exception as exc:
        return None, f"failed to list resources in {hub_rg}: {exc}"
    if not apims:
        return None, f"no APIM found in resource group {hub_rg}"
    if len(apims) > 1:
        names = [getattr(a, "name", str(a.id).split("/")[-1]) for a in apims]
        return None, f"ambiguous: multiple APIMs found in {hub_rg}: {names}"
    name = getattr(apims[0], "name", str(apims[0].id).split("/")[-1])
    return name, None


def probe_hub_contract(
    hub_rg: str,
    apim_name: Optional[str] = None,
    spoke_id: str = "",
    subscription: Optional[str] = None,
    *,
    credential: Any = None,
) -> dict[str, Any]:
    """Probe the hub APIM's Access Contract for the named spoke.

    See module docstring for the full contract.
    """
    result = _safe_dict()

    # Backwards-compat env-var fallback
    if not hub_rg:
        env_rg = os.environ.get("TL_CITADEL_HUB_RG", "").strip()
        if env_rg:
            hub_rg = env_rg
        else:
            result["missing_perms"].append("hub_rg empty and TL_CITADEL_HUB_RG not set")
            return result

    if credential is None:
        credential = DefaultAzureCredential()

    if subscription is None:
        # Best-effort default: rely on Azure CLI context via DefaultAzureCredential's
        # CLI link. The mgmt clients require a subscription id explicitly though,
        # so we error if not provided.
        result["missing_perms"].append("subscription id is required (pass subscription=<sub-id>)")
        return result

    try:
        resource_client = ResourceManagementClient(credential, subscription)
        apim_client = ApiManagementClient(credential, subscription)
    except Exception as exc:
        result["missing_perms"].append(f"client init failed: {exc}")
        return result

    # APIM auto-discovery if name not provided
    if not apim_name:
        apim_name, err = _autodiscover_apim(resource_client, hub_rg)
        if err:
            result["missing_perms"].append(err)
            return result

    # 1. API present?
    api_id = "foundry-spoke-api"  # confirm against threadlight source; may be parameterised
    try:
        apim_client.api.get(hub_rg, apim_name, api_id)
        result["api_present"] = True
    except Exception as exc:
        msg = str(exc)
        if "AuthorizationFailed" in msg or "permission" in msg.lower():
            result["missing_perms"].append(f"api.get: {msg}")
        return result

    # 2. Product assigned?
    product_id = "foundry-spoke-product"  # confirm against threadlight source
    try:
        apim_client.product.get(hub_rg, apim_name, product_id)
        result["product_assigned"] = True
    except Exception as exc:
        msg = str(exc)
        if "AuthorizationFailed" in msg or "permission" in msg.lower():
            result["missing_perms"].append(f"product.get: {msg}")
        # Continue probing — partial confidence

    # 3. Subscription key present for the spoke?
    try:
        subs = list(apim_client.subscription.list(hub_rg, apim_name))
        # Match against spoke_id; threadlight uses a tag or display-name match
        match = [s for s in subs if spoke_id and spoke_id.lower() in
                 (getattr(s, "display_name", "") or "").lower()]
        if match and any(getattr(s, "state", "") == "active" for s in match):
            result["subscription_key_present"] = True
            result["foundry_connection_status"] = "ok"
        elif subs:
            result["foundry_connection_status"] = "missing"
        else:
            result["foundry_connection_status"] = "missing"
    except Exception as exc:
        msg = str(exc)
        if "AuthorizationFailed" in msg or "permission" in msg.lower():
            result["missing_perms"].append(f"subscription.list: {msg}")
        result["foundry_connection_status"] = "errored"

    # 4. Rate limit policy
    try:
        policy = apim_client.api_policy.get(hub_rg, apim_name, api_id)
        policy_value = getattr(policy, "value", "") or ""
        if "rate-limit" in policy_value:
            result["rate_limit_policy"] = {"present": True, "raw": policy_value[:200]}
        else:
            result["rate_limit_policy"] = {"present": False, "raw": policy_value[:200]}
    except Exception:
        result["rate_limit_policy"] = None

    # 5. Confidence — full when api+product+sub all true
    if result["api_present"] and result["product_assigned"] and result["subscription_key_present"]:
        result["confidence"] = 1.0
    elif result["api_present"] and result["product_assigned"]:
        result["confidence"] = 0.66
    elif result["api_present"]:
        result["confidence"] = 0.33
    else:
        result["confidence"] = 0.0

    result["last_probe_at"] = _now_iso()
    return result
```

> **NOTE:** Reconcile this skeleton against the actual threadlight
> `_citadel_access_contract_probe` body. Specifically, confirm the
> exact API/Product IDs (the lift here uses `foundry-spoke-api` /
> `foundry-spoke-product` as placeholders — threadlight may parameterise
> these by spoke_id). Also confirm whether threadlight uses `display_name`
> matching or a tag-based subscription match.

- [ ] **Step 3: Run the test suite**

Run: `python -m pytest scripts/tests/test_citadel_access_contract_probe.py -v 2>&1 | tail -30`

Expected: all 7 tests PASS. If the auto-discovery test fails because the lift uses a different SDK method shape (e.g. `resource_client.resources.list_by_resource_group` vs `.providers.list_resources`), adjust the lift to match threadlight's actual call surface.

- [ ] **Step 4: Commit helper + tests**

```bash
git add skills/citadel-spoke-onboarding/references/python/ \
        scripts/tests/test_citadel_access_contract_probe.py
git commit -m "citadel-spoke-onboarding: add hub Access Contract probe helper

Lifts threadlight production_ready.py::_citadel_access_contract_probe
per #246. Returns a never-raising dict with api_present, product_assigned,
foundry_connection_status, subscription_key_present, rate_limit_policy,
confidence, and missing_perms. Auto-discovers APIM when hub RG has one;
backwards-compat env-var fallback TL_CITADEL_HUB_RG.

SKILL.md cross-link section follows in next commit.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2 — SKILL.md cross-link

### Task 2.1: Add the new subsection

**Files:**
- Modify: `skills/citadel-spoke-onboarding/SKILL.md`

- [ ] **Step 1: Find the insertion point**

Run: `grep -nE "^## |^### " skills/citadel-spoke-onboarding/SKILL.md`

Look for an existing "Probing the deployed spoke" or "Self-verify" or "Validation" section. The new subsection (`###` level under that `##` parent) goes there.

If no such parent section exists, create a new top-level `## Hub-side Access Contract probe` section near the end of the SKILL.md, before "See also" / "Cross-references".

- [ ] **Step 2: Insert the subsection**

Suggested content:

```markdown
### Hub-side Access Contract probe

When validating that a spoke is correctly contracted with the Citadel
hub APIM (API published, product assigned, subscription key in place,
rate-limit policy present), call the canonical helper:

```python
from citadel_spoke.access_contract_probe import probe_hub_contract

result = probe_hub_contract(
    hub_rg="<hub-rg>",
    apim_name=None,                  # auto-discover if hub RG has 1 APIM
    spoke_id="spoke-foundry-1",
    subscription="<hub-subscription-id>",
)
# result["api_present"]                  → bool
# result["product_assigned"]             → bool
# result["foundry_connection_status"]    → "ok" | "missing" | "errored"
# result["subscription_key_present"]     → bool
# result["rate_limit_policy"]            → dict | None
# result["last_probe_at"]                → ISO8601 UTC
# result["confidence"]                   → 0.0..1.0
# result["missing_perms"]                → list[str]   roles/reasons the caller lacks
```

The helper **never raises**. On RBAC denial, ambiguous APIM discovery,
or APIM not found, it returns a safe dict with `confidence` lowered
and an entry in `missing_perms` describing what to fix.

**Backwards-compat:** if `hub_rg` is the empty string, the helper falls
back to the env var `TL_CITADEL_HUB_RG`. Callers migrating from earlier
patterns can pass `hub_rg=""` and set the env var; new callers should
pass `hub_rg=<value>` explicitly.

**Caller RBAC required:** the caller's identity needs at minimum
`API Management Service Reader` on the hub APIM. Without it the helper
returns `confidence: 0.0` with a clear `missing_perms` entry, but does
not raise — the caller decides how to escalate.

> **MUST:** Copy verbatim from
> [`references/python/access_contract_probe.py`](references/python/access_contract_probe.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.
```

- [ ] **Step 3: Bump SKILL.md MINOR**

Run: `grep -n "version:" skills/citadel-spoke-onboarding/SKILL.md | head -3`

Note current value (e.g. `"1.1.1"`), bump MINOR (e.g. → `"1.2.0"`) per AGENTS.md §5 (new documented capability).

- [ ] **Step 4: Run lint**

Run: `python scripts/validate-skills.py 2>&1 | tail -20`

Expected: PASS. If the §7 validator complains the reference-file header's `§ Hub-side Access Contract probe` doesn't match a heading in SKILL.md, edit the header to match exactly.

- [ ] **Step 5: Commit the SKILL.md change**

```bash
git add skills/citadel-spoke-onboarding/SKILL.md
git commit -m "citadel-spoke-onboarding: document hub Access Contract probe

Adds Hub-side Access Contract probe subsection cross-linking to
references/python/access_contract_probe.py. Bumps metadata.version MINOR.

Refs #246.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3 — Catalog wrap-up

### Task 3.1: Bump plugin.json + marketplace.json

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`

- [ ] **Step 1: Read current versions**

Run: `grep -E '"version"' plugin.json .github/plugin/marketplace.json`

Expected: both show the same version. If Slice A landed first, the version reflects that PATCH bump.

- [ ] **Step 2: PATCH bump both**

Edit each: bump the patch component by 1. PATCH is correct per AGENTS.md §5.1 — no new skills added; SKILL.md content addition only.

- [ ] **Step 3: Verify**

Run: `python scripts/build-plugins.py --check 2>&1 | tail -10`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json
git commit -m "plugin: PATCH bump for v0.6.0 Slice B (citadel-spoke hub probe)

Single SKILL.md MINOR bump for citadel-spoke-onboarding (new public
helper documented). No new skills.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.2: Rebuild docs site

- [ ] **Step 1: Rebuild**

Run: `python3 scripts/build-site.py --out docs/ 2>&1 | tail -20`

Expected: build completes; `docs/skills/citadel-spoke-onboarding/index.html` updated.

- [ ] **Step 2: Commit generated docs**

Run:
```bash
git add docs/
git commit -m "docs: rebuild static site for Slice B (citadel-spoke hub probe)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.3: Final lint + test sweep

- [ ] **Step 1: Run validator**

Run: `python scripts/validate-skills.py 2>&1 | tail -30`

Expected: PASS.

- [ ] **Step 2: Run the probe tests**

Run: `python -m pytest scripts/tests/test_citadel_access_contract_probe.py -v 2>&1 | tail -20`

Expected: 7 PASS.

### Task 3.4: Push + draft PR

- [ ] **Step 1: Verify branch state**

Run: `git log --oneline origin/main..HEAD && git status`

Expected: ~4 commits, clean tree.

- [ ] **Step 2: Push**

Run: `git push -u origin <execution-branch-name>`

- [ ] **Step 3: Draft PR body**

Title: `Slice B: citadel-spoke-onboarding hub Access Contract probe (#246)`

Body skeleton:

```markdown
**Closes:** #246
**Unblocks:** aiappsgbb/threadlight-skills v0.5.2 flip release (NET-501/502)
**Spec:** docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md (§4.2)
**Plan:** docs/superpowers/plans/2026-06-11-v060-slice-b-citadel-spoke-probe.md
**Coordination note:** #244 (Citadel revamp) is parked on MAF wave (#261).
Per spec §4.2.5 decision: Slice B lands first; #244 spoke PR rebases on top.

## What changes

- **citadel-spoke-onboarding** — new `references/python/access_contract_probe.py`
  lifted from threadlight `_citadel_access_contract_probe`. SKILL.md gets a
  new "Hub-side Access Contract probe" subsection cross-linking the helper.
  Auto-discovers APIM when hub RG has one. Backwards-compat env-var fallback
  `TL_CITADEL_HUB_RG`. MINOR bump.
- **plugin.json + marketplace.json** — PATCH bump (no new skills).

## Test plan

- 7 pytest unit tests covering: full happy path, APIM not found, auto-discovery
  (1 APIM), auto-discovery ambiguous (>1 APIM), permission denied,
  env-var fallback, never-raises contract.
- `python scripts/validate-skills.py` PASS.
- `python scripts/build-plugins.py --check` PASS.
- `python scripts/build-site.py --out docs/` rebuilds; generated diff committed.

## Live Azure testing (AGENTS.md §2.9)

This helper is a wrapper over `azure-mgmt-apimanagement` and
`azure-mgmt-resource` clients. The unit tests cover the never-raises
contract and the auto-discovery branch with mocked SDK responses.

A full E2E test requires a real Citadel hub deployment in CI, which is
not currently provisioned per AGENTS.md §9.7 (E2E infra inventory).
Live validation will be performed by the threadlight v0.5.2 self-verify
run against a dev hub after merge; documented as manual validation here
per §2.9 (E2E test infra exemption).

## Commit tag

`[skill-rewrite]` on the SKILL.md commit (new public section is body
content per AGENTS.md §4).
```

- [ ] **Step 4: STOP and hand back to the human**

Per the planning task framing, **do not open the PR yourself**. Surface
the PR body draft, the commit list, the test summary. Coordinate with
the #244 author if they pop up before review.

---

## Self-Review checklist

- [ ] 7 pytest tests pass locally.
- [ ] `validate-skills.py` PASS.
- [ ] `build-plugins.py --check` PASS.
- [ ] One SKILL.md MINOR bump (`citadel-spoke-onboarding`).
- [ ] One `plugin.json` PATCH bump matched in `marketplace.json`.
- [ ] One docs/ rebuild commit.
- [ ] SKILL.md commit body includes `[skill-rewrite]` tag.
- [ ] Threadlight reference URL preserved in the helper's docstring.
- [ ] No identifier leaks (placeholders only — `<hub-rg>`, `<sub-id>`, `<hub-apim>`).
- [ ] AGENTS.md §12.5 stats unchanged.
- [ ] No edits outside `skills/citadel-spoke-onboarding/`, `scripts/tests/`, `plugin.json`, `marketplace.json`, `docs/`.

---

## Done criteria

Slice B is "done" when:
1. PR merged to `main`.
2. CI green on `skill-validation.yml`, `automation-pr-gate.yml`, and `skill-test.yml` import smoke for `citadel-spoke-onboarding`.
3. Threadlight is unblocked to open its v0.5.2 flip PR for NET-501/502.
4. If #244 dispatches later, that PR's spoke SKILL.md rebase absorbs our subsection as a "kept" diff (low conflict risk by design).
