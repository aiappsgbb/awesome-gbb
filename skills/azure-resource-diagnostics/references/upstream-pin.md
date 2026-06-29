---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Azure Monitor + Resource management SDKs and the
    azure-identity credential chain. No git SHA tracking — version-pinned
    PyPI only.

packages:
  - name: azure-mgmt-monitor
    source: pypi
    version: "7.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-monitor/#history
    purpose: "Diagnostic settings enumeration"
  - name: azure-mgmt-resource
    source: pypi
    version: "26.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-resource/#history
    purpose: "Resource listing by resource group"
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    purpose: "DefaultAzureCredential chain"

docs_to_revalidate:
  - https://learn.microsoft.com/python/api/azure-mgmt-monitor/azure.mgmt.monitor.monitormanagementclient
  - https://learn.microsoft.com/python/api/azure-mgmt-resource/azure.mgmt.resource.resourcemanagementclient
  - https://learn.microsoft.com/azure/azure-monitor/essentials/diagnostic-settings
  - https://pypi.org/project/azure-mgmt-monitor/
  - https://pypi.org/project/azure-mgmt-resource/
  - https://pypi.org/project/azure-identity/

known_issues: []

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    pip install -q "azure-mgmt-monitor~=7.0.0" \
                    "azure-mgmt-resource~=26.0.0" \
                    "azure-identity~=1.25.3"
    python -c "from azure.mgmt.monitor import MonitorManagementClient; print('MON OK')"
    python -c "from azure.mgmt.resource.resources import ResourceManagementClient; print('RES OK')"
    python -c "from azure.identity import DefaultAzureCredential; print('CRED OK')"
  expected_output:
    - "MON OK"
    - "RES OK"
    - "CRED OK"
  failure_signatures: []

last_validated: "2026-06-29"
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `azure-resource-diagnostics` skill

This file is the **machine-readable validation contract** for the
`azure-resource-diagnostics` skill. The YAML front-matter above is parsed
by `scripts/check-freshness.py` weekly; the prose below is the human audit
trail. Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream type** | PyPI (no git SHA — Tier B) |
| **First authored against** | 2026-06-19 |
| **Last re-validated** | 2026-06-19 |

---

## 2. Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-mgmt-monitor` | PyPI | **6.0.2** | Diagnostic settings enumeration |
| `azure-mgmt-resource` | PyPI | **23.1.1** | Resource listing by resource group |
| `azure-identity` | PyPI | **1.19.0** | `DefaultAzureCredential` chain |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them
> identical. The agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail
pip install -q "azure-mgmt-monitor~=6.0.0" \
                "azure-mgmt-resource~=23.1.0" \
                "azure-identity~=1.19.0"
python -c "from azure.mgmt.monitor import MonitorManagementClient; print('MON OK')"
python -c "from azure.mgmt.resource import ResourceManagementClient; print('RES OK')"
python -c "from azure.identity import DefaultAzureCredential; print('CRED OK')"
```

**Expected output** must contain (substring match):

- `MON OK`
- `RES OK`
- `CRED OK`

**Failure signatures** (treat as upstream regression — report distinctly):

_(none defined)_

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `from azure.mgmt.monitor import MonitorManagementClient` | ✅ | `MON OK` |
| `from azure.mgmt.resource import ResourceManagementClient` | ✅ | `RES OK` |
| `from azure.identity import DefaultAzureCredential` | ✅ | `CRED OK` |

Captured at `last_validated: 2026-06-19` by `copilot-bot`.

---

## 5. Known issues at this pin

None at v1.0.0 — all three deps are GA stable.

---

## 6. Re-pin procedure

When upstream advances:

1. **Check new versions on PyPI**:
   ```bash
   curl -fsSL https://pypi.org/pypi/azure-mgmt-monitor/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   curl -fsSL https://pypi.org/pypi/azure-mgmt-resource/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
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
7. **Open PR**: title `chore(azure-resource-diagnostics): re-pin Azure Monitor SDKs → <ver>`.
   Touch ONLY `references/upstream-pin.md` and `SKILL.md` frontmatter.
   The `automation-pr-gate.yml` workflow enforces this.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx
responses surface as a refresh issue.

- <https://learn.microsoft.com/python/api/azure-mgmt-monitor/azure.mgmt.monitor.monitormanagementclient>
- <https://learn.microsoft.com/python/api/azure-mgmt-resource/azure.mgmt.resource.resourcemanagementclient>
- <https://learn.microsoft.com/azure/azure-monitor/essentials/diagnostic-settings>
- <https://pypi.org/project/azure-mgmt-monitor/>
- <https://pypi.org/project/azure-mgmt-resource/>
- <https://pypi.org/project/azure-identity/>
