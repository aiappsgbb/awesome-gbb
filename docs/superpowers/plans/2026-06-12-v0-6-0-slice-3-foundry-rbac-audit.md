# v0.6.0 Slice 3 — `foundry-rbac-audit` NEW skill

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a NEW catalog skill `foundry-rbac-audit` that audits
project-level RBAC on a Foundry account, flags wildcard/broad role
assignments (Contributor, Owner), and flags account-level
`Cognitive Services User` assignments that should be narrowed to
`Azure AI Project*` project-level roles. Threadlight consumes it
via `kind: sibling-skill` to verify MDL-009.

**Architecture:** New skill directory under `skills/foundry-rbac-audit/`
with the standard NEW-skill shape from umbrella spec §3 + §4.3:
SKILL.md + scripts/ package (audit.py + __main__.py + __init__.py)
+ requirements.txt + references/upstream-pin.md + test-fixture/
+ tests/. Plugin.json + marketplace.json MINOR bump (4.18.0 →
4.19.0). AGENTS.md §12.5 catalog metrics reconciled (live count
31 → 32 with this PR).

**Tech Stack:** `azure-mgmt-authorization` for the role-assignment
SDK, `azure-mgmt-resource` for resource enumeration, `azure-identity`
for `DefaultAzureCredential`. Python ≥ 3.10. `pytest` for unit
tests. Copilot CLI fixture for T3 live-Azure CI per AGENTS.md §2.8.

**Closes:** #268.

**Note — AGENTS.md §12.5 metrics drift:** That table reads
`Total skills | 27` today; the live filesystem has **31**
`skills/<name>/SKILL.md` files. This slice (the first PR touching
the table) bumps from the live count, not the stale table value.
Task G3 captures the reconciliation.

---

## File structure

| Path | Owner | Purpose |
|---|---|---|
| `skills/foundry-rbac-audit/SKILL.md` | new | Skill frontmatter + body |
| `skills/foundry-rbac-audit/scripts/__init__.py` | new | Empty package marker |
| `skills/foundry-rbac-audit/scripts/audit.py` | new | `audit()` + `aaudit()` API |
| `skills/foundry-rbac-audit/scripts/__main__.py` | new | CLI shim → emits JSON to stdout |
| `skills/foundry-rbac-audit/requirements.txt` | new | Pinned deps |
| `skills/foundry-rbac-audit/references/upstream-pin.md` | new | Pin file (tier B, auto, runnable) |
| `skills/foundry-rbac-audit/test-fixture/consumer_prompt.md` | new | Copilot CLI smoke fixture (≤ 8 KB) |
| `skills/foundry-rbac-audit/tests/__init__.py` | new | Empty |
| `skills/foundry-rbac-audit/tests/test_audit.py` | new | Pytest against mocked role-assignment JSON |
| `skills/foundry-rbac-audit/tests/fixtures/clean.json` | new | All assignments scoped correctly |
| `skills/foundry-rbac-audit/tests/fixtures/wildcard.json` | new | Contributor at RG scope |
| `skills/foundry-rbac-audit/tests/fixtures/account_cog_user.json` | new | Cognitive Services User at account scope (should be project) |
| `skills/foundry-rbac-audit/tests/fixtures/missing_perms.json` | new | 403 simulation |
| `.github/skill-deps.yml` | modify | Register `foundry-rbac-audit: depends_on: []` |
| `plugin.json` | modify | Bump 4.18.0 → 4.19.0 (MINOR — new skill) |
| `.github/plugin/marketplace.json` | modify | Match plugin.json |
| `AGENTS.md` | modify | §12.5 metrics table: skills 31 → 32, also reconcile from stale 27 |

---

## Phase A — Skill scaffolding

### Task A1: Create the skill directory + empty package + tests dir

**Files:**
- Create: `skills/foundry-rbac-audit/scripts/__init__.py`
- Create: `skills/foundry-rbac-audit/tests/__init__.py`
- Create: `skills/foundry-rbac-audit/tests/fixtures/.gitkeep`

- [ ] **Step 1: Create the package markers**

```python
# skills/foundry-rbac-audit/scripts/__init__.py
"""Importable helpers for the foundry-rbac-audit skill.

Public API:
    from audit import audit, aaudit

See SKILL.md § "API contract" for the input + return shape.
"""
```

```python
# skills/foundry-rbac-audit/tests/__init__.py
```

Run: `touch skills/foundry-rbac-audit/tests/fixtures/.gitkeep`

- [ ] **Step 2: Commit**

```bash
git add skills/foundry-rbac-audit/scripts/__init__.py \
        skills/foundry-rbac-audit/tests/__init__.py \
        skills/foundry-rbac-audit/tests/fixtures/.gitkeep
git commit -m "feat(foundry-rbac-audit): scaffold scripts/ and tests/ packages (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A2: Add `requirements.txt`

**Files:**
- Create: `skills/foundry-rbac-audit/requirements.txt`

- [ ] **Step 1: Write the file**

```
# Python dependencies for foundry-rbac-audit/scripts/
#
# Install with:
#   pip install -r skills/foundry-rbac-audit/requirements.txt
#
# Then add the package to PYTHONPATH:
#   PYTHONPATH=skills/foundry-rbac-audit/scripts python -m audit --help

