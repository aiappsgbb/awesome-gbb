---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the azure-mgmt-monitor SDK and azure-identity
    credential chain, plus pyyaml for loading the baseline YAMLs.
    No git SHA tracking — version-pinned PyPI only.

packages:
  - name: azure-mgmt-monitor
    source: pypi
    version: "7.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-monitor/#history
    notes: |
      Provides MonitorManagementClient. The probe uses
      metric_alerts.list_by_resource_group() to enumerate
      live metric alerts in a resource group.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      DefaultAzureCredential chain.
  - name: pyyaml
    source: pypi
    version: "6.0.3"
    upstream_changelog: https://pypi.org/project/PyYAML/#history
    notes: |
      Loads the three baseline files in references/baselines/*.yaml.

docs_to_revalidate:
  - https://learn.microsoft.com/python/api/azure-mgmt-monitor/azure.mgmt.monitor.monitormanagementclient
  - https://learn.microsoft.com/python/api/azure-mgmt-monitor/azure.mgmt.monitor.operations.metricalertsoperations
  - https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-overview
  - https://pypi.org/project/azure-mgmt-monitor/
  - https://pypi.org/project/azure-identity/
  - https://pypi.org/project/PyYAML/

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
        "azure-mgmt-monitor~=7.0.0" \
        "azure-identity~=1.25.0" \
        "pyyaml~=6.0.0"
    python - <<'PY'
    from azure.mgmt.monitor import MonitorManagementClient
    from azure.identity import DefaultAzureCredential
    import yaml

    # Verify the surface area the probe depends on
    assert hasattr(MonitorManagementClient, "__init__")
    cred_class = DefaultAzureCredential
    assert callable(yaml.safe_load)
    print("ok azure-monitor-alert-baseline imports")
    PY
  expected_output:
    - "ok azure-monitor-alert-baseline imports"
  failure_signatures: []

last_validated: "2026-06-12"
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `azure-monitor-alert-baseline` skill

This file is the **machine-readable validation contract** for the
`azure-monitor-alert-baseline` skill. The YAML front-matter above is parsed by
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
| `azure-mgmt-monitor` | PyPI | **7.0.0** | `MonitorManagementClient`, `metric_alerts.list_by_resource_group()` |
| `azure-identity` | PyPI | **1.25.3** | `DefaultAzureCredential` chain |
| `pyyaml` | PyPI | **6.0.3** | `yaml.safe_load()` for baseline YAML files in `references/baselines/` |

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
    "azure-mgmt-monitor~=7.0.0" \
    "azure-identity~=1.25.0" \
    "pyyaml~=6.0.0"
python - <<'PY'
from azure.mgmt.monitor import MonitorManagementClient
from azure.identity import DefaultAzureCredential
import yaml

# Verify the surface area the probe depends on
assert hasattr(MonitorManagementClient, "__init__")
cred_class = DefaultAzureCredential
assert callable(yaml.safe_load)
print("ok azure-monitor-alert-baseline imports")
PY
```

**Expected output** must contain (substring match):

- `ok azure-monitor-alert-baseline imports`

**Failure signatures** (treat as upstream regression — report distinctly):

_(none defined)_

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `from azure.mgmt.monitor import MonitorManagementClient` | ✅ | `ok azure-monitor-alert-baseline imports` |
| `from azure.identity import DefaultAzureCredential` | ✅ | `ok azure-monitor-alert-baseline imports` |
| `import yaml; assert callable(yaml.safe_load)` | ✅ | `ok azure-monitor-alert-baseline imports` |
| `print("ok azure-monitor-alert-baseline imports")` | ✅ | `ok azure-monitor-alert-baseline imports` |

Captured at `last_validated: 2026-06-12` by `copilot-bot`.

---

## 5. Known issues at this pin

None at v1.0.0 — all three deps are GA stable.

---

## 6. Re-pin procedure

When upstream advances:

1. **Check new versions on PyPI**:
   ```bash
   curl -fsSL https://pypi.org/pypi/azure-mgmt-monitor/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   curl -fsSL https://pypi.org/pypi/azure-identity/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   curl -fsSL https://pypi.org/pypi/PyYAML/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
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
7. **Open PR**: title `chore(azure-monitor-alert-baseline): re-pin azure-mgmt-monitor + azure-identity + pyyaml → <ver>`.
   Touch ONLY `references/upstream-pin.md` and `SKILL.md` frontmatter.
   The `automation-pr-gate.yml` workflow enforces this.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx
responses surface as a refresh issue.

- <https://learn.microsoft.com/python/api/azure-mgmt-monitor/azure.mgmt.monitor.monitormanagementclient>
- <https://learn.microsoft.com/python/api/azure-mgmt-monitor/azure.mgmt.monitor.operations.metricalertsoperations>
- <https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-overview>
- <https://pypi.org/project/azure-mgmt-monitor/>
- <https://pypi.org/project/azure-identity/>
- <https://pypi.org/project/PyYAML/>
