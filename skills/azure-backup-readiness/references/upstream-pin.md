---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Azure Backup management SDKs and azure-identity
    credential chain. No git SHA tracking — version-pinned PyPI only.

packages:
  - name: azure-mgmt-recoveryservices
    source: pypi
    version: "4.0.1"
    upstream_changelog: https://pypi.org/project/azure-mgmt-recoveryservices/#history
    purpose: "RSV listing"
  - name: azure-mgmt-recoveryservicesbackup
    source: pypi
    version: "10.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-recoveryservicesbackup/#history
    purpose: "Protected item enumeration"
  - name: azure-mgmt-dataprotection
    source: pypi
    version: "2.0.1"
    upstream_changelog: https://pypi.org/project/azure-mgmt-dataprotection/#history
    purpose: "Backup Vault (DataProtection) listing"
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    purpose: "DefaultAzureCredential chain"

docs_to_revalidate:
  - https://learn.microsoft.com/python/api/azure-mgmt-recoveryservices/azure.mgmt.recoveryservices.recoveryservicesclient
  - https://learn.microsoft.com/python/api/azure-mgmt-recoveryservicesbackup/azure.mgmt.recoveryservicesbackup?view=azure-python
  - https://learn.microsoft.com/python/api/azure-mgmt-dataprotection/azure.mgmt.dataprotection.dataprotectionmgmtclient
  - https://learn.microsoft.com/azure/backup/backup-overview
  - https://pypi.org/project/azure-mgmt-recoveryservices/
  - https://pypi.org/project/azure-mgmt-recoveryservicesbackup/
  - https://pypi.org/project/azure-mgmt-dataprotection/
  - https://pypi.org/project/azure-identity/

known_issues: []

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    pip install -q "azure-mgmt-recoveryservices~=4.0.1" \
                    "azure-mgmt-recoveryservicesbackup~=10.0.0" \
                    "azure-mgmt-dataprotection~=2.0.1" \
                    "azure-identity~=1.25.3"
    python -c "from azure.mgmt.recoveryservices import RecoveryServicesClient; print('RSV OK')"
    python -c "from azure.mgmt.dataprotection import DataProtectionMgmtClient; print('BV OK')"
    python -c "from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient; print('RSVB OK')"
  expected_output:
    - "RSV OK"
    - "BV OK"
    - "RSVB OK"
  failure_signatures: []

last_validated: "2026-06-29"
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `azure-backup-readiness` skill

This file is the **machine-readable validation contract** for the
`azure-backup-readiness` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit
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
| `azure-mgmt-recoveryservices` | PyPI | **3.0.0** | RSV listing |
| `azure-mgmt-recoveryservicesbackup` | PyPI | **9.1.0** | Protected item enumeration |
| `azure-mgmt-dataprotection` | PyPI | **2.0.1** | Backup Vault (DataProtection) listing |
| `azure-identity` | PyPI | **1.19.0** | `DefaultAzureCredential` chain |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them
> identical. The agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail
pip install -q "azure-mgmt-recoveryservices~=3.0.0" \
                "azure-mgmt-recoveryservicesbackup~=9.1.0" \
                "azure-mgmt-dataprotection~=2.0.1" \
                "azure-identity~=1.19.0"
python -c "from azure.mgmt.recoveryservices import RecoveryServicesClient; print('RSV OK')"
python -c "from azure.mgmt.dataprotection import DataProtectionMgmtClient; print('BV OK')"
python -c "from azure.mgmt.recoveryservicesbackup.activestamp import RecoveryServicesBackupClient; print('RSVB OK')"
```

**Expected output** must contain (substring match):

- `RSV OK`
- `BV OK`
- `RSVB OK`

**Failure signatures** (treat as upstream regression — report distinctly):

_(none defined)_

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `from azure.mgmt.recoveryservices import RecoveryServicesClient` | ✅ | `RSV OK` |
| `from azure.mgmt.dataprotection import DataProtectionMgmtClient` | ✅ | `BV OK` |
| `from azure.mgmt.recoveryservicesbackup.activestamp import RecoveryServicesBackupClient` | ✅ | `RSVB OK` |

Captured at `last_validated: 2026-06-19` by `copilot-bot`.

---

## 5. Known issues at this pin

None at v1.0.0 — all four deps are GA stable.

---

## 6. Re-pin procedure

When upstream advances:

1. **Check new versions on PyPI**:
   ```bash
   curl -fsSL https://pypi.org/pypi/azure-mgmt-recoveryservices/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   curl -fsSL https://pypi.org/pypi/azure-mgmt-recoveryservicesbackup/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
   curl -fsSL https://pypi.org/pypi/azure-mgmt-dataprotection/json | python3 -c "import json, sys; d=json.load(sys.stdin); print(d['info']['version'])"
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
7. **Open PR**: title `chore(azure-backup-readiness): re-pin Azure Backup SDKs → <ver>`.
   Touch ONLY `references/upstream-pin.md` and `SKILL.md` frontmatter.
   The `automation-pr-gate.yml` workflow enforces this.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx
responses surface as a refresh issue.

- <https://learn.microsoft.com/python/api/azure-mgmt-recoveryservices/azure.mgmt.recoveryservices.recoveryservicesclient>
- <https://learn.microsoft.com/python/api/azure-mgmt-recoveryservicesbackup/azure.mgmt.recoveryservicesbackup.activestamp.recoveryservicesbackupclient>
- <https://learn.microsoft.com/python/api/azure-mgmt-dataprotection/azure.mgmt.dataprotection.dataprotectionmgmtclient>
- <https://learn.microsoft.com/azure/backup/backup-overview>
- <https://pypi.org/project/azure-mgmt-recoveryservices/>
- <https://pypi.org/project/azure-mgmt-recoveryservicesbackup/>
- <https://pypi.org/project/azure-mgmt-dataprotection/>
- <https://pypi.org/project/azure-identity/>
