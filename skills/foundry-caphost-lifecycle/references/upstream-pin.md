---
schema_version: 2

freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  repo: Azure/azure-sdk-for-python
  ref: main
  pinned_sha: ""
  pinned_commit_message: |
    PyPI-only wrapper — no SHA pin. Tracks azure-mgmt-cognitiveservices
    + azure-identity stable releases via cap windows below. The freshness
    detector watches PyPI for new minors / majors.
  license: MIT
  notes: |
    This skill is a Day-2 operations overlay on top of the MS Learn
    capability-hosts page. The "upstream" is the combination of:
      1. The Azure REST contract (api-version 2025-06-01) documented on
         https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts
      2. The azure-mgmt-cognitiveservices Python SDK (CapabilityHost models)
      3. The az CLI cognitiveservices account verbs (delete, purge, recover,
         list-deleted, show-deleted) — GA, no extension required
    There is no single git SHA to pin. PyPI cap windows below + MS Learn
    URL revalidation cover the surface.

packages:
  - name: azure-mgmt-cognitiveservices
    source: pypi
    version: "~=14.1.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/cognitiveservices/azure-mgmt-cognitiveservices/CHANGELOG.md
    notes: |
      Cap window allows 14.1.x patch upgrades inside 14.x; bump cap when a
      14.2 / 15.0 lands and re-validate the CapabilityHost model surface.
  - name: azure-identity
    source: pypi
    version: "~=1.25.3"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md
    notes: |
      Pinned to match peer skills' baseline (foundry-prompt-agents,
      foundry-hosted-agents, foundry-memory). DefaultAzureCredential
      contract is stable inside the 1.25.x window.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts
  - https://learn.microsoft.com/cli/azure/cognitiveservices/account
  - https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks
  - https://pypi.org/project/azure-mgmt-cognitiveservices/
  - https://pypi.org/project/azure-identity/

known_issues: []

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    # ── SDK import smoke (proves the CapabilityHost surface still exists)
    python3 -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "azure-mgmt-cognitiveservices~=14.1.0" \
      "azure-identity~=1.25.3"
    python3 -c "
    import azure.mgmt.cognitiveservices as mc
    from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
    from azure.mgmt.cognitiveservices.models import CapabilityHost, CapabilityHostProperties
    from azure.identity import DefaultAzureCredential
    print(f'azure-mgmt-cognitiveservices={mc.VERSION}')
    print('caphost-sdk-import-ok')
    "

    # ── az CLI surface smoke (proves the GA purge verb is present)
    # No Azure auth needed: --help exits 0 against the local CLI binary.
    az cognitiveservices account purge --help > /dev/null && \
      echo "caphost-purge-cli-ok"
    az cognitiveservices account list-deleted --help > /dev/null && \
      echo "caphost-list-deleted-cli-ok"
    az cognitiveservices account recover --help > /dev/null && \
      echo "caphost-recover-cli-ok"
  expected_output:
    - "caphost-sdk-import-ok"
    - "caphost-purge-cli-ok"
    - "caphost-list-deleted-cli-ok"
    - "caphost-recover-cli-ok"
  failure_signatures:
    - "ImportError"
    - "ModuleNotFoundError"
    - "is not in the 'cognitiveservices' command group"

last_validated: 2026-07-06
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `foundry-caphost-lifecycle` skill

This file is the **machine-readable validation contract** for the
`foundry-caphost-lifecycle` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | Azure REST API + Python SDK + `az` CLI |
| **REST API version** | `2025-06-01` |
| **SDK package** | `azure-mgmt-cognitiveservices` ~= 14.1.0 |
| **Identity package** | `azure-identity` ~= 1.25.3 |
| **CLI surface** | `az cognitiveservices account {delete,purge,recover,list-deleted,show-deleted}` (GA) |
| **First authored against** | 2026-06-09 |
| **Last re-validated** | 2026-06-09 |

The live-Azure proof for this skill is the fixture at
`skills/foundry-caphost-lifecycle/test-fixture/consumer_prompt.md` — the
matrix leg in `.github/workflows/skill-test.yml` exercises the full caphost
lifecycle (create → idempotent replay → delete → soft-delete → purge → verify)
against `rg-awesome-gbb-ci` on every PR.

---

## 2. Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-mgmt-cognitiveservices` | PyPI | **~= 14.1.0** | Cap window allows 14.1.x patch upgrades inside 14.x |
| `azure-identity` | PyPI | **~= 1.25.3** | Matches peer skills' baseline |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: the `validation.script` block in the front-matter
> is the SPEC. CI re-runs it on the runner via `pin-validation.yml`. Keep
> the prose below in sync with the YAML.

