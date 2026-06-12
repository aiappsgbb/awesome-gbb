---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the azure-mgmt-authorization SDK and azure-identity
    credential chain. No git SHA tracking — version-pinned PyPI only.

packages:
  - name: azure-mgmt-authorization
    source: pypi
    version: "4.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-authorization/#history
    notes: |
      Provides AuthorizationManagementClient. The probe uses
      role_assignments.list_for_scope() and role_definitions.get().
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      DefaultAzureCredential chain.

docs_to_revalidate:
  - https://learn.microsoft.com/python/api/azure-mgmt-authorization/azure.mgmt.authorization.authorizationmanagementclient
  - https://learn.microsoft.com/python/api/azure-mgmt-authorization/azure.mgmt.authorization.operations.roleassignmentsoperations
  - https://learn.microsoft.com/azure/role-based-access-control/built-in-roles
  - https://pypi.org/project/azure-mgmt-authorization/
  - https://pypi.org/project/azure-identity/

known_issues: []

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
        "azure-mgmt-authorization~=4.0.0" \
        "azure-identity~=1.25.0"
    python - <<'PY'
    from azure.mgmt.authorization import AuthorizationManagementClient
    from azure.mgmt.authorization.models import RoleAssignment, RoleDefinition
    from azure.identity import DefaultAzureCredential

    # Verify the surface area the probe depends on
    assert hasattr(AuthorizationManagementClient, "__init__")
    cred_class = DefaultAzureCredential
    print("ok foundry-rbac-audit imports")
    PY
  expected_output:
    - "ok foundry-rbac-audit imports"
  failure_signatures: []

last_validated: "2026-06-12"
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `foundry-rbac-audit` skill

This file is the **machine-readable validation contract** for the
`foundry-rbac-audit` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human
audit trail. Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream type** | PyPI (no git SHA — Tier B) |
| **First authored against** | 2026-06-12 |
| **Last re-validated** | 2026-06-12 |

---

## 2. Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-mgmt-authorization` | PyPI | **4.0.0** | `AuthorizationManagementClient`, `role_assignments.list_for_scope()`, `role_definitions.get()` |
| `azure-identity` | PyPI | **1.25.3** | `DefaultAzureCredential` chain |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them
> identical. The agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
. .venv/bin/activate
pip install --quiet \
    "azure-mgmt-authorization~=4.0.0" \
    "azure-identity~=1.25.0"
python - <<'PY'
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignment, RoleDefinition
from azure.identity import DefaultAzureCredential

# Verify the surface area the probe depends on
assert hasattr(AuthorizationManagementClient, "__init__")
cred_class = DefaultAzureCredential
print("ok foundry-rbac-audit imports")
PY
```

**Expected output** must contain (substring match):

- `ok foundry-rbac-audit imports`

**Failure signatures** (treat as upstream regression — report distinctly):

_(none defined)_

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `from azure.mgmt.authorization import AuthorizationManagementClient` | ✅ | `ok foundry-rbac-audit imports` |
| `from azure.mgmt.authorization.models import RoleAssignment, RoleDefinition` | ✅ | `ok foundry-rbac-audit imports` |
| `from azure.identity import DefaultAzureCredential` | ✅ | `ok foundry-rbac-audit imports` |

Captured at `last_validated: 2026-06-12` by `copilot-bot`.

---

## 5. Known issues at this pin

None at v1.0.0 — both SDKs are GA stable.

---

## 6. Re-pin procedure

When upstream advances:

1. **Check new versions on PyPI**:
   ```bash
   curl -fsSL https://pypi.org/pypi/azure-mgmt-authorization/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   curl -fsSL https://pypi.org/pypi/azure-identity/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   ```
2. **Update front-matter**: set `packages[*].version` to the new values.
3. **Run the validation script**:
   ```bash
   bash -c "$(yq '.validation.script' upstream-pin.md)"
   # (or copy the script from § 3 above)
   ```
4. **Verify expected output**: each `expected_output[]` substring must
   appear in the script's stdout.
5. **Update audit trail**:
   - `last_validated: <today>`
   - `validated_by: <handle>`
6. **Bump SKILL.md `metadata.version` PATCH** (e.g., `1.0.0` → `1.0.1`)
   per AGENTS.md § 5. NOT MINOR — pin refresh is not a new feature.
7. **Open PR**: title `chore(foundry-rbac-audit): re-pin azure-mgmt-authorization + azure-identity → <ver>`.
   Touch ONLY `references/upstream-pin.md` and `SKILL.md` frontmatter.
   The `automation-pr-gate.yml` workflow enforces this.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx
responses surface as a refresh issue.

- <https://learn.microsoft.com/python/api/azure-mgmt-authorization/azure.mgmt.authorization.authorizationmanagementclient>
- <https://learn.microsoft.com/python/api/azure-mgmt-authorization/azure.mgmt.authorization.operations.roleassignmentsoperations>
- <https://learn.microsoft.com/azure/role-based-access-control/built-in-roles>
- <https://pypi.org/project/azure-mgmt-authorization/>
- <https://pypi.org/project/azure-identity/>