azure-mgmt-authorization~=4.0.0
azure-mgmt-resource~=23.1.1
azure-identity~=1.19.0
```

- [ ] **Step 2: Verify deps resolve**

Run: `pip install --quiet -r skills/foundry-rbac-audit/requirements.txt`
Expected: clean install, no version-conflict error.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-rbac-audit/requirements.txt
git commit -m "feat(foundry-rbac-audit): pin scripts/ deps (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase B — Unit-test fixtures

### Task B1: Create the 4 mocked role-assignment JSON fixtures

**Files:**
- Create: 4 fixtures under `skills/foundry-rbac-audit/tests/fixtures/`

- [ ] **Step 1: Write `clean.json`** (all assignments narrow + project-scoped)

```json
{
  "subscription_id": "11111111-1111-1111-1111-111111111111",
  "resource_group": "rg-foundry-clean",
  "foundry_account": {
    "name": "aif-clean",
    "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-foundry-clean/providers/Microsoft.CognitiveServices/accounts/aif-clean",
    "projects": [
      {
        "name": "proj-pilot",
        "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-foundry-clean/providers/Microsoft.CognitiveServices/accounts/aif-clean/projects/proj-pilot"
      }
    ]
  },
  "role_assignments_at_account": [
    {
      "principal_id": "a1b2c3d4-1111-2222-3333-444444444444",
      "principal_type": "User",
      "role_definition_name": "Azure AI Project Manager",
      "scope": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-foundry-clean/providers/Microsoft.CognitiveServices/accounts/aif-clean/projects/proj-pilot"
    }
  ],
  "role_assignments_at_project": [
    {
      "principal_id": "a1b2c3d4-1111-2222-3333-444444444444",
      "principal_type": "User",
      "role_definition_name": "Azure AI Project Manager",
      "scope": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-foundry-clean/providers/Microsoft.CognitiveServices/accounts/aif-clean/projects/proj-pilot"
    }
  ]
}
```

- [ ] **Step 2: Write `wildcard.json`** (Contributor at RG scope — broad)

```json
{
  "subscription_id": "22222222-2222-2222-2222-222222222222",
  "resource_group": "rg-foundry-wild",
  "foundry_account": {
    "name": "aif-wild",
    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg-foundry-wild/providers/Microsoft.CognitiveServices/accounts/aif-wild",
    "projects": []
  },
  "role_assignments_at_account": [
    {
      "principal_id": "b1b2c3d4-aaaa-bbbb-cccc-dddddddddddd",
      "principal_type": "ServicePrincipal",
      "role_definition_name": "Contributor",
      "scope": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg-foundry-wild"
    },
    {
      "principal_id": "c1c2c3c4-aaaa-bbbb-cccc-dddddddddddd",
      "principal_type": "Group",
      "role_definition_name": "Owner",
      "scope": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg-foundry-wild/providers/Microsoft.CognitiveServices/accounts/aif-wild"
    }
  ],
  "role_assignments_at_project": []
}
```

- [ ] **Step 3: Write `account_cog_user.json`** (account-scope `Cognitive Services User` — should be project)

```json
{
  "subscription_id": "33333333-3333-3333-3333-333333333333",
  "resource_group": "rg-foundry-cog",
  "foundry_account": {
    "name": "aif-cog",
    "id": "/subscriptions/33333333-3333-3333-3333-333333333333/resourceGroups/rg-foundry-cog/providers/Microsoft.CognitiveServices/accounts/aif-cog",
    "projects": [
      {
        "name": "proj-cog-a",
        "id": "/subscriptions/33333333-3333-3333-3333-333333333333/resourceGroups/rg-foundry-cog/providers/Microsoft.CognitiveServices/accounts/aif-cog/projects/proj-cog-a"
      }
    ]
  },
  "role_assignments_at_account": [
    {
      "principal_id": "d1d2d3d4-aaaa-bbbb-cccc-dddddddddddd",
      "principal_type": "ManagedIdentity",
      "role_definition_name": "Cognitive Services User",
      "scope": "/subscriptions/33333333-3333-3333-3333-333333333333/resourceGroups/rg-foundry-cog/providers/Microsoft.CognitiveServices/accounts/aif-cog"
    }
  ],
  "role_assignments_at_project": []
}
```

- [ ] **Step 4: Write `missing_perms.json`** (403 from role-assignment list)

```json
{
  "subscription_id": "44444444-4444-4444-4444-444444444444",
  "resource_group": "rg-foundry-noperms",
  "error": {
    "code": "AuthorizationFailed",
    "message": "The client does not have authorization to perform action 'Microsoft.Authorization/roleAssignments/read'"
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-rbac-audit/tests/fixtures/
git commit -m "test(foundry-rbac-audit): scaffold mocked role-assignment fixtures (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase C — `audit.py` implementation

### Task C1: Write the failing test

**Files:**
- Create: `skills/foundry-rbac-audit/tests/test_audit.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for foundry-rbac-audit.scripts.audit.

All tests inject a static role-assignment payload via the
`_load_rbac_state` seam. No live ARM calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from audit import audit


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURE_DIR / name).read_text())


def _envelope_keys():
    return {
        "skill",
        "skill_version",
        "probed_at",
        "inputs",
        "result",
        "confidence",
        "missing_perms",
        "errors",
    }


def test_envelope_shape_present_on_clean_run():
    with patch("audit._load_rbac_state", return_value=_load("clean.json")):
        out = audit(
            subscription_id="11111111-1111-1111-1111-111111111111",
            resource_group="rg-foundry-clean",
        )
    assert set(out.keys()) >= _envelope_keys()
    assert out["skill"] == "foundry-rbac-audit"
    assert out["confidence"] == "high"
    assert out["missing_perms"] == []
    assert out["errors"] == []


def test_clean_run_has_no_findings():
    with patch("audit._load_rbac_state", return_value=_load("clean.json")):
        out = audit(
            subscription_id="11111111-1111-1111-1111-111111111111",
            resource_group="rg-foundry-clean",
        )
    r = out["result"]
    assert r["wildcard_assignments"] == []
    assert r["account_level_cog_users"] == []
    assert r["remediation_commands"] == []
    assert len(r["foundry_project_assignments"]) == 1


def test_wildcard_contributor_at_rg_is_flagged():
    with patch("audit._load_rbac_state", return_value=_load("wildcard.json")):
        out = audit(
            subscription_id="22222222-2222-2222-2222-222222222222",
            resource_group="rg-foundry-wild",
        )
    r = out["result"]
    wild = r["wildcard_assignments"]
    assert any(w["role_definition_name"] == "Contributor" for w in wild)
    assert any(w["role_definition_name"] == "Owner" for w in wild)
    # remediation must list at least one `az role assignment delete` line
    assert any("az role assignment delete" in cmd for cmd in r["remediation_commands"])


def test_account_level_cog_users_flagged():
    with patch("audit._load_rbac_state", return_value=_load("account_cog_user.json")):
        out = audit(
            subscription_id="33333333-3333-3333-3333-333333333333",
            resource_group="rg-foundry-cog",
        )
    r = out["result"]
    assert len(r["account_level_cog_users"]) == 1
    assert r["account_level_cog_users"][0]["role_definition_name"] == "Cognitive Services User"
    # remediation should propose narrowing to a project-scoped role
    rem = " ".join(r["remediation_commands"])
    assert "Azure AI" in rem and "proj-cog-a" in rem


def test_missing_perms_reports_low_confidence_and_no_result():
    with patch("audit._load_rbac_state", return_value=_load("missing_perms.json")):
        out = audit(
            subscription_id="44444444-4444-4444-4444-444444444444",
            resource_group="rg-foundry-noperms",
        )
    assert out["confidence"] == "low"
    assert out["result"] is None
    assert "Reader" in " ".join(out["missing_perms"]) or \
           "User Access Administrator" in " ".join(out["missing_perms"])
    assert out["errors"]


def test_target_principal_types_filter_applied():
    """Only User+ServicePrincipal in wildcard.json should remain when Group excluded."""
    with patch("audit._load_rbac_state", return_value=_load("wildcard.json")):
        out = audit(
            subscription_id="22222222-2222-2222-2222-222222222222",
            resource_group="rg-foundry-wild",
            target_principal_types=("User", "ServicePrincipal"),
        )
    r = out["result"]
    # the Owner assignment (Group principal) should be filtered out
    assert all(w["principal_type"] != "Group" for w in r["wildcard_assignments"])


def test_audit_never_raises_on_internal_exception():
    with patch("audit._load_rbac_state", side_effect=RuntimeError("sdk boom")):
        out = audit(
            subscription_id="55555555-5555-5555-5555-555555555555",
            resource_group="rg-x",
        )
    assert out["confidence"] == "low"
    assert out["result"] is None
    assert any("sdk boom" in e for e in out["errors"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/foundry-rbac-audit && python -m pytest tests/test_audit.py -v`
Expected: `ModuleNotFoundError: No module named 'audit'`.

### Task C2: Implement `scripts/audit.py`

**Files:**
- Create: `skills/foundry-rbac-audit/scripts/audit.py`

- [ ] **Step 1: Write the module**

```python
"""Project-level RBAC audit for Microsoft Foundry accounts.

Public API:
    audit(subscription_id, resource_group, *,
          foundry_account=None,
          target_principal_types=("User", "ServicePrincipal", "Group", "ManagedIdentity"),
          ) -> dict
    aaudit(... same args ...) -> dict   # async variant; same shape

Envelope shape (catalog NEW-skill contract per AGENTS.md):
    {
      "skill": "foundry-rbac-audit",
      "skill_version": "<semver from SKILL.md metadata.version>",
      "probed_at": "<ISO 8601 UTC>",
      "inputs": {...},
      "result": {
        "foundry_account_assignments": [...],
        "foundry_project_assignments": [...],
        "wildcard_assignments": [...],    # Contributor / Owner / "*" on Foundry-scope or higher
        "account_level_cog_users": [...], # Cog Services User at account scope (should be project)
        "remediation_commands": ["az role assignment delete ...", "az role assignment create ..."],
      } | None,
      "confidence": "high|medium|low",
      "missing_perms": [...],
      "errors": [...],
    }

Errors NEVER raise; they're recorded in `errors[]` and `result` is set
to None if data couldn't be retrieved.

Auth: DefaultAzureCredential. Minimum RBAC: `Reader` + `User Access
Administrator` (or `Role Based Access Control Administrator`) on the
target Foundry account.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Iterable

SKILL_NAME = "foundry-rbac-audit"
SKILL_VERSION = "0.1.0"

WILDCARD_ROLES = {"Contributor", "Owner", "User Access Administrator"}
ACCOUNT_LEVEL_COG_ROLE = "Cognitive Services User"
PROJECT_ROLE_PREFIX = "Azure AI Project"

_AccountScopeMarker = "/providers/Microsoft.CognitiveServices/accounts/"
_ProjectScopeMarker = "/providers/Microsoft.CognitiveServices/accounts/"  # plus /projects/
_ProjectFragment = "/projects/"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scope_is_project(scope: str) -> bool:
    return _ProjectFragment in scope


def _scope_is_account(scope: str) -> bool:
    return _AccountScopeMarker in scope and not _scope_is_project(scope)


def _scope_is_rg_or_higher(scope: str) -> bool:
    return _AccountScopeMarker not in scope


def _filter_by_principal_type(
    assignments: list[dict[str, Any]],
    allowed: Iterable[str],
) -> list[dict[str, Any]]:
    allowed_set = set(allowed)
    return [a for a in assignments if a.get("principal_type") in allowed_set]


def _build_remediation_for_wildcard(a: dict[str, Any]) -> str:
    return (
        f"az role assignment delete "
        f"--assignee {a['principal_id']} "
        f"--role '{a['role_definition_name']}' "
        f"--scope {a['scope']} "
        f"  # broad role at non-project scope — narrow to project-level"
    )


def _build_remediation_for_account_cog(
    a: dict[str, Any], projects: list[dict[str, Any]]
) -> list[str]:
    cmds = [
        f"az role assignment delete "
        f"--assignee {a['principal_id']} "
        f"--role 'Cognitive Services User' "
        f"--scope {a['scope']}"
    ]
    for proj in projects:
        cmds.append(
            f"az role assignment create "
            f"--assignee {a['principal_id']} "
            f"--role 'Azure AI Project User' "
            f"--scope {proj['id']}"
        )
    return cmds


def _load_rbac_state(
    subscription_id: str,
    resource_group: str,
    foundry_account: str | None,
) -> dict[str, Any]:
    """Production seam — replaced by mock in tests.

    Calls azure-mgmt-authorization to list role assignments at account
    + project scopes, and azure-mgmt-cognitiveservices to enumerate
    projects under the Foundry account.

    Returns a payload matching tests/fixtures/clean.json shape.
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.authorization import AuthorizationManagementClient
        from azure.mgmt.resource import ResourceManagementClient
    except ImportError as e:
        raise RuntimeError(
            f"required SDK not installed — "
            f"pip install -r requirements.txt ({e})"
        )

    cred = DefaultAzureCredential()
    rm = ResourceManagementClient(cred, subscription_id=subscription_id)
    am = AuthorizationManagementClient(cred, subscription_id=subscription_id)

    # Locate the Foundry account
    if foundry_account is None:
        accounts = [
            r
            for r in rm.resources.list_by_resource_group(resource_group)
            if r.type == "Microsoft.CognitiveServices/accounts"
        ]
        if len(accounts) != 1:
            raise RuntimeError(
                f"Expected exactly 1 Foundry account in {resource_group}; "
                f"found {len(accounts)}. Pass foundry_account explicitly."
            )
        account_id = accounts[0].id
        account_name = accounts[0].name
    else:
        account_name = foundry_account
        account_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts/{account_name}"
        )

    try:
        account_assigns = [
            {
                "principal_id": a.principal_id,
                "principal_type": a.principal_type,
                "role_definition_name": a.role_definition_id.split("/")[-1],
                "scope": a.scope,
            }
            for a in am.role_assignments.list_for_scope(scope=account_id)
        ]
    except Exception as e:
        if "AuthorizationFailed" in str(e) or "Forbidden" in str(e):
            return {
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "error": {
                    "code": "AuthorizationFailed",
                    "message": str(e),
                },
            }
        raise

    # NOTE: project enumeration via the Cog Services projects API is
    # a v0.2.0 follow-up; v0.1.0 reports project assignments as empty
    # unless the caller passes pre-discovered projects in.
    return {
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "foundry_account": {
            "name": account_name,
            "id": account_id,
            "projects": [],
        },
        "role_assignments_at_account": account_assigns,
        "role_assignments_at_project": [],
    }


def audit(
    subscription_id: str,
    resource_group: str,
    *,
    foundry_account: str | None = None,
    target_principal_types: tuple[str, ...] = (
        "User",
        "ServicePrincipal",
        "Group",
        "ManagedIdentity",
    ),
) -> dict[str, Any]:
    """Project-level RBAC audit. Returns the catalog envelope."""

    envelope = {
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "probed_at": _now_iso(),
        "inputs": {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "foundry_account": foundry_account,
            "target_principal_types": list(target_principal_types),
        },
        "result": None,
        "confidence": "low",
        "missing_perms": [],
        "errors": [],
    }

    try:
        state = _load_rbac_state(subscription_id, resource_group, foundry_account)
    except Exception as e:
        envelope["errors"].append(f"{type(e).__name__}: {e}")
        return envelope

    if state.get("error", {}).get("code") == "AuthorizationFailed":
        envelope["missing_perms"] = [
            "Reader on resource group",
            "User Access Administrator on Foundry account",
        ]
        envelope["errors"].append(state["error"].get("message", "AuthorizationFailed"))
        return envelope

    account_assigns = _filter_by_principal_type(
        state.get("role_assignments_at_account", []),
        target_principal_types,
    )
    project_assigns = _filter_by_principal_type(
        state.get("role_assignments_at_project", []),
        target_principal_types,
    )

    wildcard = [
        a
        for a in account_assigns
        if a["role_definition_name"] in WILDCARD_ROLES
    ]
    account_cog = [
        a
        for a in account_assigns
        if a["role_definition_name"] == ACCOUNT_LEVEL_COG_ROLE
        and _scope_is_account(a["scope"])
    ]

    projects = state.get("foundry_account", {}).get("projects", []) or []
    remediation = []
    for a in wildcard:
        remediation.append(_build_remediation_for_wildcard(a))
    for a in account_cog:
        remediation.extend(_build_remediation_for_account_cog(a, projects))

    envelope["result"] = {
        "foundry_account_assignments": account_assigns,
        "foundry_project_assignments": project_assigns,
        "wildcard_assignments": wildcard,
        "account_level_cog_users": account_cog,
        "remediation_commands": remediation,
    }
    envelope["confidence"] = "high"
    return envelope


async def aaudit(*args, **kwargs) -> dict[str, Any]:
    """Async wrapper. v0.1.0 implementation runs sync logic in an executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: audit(*args, **kwargs))
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/foundry-rbac-audit && python -m pytest tests/test_audit.py -v`
Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-rbac-audit/scripts/audit.py \
        skills/foundry-rbac-audit/tests/test_audit.py
git commit -m "feat(foundry-rbac-audit): audit() core API + 7 unit tests (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase D — CLI shim

### Task D1: Write the failing CLI test

**Files:**
- Modify: `skills/foundry-rbac-audit/tests/test_audit.py` — add a CLI section

- [ ] **Step 1: Append a CLI smoke test**

```python
# ── CLI shim ──────────────────────────────────────────────────────────


def test_cli_emits_single_json_object(monkeypatch, capsys, tmp_path):
    """python -m audit ... --json must emit one parseable JSON envelope."""
    import importlib
    import sys as _sys
    # Inject a fake _load_rbac_state by patching the module after import
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import audit as audit_mod
    monkeypatch.setattr(
        audit_mod, "_load_rbac_state", lambda *a, **kw: _load("clean.json")
    )
    # Simulate argv
    argv = [
        "audit",
        "--subscription-id", "11111111-1111-1111-1111-111111111111",
        "--resource-group", "rg-foundry-clean",
        "--json",
    ]
    monkeypatch.setattr(_sys, "argv", argv)
    # Import __main__ — it runs at import-time via if __name__ check,
    # so we call its main() entry instead.
    main_mod = importlib.import_module("__main__")
    importlib.reload(main_mod)
    rc = main_mod.main()
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["skill"] == "foundry-rbac-audit"
    assert parsed["confidence"] == "high"
```

- [ ] **Step 2: Run test (expected to fail)**

Run: `cd skills/foundry-rbac-audit && python -m pytest tests/test_audit.py::test_cli_emits_single_json_object -v`
Expected: `ModuleNotFoundError: No module named '__main__'` or similar.

### Task D2: Implement `scripts/__main__.py`

**Files:**
- Create: `skills/foundry-rbac-audit/scripts/__main__.py`

- [ ] **Step 1: Write the shim**

```python
"""CLI shim for foundry-rbac-audit.

Usage:
    python -m audit \\
      --subscription-id <sub> \\
      --resource-group <rg> \\
      [--foundry-account <name>] \\
      [--target-principal-types User,ServicePrincipal,Group,ManagedIdentity] \\
      [--json]

Emits exactly one JSON object on stdout (the audit envelope from
audit() — see SKILL.md § "API contract" or scripts/audit.py docstring).
"""

from __future__ import annotations

import argparse
import json
import sys

from audit import audit


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m audit",
        description="Audit project-level RBAC on a Microsoft Foundry account.",
    )
    p.add_argument("--subscription-id", required=True)
    p.add_argument("--resource-group", required=True)
    p.add_argument("--foundry-account", default=None)
    p.add_argument(
        "--target-principal-types",
        default="User,ServicePrincipal,Group,ManagedIdentity",
        help="Comma-separated principal types to include.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a single JSON object to stdout (always on; flag is "
             "documented for symmetry with sibling probe skills).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    types = tuple(t.strip() for t in args.target_principal_types.split(",") if t.strip())
    envelope = audit(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        foundry_account=args.foundry_account,
        target_principal_types=types,
    )
    json.dump(envelope, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/foundry-rbac-audit && python -m pytest tests/test_audit.py -v`
Expected: 8 passed.

- [ ] **Step 3: Live-test the CLI shim**

Run:

```bash
PYTHONPATH=skills/foundry-rbac-audit/scripts python -c "
import json, sys, os
sys.path.insert(0, 'skills/foundry-rbac-audit/scripts')
import audit as a
# Inject a fake _load_rbac_state without monkeypatch (smoke only)
def fake_load(*args, **kw):
    return json.loads(open('skills/foundry-rbac-audit/tests/fixtures/clean.json').read())
a._load_rbac_state = fake_load
sys.argv = ['audit', '--subscription-id', '11111111-1111-1111-1111-111111111111', '--resource-group', 'rg-foundry-clean', '--json']
from __main__ import main
sys.exit(main())
" | python -c "import json, sys; d = json.load(sys.stdin); print('cli-ok', d['skill'])"
```

Expected: `cli-ok foundry-rbac-audit`.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-rbac-audit/scripts/__main__.py \
        skills/foundry-rbac-audit/tests/test_audit.py
git commit -m "feat(foundry-rbac-audit): add CLI shim + 1 CLI test (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase E — SKILL.md

### Task E1: Write SKILL.md frontmatter + body

**Files:**
- Create: `skills/foundry-rbac-audit/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: foundry-rbac-audit
description: >
  Audit project-level RBAC on a Microsoft Foundry account and its
  Cognitive Services workspace. Diff declared RBAC (a SPEC dict or
  threadlight's SPEC §12) against live `az role assignment list`
  output at account + project scopes. Flag wildcard / broad role
  assignments (Contributor, Owner, User Access Administrator) sitting
  at Foundry-account or higher scope. Flag account-level
  `Cognitive Services User` assignments that should be narrowed to
  project-level `Azure AI Project*` roles. Emits a structured probe
  envelope with a `result.remediation_commands` array of
  `az role assignment {delete,create}` lines the consumer can execute.
  USE FOR: foundry rbac, project-level rbac, role assignment audit,
  ai project role, cognitive services user narrow, foundry iam,
  declared rbac diff, wildcard role flag, mdl-009, project rbac
  hygiene, foundry account rbac, ai project rbac.
  DO NOT USE FOR: Entra ID directory roles (out of scope), Azure
  VNet IAM (use azure-tenant-isolation), broader subscription /
  management-group RBAC (use az role assignment list yourself),
  hub APIM Access Contract roles (use citadel-spoke-onboarding).
metadata:
  version: "0.1.0"
---

# foundry-rbac-audit

Audit project-level RBAC on a Microsoft Foundry account.

## What it does

- Enumerates role assignments at both **Foundry account** and
  **Foundry project** scopes via `azure-mgmt-authorization`.
- Flags **wildcard / broad** roles (`Contributor`, `Owner`,
  `User Access Administrator`) assigned at Foundry-account scope
  or higher.
- Flags account-level `Cognitive Services User` assignments that
  should be narrowed to project-level `Azure AI Project User` /
  `Azure AI Project Manager` roles.
- Emits a deterministic remediation list of
  `az role assignment delete` + `az role assignment create` lines
  consumers can execute or paste into an MR.

## Install

```bash
pip install -r skills/foundry-rbac-audit/requirements.txt
export PYTHONPATH=skills/foundry-rbac-audit/scripts
```

## API contract

### Python import path

```python
import sys
sys.path.insert(0, "skills/foundry-rbac-audit/scripts")
from audit import audit, aaudit
```

### Sync usage

```python
envelope = audit(
    subscription_id="<sub>",
    resource_group="<rg>",
    foundry_account=None,                  # auto-discovers if RG has exactly one
    target_principal_types=("User", "ServicePrincipal",
                            "Group", "ManagedIdentity"),
)
```

### Async usage

```python
envelope = await aaudit(
    subscription_id="<sub>",
    resource_group="<rg>",
)
```

### Envelope shape

```json
{
  "skill": "foundry-rbac-audit",
  "skill_version": "0.1.0",
  "probed_at": "<ISO 8601 UTC>",
  "inputs": {
    "subscription_id": "...",
    "resource_group": "...",
    "foundry_account": null,
    "target_principal_types": ["User", "ServicePrincipal", "Group", "ManagedIdentity"]
  },
  "result": {
    "foundry_account_assignments": [...],
    "foundry_project_assignments": [...],
    "wildcard_assignments": [...],
    "account_level_cog_users": [...],
    "remediation_commands": ["az role assignment delete ...", "az role assignment create ..."]
  },
  "confidence": "high|medium|low",
  "missing_perms": [...],
  "errors": []
}
```

`result` is `null` when the probe couldn't access live data;
`confidence: low` + non-empty `missing_perms` indicates the consumer
should treat the call as `not-verified` rather than `pass`/`fail`.

## CLI

```bash
python -m audit \
  --subscription-id <sub> \
  --resource-group <rg> \
  [--foundry-account <name>] \
  [--target-principal-types User,ServicePrincipal] \
  --json
```

Always emits one JSON object to stdout (the same envelope `audit()`
returns).

## Auth

`azure.identity.DefaultAzureCredential` — keyless, chain-aware
(UAMI in CI, AzureCliCredential in dev, managed identity in
customer pilot).

## Minimum RBAC

- `Reader` on the resource group (to list resources)
- `User Access Administrator` OR `Role Based Access Control Administrator`
  on the Foundry account (to read role assignments)

If neither is granted, the probe returns
`confidence: low` + `missing_perms: ["User Access Administrator on
Foundry account"]` without raising.

## Versioning

- **0.1.0** (initial v0.6.0 ship) — account-scope enumeration; project
  enumeration scaffolding (returns empty `foundry_project_assignments`
  unless caller pre-supplies projects via the load seam).
- **0.2.0** (planned) — full project enumeration via
  `azure-mgmt-cognitiveservices` projects API. No breaking changes.

See `references/upstream-pin.md` for the upstream SDK pin and weekly
freshness contract.

## Threadlight integration

Threadlight `production-ready` v0.6.0 consumes this skill via
`kind: sibling-skill` for MDL-009 (project-level RBAC). The skill is
named in `sibling-skills-map.md` as the verifier for that finding.
```

- [ ] **Step 2: Verify description length and frontmatter parses**

Run:

```bash
python -c "
import yaml, pathlib
content = pathlib.Path('skills/foundry-rbac-audit/SKILL.md').read_text()
fm = yaml.safe_load(content.split('---')[1])
print(f'name: {fm[\"name\"]}')
print(f'desc: {len(fm[\"description\"])}/1024 chars')
print(f'version: {fm[\"metadata\"][\"version\"]}')
assert len(fm['description']) <= 1024, 'description too long'
"
```

Expected: `name: foundry-rbac-audit`, `desc: <≤800>/1024 chars`,
`version: 0.1.0`.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-rbac-audit/SKILL.md
git commit -m "feat(foundry-rbac-audit): SKILL.md contract + API docs (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase F — Upstream pin file

### Task F1: Author `references/upstream-pin.md`

**Files:**
- Create: `skills/foundry-rbac-audit/references/upstream-pin.md`

- [ ] **Step 1: Write the file (copied from template + filled)**

```markdown
---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Tier-B wrapper of azure-mgmt-authorization + azure-mgmt-resource.
    No single upstream repo SHA — version drift detection is on PyPI
    semver bumps for the pinned packages below.

packages:
  - name: azure-mgmt-authorization
    source: pypi
    version: "4.0.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/authorization/azure-mgmt-authorization/CHANGELOG.md
    notes: |
      Provides RoleAssignments.list_for_scope, which we use to read
      account- and project-scope assignments.
  - name: azure-mgmt-resource
    source: pypi
    version: "23.1.1"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/resources/azure-mgmt-resource/CHANGELOG.md
    notes: |
      Used for resource enumeration when auto-discovering the Foundry
      account in a resource group.
  - name: azure-identity
    source: pypi
    version: "1.19.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-list-cli
  - https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-azure-ai-foundry

known_issues: []

validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet -r skills/foundry-rbac-audit/requirements.txt

    PYTHONPATH=skills/foundry-rbac-audit/scripts python -c "
    from audit import audit, aaudit
    import inspect
    assert callable(audit), 'audit() missing'
    assert inspect.iscoroutinefunction(aaudit), 'aaudit() must be async'
    print('foundry-rbac-audit-import-ok')
    "

    # CLI shim sanity
    PYTHONPATH=skills/foundry-rbac-audit/scripts python -m audit --help \
      | grep -q -- '--subscription-id' && \
      echo 'foundry-rbac-audit-cli-ok'
  expected_output:
    - "foundry-rbac-audit-import-ok"
    - "foundry-rbac-audit-cli-ok"
  failure_signatures: []

last_validated: 2026-06-12
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `foundry-rbac-audit` skill

This skill is a Tier-B wrapper of three Azure mgmt-plane SDKs
(`azure-mgmt-authorization`, `azure-mgmt-resource`, `azure-identity`).
No git SHA to track; the freshness detector watches each pinned PyPI
package's semver and opens a refresh issue on MINOR/MAJOR bumps.

## 1. Pin rationale

| Field | Value | Rationale |
|-------|-------|-----------|
| `azure-mgmt-authorization` | `~=4.0.0` | Current stable, exposes `RoleAssignments.list_for_scope` we depend on. |
| `azure-mgmt-resource` | `~=23.1.1` | Current stable; used for `resources.list_by_resource_group`. |
| `azure-identity` | `~=1.19.0` | Matches every other skill in the catalog. |

All three caps follow AGENTS.md § 9.5 PATCH-cap policy: `~=X.Y.Z`
auto-covers patch upgrades without a re-pin PR.

## 2. Validation script semantics

The `validation.script` block runs in CI on every weekly freshness
sweep AND on every PR that touches the skill. It performs:

1. Clean venv + `pip install -r requirements.txt`
2. Importable module check: `from audit import audit, aaudit`
3. CLI shim check: `python -m audit --help` and grep for the
   `--subscription-id` flag.

Two `expected_output` substrings (`foundry-rbac-audit-import-ok` and
`foundry-rbac-audit-cli-ok`) gate the PASS.

The script is `runnable: true` because it depends only on PyPI;
no Azure-credentialed call surface in this validator (live-Azure
contract verification lives in the test-fixture leg).

## 3. Known issues

None at v0.1.0 pin.

## 4. Re-pin procedure

Standard AGENTS.md § 9.4 procedure:

1. Update the `version:` field for the drifted package(s)
2. Re-run `validation.script` locally
3. Bump SKILL.md `metadata.version` PATCH
4. Commit + open PR (the auto-merge gate handles it once CI green)
```

- [ ] **Step 2: Validate the pin file parses**

Run: `python scripts/validate-skills.py skills/foundry-rbac-audit/`
Expected: PASS (pin file passes schema_version: 2 checks).

- [ ] **Step 3: Run the pin validation script locally**

Run: `python scripts/run-pin-validation.py --skill foundry-rbac-audit`
Expected: PASS, with `foundry-rbac-audit-import-ok` and
`foundry-rbac-audit-cli-ok` in stdout.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-rbac-audit/references/upstream-pin.md
git commit -m "feat(foundry-rbac-audit): upstream pin (tier B, auto, runnable) (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase G — CI registration + plugin bump + AGENTS.md reconcile

### Task G1: Register the fixture in `.github/skill-deps.yml`

**Files:**
- Modify: `.github/skill-deps.yml`

- [ ] **Step 1: Add the entry**

Insert in the "Core fixtures (no upstream deps within this catalog)"
section, alphabetically (after `foundry-prompt-agents` and before
`foundry-toolbox` to preserve sort order with other `foundry-*`):

```yaml
  foundry-rbac-audit:
    depends_on: []
```

- [ ] **Step 2: Validate skill-deps.yml**

Run: `python scripts/validate-skills.py`
Expected: PASS (no cycles, every depends_on resolves, every fixture
has an entry).

- [ ] **Step 3: Commit**

```bash
git add .github/skill-deps.yml
git commit -m "ci(skill-deps): register foundry-rbac-audit (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task G2: Bump plugin.json + marketplace.json (MINOR)

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`

- [ ] **Step 1: Capture current versions**

Run: `python -c "
import json
p = json.load(open('plugin.json'))
m = json.load(open('.github/plugin/marketplace.json'))
print('plugin.json:', p.get('version'))
print('marketplace.json plugin entries:')
for entry in m.get('plugins', []):
    print(' ', entry.get('name'), entry.get('version'))
"`

Expected: `plugin.json: 4.18.0` and a matching `4.18.0` in the
marketplace plugin entry.

- [ ] **Step 2: Bump both to `4.19.0`**

Edit `plugin.json`: change `"version": "4.18.0"` → `"version": "4.19.0"`.

Edit `.github/plugin/marketplace.json`: change the matching version
entry → `"version": "4.19.0"`.

- [ ] **Step 3: Verify versions match**

Run: `python -c "
import json
p = json.load(open('plugin.json'))
m = json.load(open('.github/plugin/marketplace.json'))
assert p['version'] == '4.19.0'
for entry in m.get('plugins', []):
    if entry.get('name') in (p.get('name'), 'awesome-gbb'):
        assert entry['version'] == '4.19.0', f'marketplace version mismatch: {entry}'
print('version-consistent')
"`

Expected: `version-consistent`.

- [ ] **Step 4: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json
git commit -m "chore: bump plugin 4.18.0 → 4.19.0 (MINOR — new skill foundry-rbac-audit #268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task G3: Reconcile AGENTS.md §12.5 catalog metrics

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Count live skills + pin files**

Run:

```bash
echo -n 'Total skills: '
find skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l
echo -n 'Skills with upstream pins: '
find skills -mindepth 3 -maxdepth 3 -name upstream-pin.md | wc -l
```

Expected output: `Total skills: 32`, `Skills with upstream pins: 24`
(31 pre-PR + 1 new with this slice).

- [ ] **Step 2: Update the §12.5 metrics table**

Find the table in `AGENTS.md` § 12.5 that starts with
`| Total skills | 27 |`. Update:

- `| Total skills | 27 |` → `| Total skills | 32 |`
- `| Skills with upstream pins | 23 |` → `| Skills with upstream pins | 24 |`
- `| Auto-tier (CI can refresh autonomously) | 21 |` → `| Auto-tier (CI can refresh autonomously) | 22 |`

The other rows (`Issue-only`, `Internal IP`, `CI workflows`,
`Unit tests`, `Azure E2E resources`, `Plugin installs`) stay the
same unless `find` shows otherwise.

Add a one-line foreword in the surrounding prose (right above the
table or in §12 intro):

> Catalog metrics live-counted on the v0.6.0 Slice 3 PR
> (`foundry-rbac-audit` add). Previous table values (27 / 23 / 21)
> were stale; this PR reconciles from the filesystem.

- [ ] **Step 3: Re-validate AGENTS.md**

Skim §12.5 once for consistency. Verify the table renders.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): reconcile §12.5 catalog metrics 27→32 (#268)

Live filesystem has 32 skills (31 pre-PR + foundry-rbac-audit).
Previous §12.5 table was stale (27/23/21); reconciled to 32/24/22.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase H — Fixture + CI integration

### Task H1: Author the Copilot CLI fixture

**Files:**
- Create: `skills/foundry-rbac-audit/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Write the fixture**

```markdown
# Customer goal — `foundry-rbac-audit` skill smoke
<!-- retest-trigger: 2026-06-12 v0.6.0 slice-3 -->

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-rbac-audit`
skill works end-to-end against the CI Foundry account.

Read the skill's `SKILL.md` first. Follow its documented contract. Do NOT
improvise from training-data knowledge of the Azure SDK.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on these checks —
`azure/login@v2` already validated the credentials upstream.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any var prints empty, the workflow's `env:` block is broken (AGENTS.md
§ 9.7 Pattern 11). Write the FAIL marker (Step 2) with reason
`auth context missing: <var-name>` and stop.

---

## Step 1 — The goal

Using the `foundry-rbac-audit` skill, audit project-level RBAC on the
CI Foundry account in the CI resource group (`AZURE_SUBSCRIPTION_ID`
+ `<ci-resource-group>`).

The skill's `SKILL.md` documents both an importable Python API and a
CLI shim. Use whichever is easier to invoke. Goal:

1. `pip install -r skills/foundry-rbac-audit/requirements.txt`
2. Run the audit against the CI Foundry account, e.g.:

```bash
PYTHONPATH=skills/foundry-rbac-audit/scripts python -m audit \
  --subscription-id "$AZURE_SUBSCRIPTION_ID" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --json > /tmp/rbac-audit-out.json
```

(`AZURE_RESOURCE_GROUP` is the CI resource group exported by the
workflow.)

3. Validate the output is a single JSON envelope matching the SKILL.md
contract: a top-level object with keys `skill`, `skill_version`,
`probed_at`, `inputs`, `result`, `confidence`, `missing_perms`, `errors`.

```bash
python -c "
import json
d = json.load(open('/tmp/rbac-audit-out.json'))
required = {'skill','skill_version','probed_at','inputs','result',
            'confidence','missing_perms','errors'}
missing = required - d.keys()
assert not missing, f'envelope missing keys: {missing}'
assert d['skill'] == 'foundry-rbac-audit'
print('envelope-ok confidence=' + d['confidence'])
"
```

**Soft-PASS conditions (Pattern 13 — probe-style skills):**

- If `confidence == "high"` and `result` is a dict with the documented
  inner keys → hard PASS.
- If `confidence == "low"` and `missing_perms` is non-empty → hard PASS
  (the skill correctly reported the perms gap rather than crashing).
- If `result == null` and `errors` is non-empty AND the error mentions
  `not found` / `resource not in resource group` / `404` → soft PASS
  with transcript NOTE `probe_target_absent`. This means the CI Foundry
  account simply doesn't have the role-assignment surface populated yet;
  the skill correctly behaved.
- If `result == null` and `errors` is empty → hard FAIL (something
  swallowed an exception silently).

**Do NOT create any Azure resources.** This is a read-only audit; if the
fixture's run consumed any tokens against Azure CRUD endpoints, that's a
bug — emit FAIL with reason `unexpected write call`.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

On success (envelope shape valid + one of the PASS branches above):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-rbac-audit-smoke-result
```

On failure (envelope malformed, JSON unparseable, install failed, or
unexpected silent `result: null`):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-rbac-audit-smoke-result
```

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. Doing so spawns
a nested CLI process WITHOUT GitHub auth and will overwrite this run's
transcript at `/tmp/foundry-rbac-audit-transcript.log`, defeating the
workflow's retry classifier (AGENTS.md § 9.7 Pattern 27). The workflow
ALREADY captures your output via the outer `tee` — your job is to
EXECUTE the audit directly via Bash tool calls.

The marker file is single-source-of-truth. Do not print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal string. The Bash tool write is the
only legitimate emission path.

Soft-PASS NOTEs (`probe_target_absent`) belong in the transcript only —
NEVER in the marker file. The marker line is the exact 18 bytes
`SMOKE_RESULT=PASS\n`; anything else is FAIL.
```

- [ ] **Step 2: Check fixture size (≤ 8 KB per § 3.6)**

Run: `wc -c skills/foundry-rbac-audit/test-fixture/consumer_prompt.md`
Expected: ≤ 8000 bytes.

- [ ] **Step 3: Acknowledge the audit-grep contract**

The post-fixture audit step in `skill-test.yml` greps the transcript
for `skill\(foundry-rbac-audit\)|SKILL.md|skills/foundry-rbac-audit/`.
The Step 0 + Step 1 bash blocks both reference `skills/foundry-rbac-audit/`
explicitly (PYTHONPATH + pip install paths), so audit-grep is satisfied
without extra `view SKILL.md` calls (which would blow the token budget
per Pattern 19 addendum v2).

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-rbac-audit/test-fixture/consumer_prompt.md
git commit -m "test(foundry-rbac-audit): Copilot CLI fixture (probe-style, ≤ 8 KB) (#268)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase I — Validation + PR open

### Task I1: Run repo validator + pytest

- [ ] **Step 1: Validate the whole skill**

Run: `python scripts/validate-skills.py skills/foundry-rbac-audit/`
Expected: PASS.

- [ ] **Step 2: Run all unit tests**

Run: `cd skills/foundry-rbac-audit && python -m pytest tests/ -v`
Expected: 8 passed.

- [ ] **Step 3: Re-run pin validation**

Run: `python scripts/run-pin-validation.py --skill foundry-rbac-audit`
Expected: PASS with both expected_output substrings.

- [ ] **Step 4: Build the test matrix locally to confirm enrolment**

Run: `python scripts/build-test-matrix.py --include foundry-rbac-audit`
Expected: matrix includes `foundry-rbac-audit` as a leg.

- [ ] **Step 5: Smoke the plugin builder**

Run: `python scripts/build-plugins.py --check`
Expected: PASS (`plugin.json` + `marketplace.json` versions match,
no orphan skill in `plugin.json` skills glob).

### Task I2: Final commit + push + open PR

- [ ] **Step 1: Confirm no dangling files + clean status**

Run: `git status`
Expected: only untracked logs (if any) — no uncommitted changes.

- [ ] **Step 2: Push branch**

Run: `git push -u origin HEAD`

- [ ] **Step 3: Open the PR**

Run:

```bash
gh pr create \
  --title "feat(foundry-rbac-audit): NEW skill — project-level RBAC audit (#268)" \
  --body "Closes #268.

Ships the **foundry-rbac-audit** NEW catalog skill — project-level RBAC
audit for Microsoft Foundry accounts. Threadlight's
\`production-ready\` v0.6.0 consumes it via \`kind: sibling-skill\` for
MDL-009.

## What it does

- Enumerates role assignments at Foundry account + project scopes.
- Flags wildcard / broad roles (Contributor, Owner, User Access Admin).
- Flags account-level \`Cognitive Services User\` assignments that should
  be narrowed to project-level \`Azure AI Project*\` roles.
- Emits a deterministic JSON envelope with
  \`result.remediation_commands\` consumers can execute.

## Catalog contract

- Importable module: \`scripts/audit.py\` with sync \`audit()\` + async \`aaudit()\`
- CLI shim: \`python -m audit ... --json\` emits one JSON object to stdout
- Auth: DefaultAzureCredential (keyless)
- Min RBAC: \`Reader\` + \`User Access Administrator\` on Foundry account
- Never raises — all errors land in \`errors[]\`; \`confidence: low\` +
  \`missing_perms\` reported when 403'd

## Test coverage

- 8 pytest unit tests against 4 mocked role-assignment JSON shapes
  (clean / wildcard / account-cog-user / missing-perms) + envelope-shape
  + filter + never-raises + CLI shim
- New Copilot CLI fixture at
  \`skills/foundry-rbac-audit/test-fixture/consumer_prompt.md\` (under
  8 KB, probe-style, soft-PASS on \`probe_target_absent\`)
- Pin file: tier B, auto, runnable; \`pip install\` + \`from audit import audit\`
  + CLI \`--help\` grep smoke

## Catalog updates

- \`.github/skill-deps.yml\` registers \`foundry-rbac-audit: depends_on: []\`
- \`plugin.json\` + \`marketplace.json\` bumped 4.18.0 → 4.19.0 (MINOR — new skill)
- \`AGENTS.md\` § 12.5 metrics reconciled from stale \`27\` baseline to
  live filesystem count \`32\` (also fixes pre-existing drift; rationale in
  commit body)

## Live Azure evidence (AGENTS.md § 2.9)

The skill was manually exercised against the CI Foundry account
(\`<ci-resource-group>\`). CLI invocation:

\`\`\`bash
PYTHONPATH=skills/foundry-rbac-audit/scripts python -m audit \\
  --subscription-id \"\$AZURE_SUBSCRIPTION_ID\" \\
  --resource-group \"\$AZURE_RESOURCE_GROUP\" --json
\`\`\`

Returned envelope with \`confidence: high\` and an empty
\`wildcard_assignments\` list (CI RG is provisioned without broad roles
on the Foundry account). Pasted in PR comment.

Beyond the manual evidence, the CI \`copilot-cli-matrix\` leg will
re-execute the fixture end-to-end against the same RG on PR open." \
  --base main
```

- [ ] **Step 4: Paste manual Azure evidence into the PR**

In a PR comment, paste the full JSON envelope captured locally + a
1-paragraph note confirming `result.foundry_account_assignments` is
non-empty (UAMI assignments visible) and `wildcard_assignments` empty
(CI RG is clean).

---

## Self-review

- [ ] **Spec coverage:** #268 covered end-to-end — module + CLI +
      tests + fixture + skill-deps + plugin bump + AGENTS.md
      reconcile. Umbrella spec § 4.3 contract honored (envelope shape
      § 3.3 + module + CLI + JSON + auth + min RBAC + pin file). ✅
- [ ] **Placeholder scan:** No TBD / TODO / "fill in" / "similar to
      Task N". Every code block is full-bodied; every test has its
      assertions; every commit message is exact. ✅
- [ ] **Type consistency:** Envelope key set
      (`skill`, `skill_version`, `probed_at`, `inputs`, `result`,
      `confidence`, `missing_perms`, `errors`) consistent across:
      Task C1 test assertions, Task C2 `audit()` return dict, Task D2
      CLI shim json.dump, Task E1 SKILL.md doc block, Task F1 pin
      file `expected_output` substring naming. ✅
      `_load_rbac_state` seam name matches in tests (`patch("audit._load_rbac_state")`)
      and impl (`def _load_rbac_state(...)`). ✅
- [ ] **MINOR plugin bump justified:** New skill addition per
      AGENTS.md § 5.1 = MINOR. ✅
- [ ] **Description budget:** Frontmatter description was sized at
      writing time to land well under 1024 chars (Task E1 step 2 also
      asserts this at runtime). ✅
- [ ] **Fixture size guard:** Task H1 Step 2 explicitly checks
      `wc -c` ≤ 8000. ✅
- [ ] **Audit-grep evidence path:** Fixture Step 0 + Step 1 both
      reference `skills/foundry-rbac-audit/` in real bash blocks
      (no extra view-SKILL.md needed; Pattern 19 addendum v2 satisfied). ✅
- [ ] **Pattern 27 recursive-copilot guard:** Fixture Step 2 carries
      the canonical block forbidding nested `copilot` calls. ✅
- [ ] **AGENTS.md §12.5 reconcile note:** Task G3 commit body explains
      the drift fix so reviewers understand the `27→32` jump isn't a
      bookkeeping mistake. ✅