```bash
#!/usr/bin/env bash
set -euo pipefail

# SDK import smoke
python3 -m venv .venv
. .venv/bin/activate
pip install --quiet \
  "azure-mgmt-cognitiveservices~=14.1.0" \
  "azure-identity~=1.25.3"
python3 -c "
import azure.mgmt.cognitiveservices as mc
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.cognitiveservices.models import CapabilityHost, CapabilityHostProperties
from azure.identity import DefaultAzureCredential
print(f'azure-mgmt-cognitiveservices={mc.VERSION}')
print('caphost-sdk-import-ok')
"

# az CLI surface smoke (no auth required)
az cognitiveservices account purge --help > /dev/null && echo "caphost-purge-cli-ok"
az cognitiveservices account list-deleted --help > /dev/null && echo "caphost-list-deleted-cli-ok"
az cognitiveservices account recover --help > /dev/null && echo "caphost-recover-cli-ok"
```

**Expected output** must contain (substring match):

- `caphost-sdk-import-ok`
- `caphost-purge-cli-ok`
- `caphost-list-deleted-cli-ok`
- `caphost-recover-cli-ok`

**Failure signatures** (upstream regression):

- `ImportError` — SDK module surface broke
- `ModuleNotFoundError` — package name changed upstream
- `is not in the 'cognitiveservices' command group` — `az` CLI surface dropped a verb

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `azure-mgmt-cognitiveservices` import | ✅ | `caphost-sdk-import-ok` |
| `az cognitiveservices account purge` | ✅ | `caphost-purge-cli-ok` |
| `az cognitiveservices account list-deleted` | ✅ | `caphost-list-deleted-cli-ok` |
| `az cognitiveservices account recover` | ✅ | `caphost-recover-cli-ok` |

Captured at `last_validated: 2026-06-09` by `copilot-bot`.

---

## 5. Known issues at this pin

None at the v1.0.0 pin. The MS Learn caphost page and the `az
cognitiveservices` surface are stable. The Day-2 field-experience overlay
(SAL release, soft-delete/purge sequence) is proven by the fixture, not by
the upstream — there is no upstream issue to track.

---

## 6. Re-pin procedure

When upstream advances:

1. **Bump the SDK cap** in `packages[].version` if a new minor lands
   (e.g. 14.1 → 14.2 → `~=14.2.0`). Patch upgrades inside the cap window
   are auto-covered, no PR needed.
2. **Re-run `validation.script`** (or push an empty commit to retrigger
   `pin-validation.yml` on the latest cap).
3. **Verify expected_output** — each substring must appear in stdout.
4. **Bump SKILL.md `metadata.version` PATCH** (per AGENTS.md § 5).
5. **Open PR**: title `chore(foundry-caphost-lifecycle): re-pin → <new>`.
   Touch ONLY this file and SKILL.md frontmatter. Tag commit `[pin-refresh]`
   if `automation-pr-gate.yml` requires it.

For MS Learn page updates (api-version bumps, new field semantics, etc.),
re-read the MS Learn page in full, update SKILL.md § 4 (Constraints recap)
and § 6 (Create REST shape), then bump SKILL.md MINOR. The `[skill-rewrite]`
commit tag is required for any SKILL.md body change.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts>
- <https://learn.microsoft.com/cli/azure/cognitiveservices/account>
- <https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks>
- <https://pypi.org/project/azure-mgmt-cognitiveservices/>
- <https://pypi.org/project/azure-identity/>

---

## 8. Cross-references worth bookmarking

- [`foundry-vnet-deploy/SKILL.md`](../../foundry-vnet-deploy/SKILL.md) §11.4
  — the create-time capability host verification this skill picks up at Day-2.
- [Azure CLI cognitiveservices account reference](https://learn.microsoft.com/cli/azure/cognitiveservices/account)
  — `delete`, `purge`, `recover`, `list-deleted`, `show-deleted`.
- [`azure-mgmt-cognitiveservices` CHANGELOG](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/cognitiveservices/azure-mgmt-cognitiveservices/CHANGELOG.md)
  — watch for `CapabilityHost` / `CapabilityHostProperties` model breakage.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. The `validation.script` in the front-matter is your spec. Run it.
> 2. If it passes, update front-matter (`packages[].version` if you bumped
>    the cap, `last_validated`, `validated_by: copilot-bot`) and bump
>    SKILL.md `metadata.version` PATCH. Touch nothing else unless the
>    issue body explicitly authorises a body change with `[skill-rewrite]`.
> 3. If it fails, comment on the issue with the failure output and
>    **do NOT open a PR**.
> 4. The matrix-leg fixture is the live-Azure proof for this skill —
>    don't try to substitute pin validation for it. They cover different
>    surfaces (pin = static SDK contract; fixture = live REST + CLI).
