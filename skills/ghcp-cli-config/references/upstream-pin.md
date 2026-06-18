---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: microsoft/playwright-mcp
  ref: main
  pinned_sha: b301c372ec741289eff1cf6aab9d3bec553f31e2
  pinned_commit_message: |
    chore(deps-dev): bump fast-uri from 3.1.0 to 3.1.2 (#1616)
  license: Apache-2.0
  notes: |
    ghcp-cli-config relies on multiple public config references. microsoft/playwright-mcp is the GitHub upstream selected for SHA drift because the skill pins the Playwright MCP launch shape; Azure MCP and GHCP docs are revalidated as URLs.
packages:
  - name: PyYAML
    source: pypi
    version: "6.0.3"
    upstream_changelog: https://pypi.org/project/PyYAML/
    notes: |
      Validation helper only, used to parse an inline sample MCP config YAML. Not a runtime dependency of the skill.
docs_to_revalidate:
  - https://docs.github.com/copilot/github-copilot-in-the-cli
  - https://github.com/microsoft/playwright-mcp
  - https://github.com/Azure/azure-mcp
  - https://pypi.org/project/PyYAML/
known_issues: []
validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    PINNED_SHA="${PINNED_SHA:-b301c372ec741289eff1cf6aab9d3bec553f31e2}"
    PINNED_VERSION="${PINNED_VERSION:-6.0.3}"
    WORK=".upstream-pin-smoke/ghcp-cli-config"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    remote="$(git ls-remote https://github.com/microsoft/playwright-mcp main | awk '{print $1}')"
    test "$remote" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    curl -fsSI -L "https://docs.github.com/copilot/github-copilot-in-the-cli" >/dev/null
    curl -fsSI -L "https://github.com/microsoft/playwright-mcp" >/dev/null
    curl -fsSI -L "https://github.com/Azure/azure-mcp" >/dev/null
    http_code=$(curl -sS -L -o /dev/null -w "%{http_code}" "https://learn.microsoft.com/api/mcp" || true)
    test "$http_code" = "405" -o "$http_code" = "200"
    echo "canonical config URLs ok"

    python -m venv "$WORK/.venv"
    . "$WORK/.venv/bin/activate"
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet "PyYAML~=${PINNED_VERSION}"
    python - <<'PY'
    import yaml
    sample = '''
    mcpServers:
      mslearn:
        type: http
        url: https://learn.microsoft.com/api/mcp
        tools: ['*']
        headers: {}
      Playwright:
        type: local
        command: cmd
        args: ['/c', 'npx', '-y', '@playwright/mcp@0.0.42', '--isolated', '--headless']
        tools: ['*']
    '''
    data = yaml.safe_load(sample)
    assert data['mcpServers']['mslearn']['type'] == 'http'
    assert data['mcpServers']['Playwright']['args'][-2:] == ['--isolated', '--headless']
    PY
    echo "sample config YAML parse ok"
  expected_output:
    - "pinned SHA verified"
    - "canonical config URLs ok"
    - "sample config YAML parse ok"
  failure_signatures: []
last_validated: 2026-06-18
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `ghcp-cli-config` skill

This file is the **machine-readable validation contract** for the
`ghcp-cli-config` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `microsoft/playwright-mcp` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `32017187a0f044b2b5cbc97c20a78a3878e00ac2` |
| **Pinned commit subject** | `chore(deps-dev): bump fast-uri from 3.1.0 to 3.1.2 (#1616)` |
| **License** | `Apache-2.0` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-28` |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft/playwright-mcp main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `PyYAML` | PyPI | **6.0.2** | Validation helper for parsing an inline MCP config sample. |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-32017187a0f044b2b5cbc97c20a78a3878e00ac2}"
PINNED_VERSION="${PINNED_VERSION:-6.0.2}"
WORK=".upstream-pin-smoke/ghcp-cli-config"

rm -rf "$WORK"
mkdir -p "$WORK"
remote="$(git ls-remote https://github.com/microsoft/playwright-mcp main | awk '{print $1}')"
test "$remote" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

curl -fsSI -L "https://docs.github.com/copilot/github-copilot-in-the-cli" >/dev/null
curl -fsSI -L "https://github.com/microsoft/playwright-mcp" >/dev/null
curl -fsSI -L "https://github.com/Azure/azure-mcp" >/dev/null
http_code=$(curl -sS -L -o /dev/null -w "%{http_code}" "https://learn.microsoft.com/api/mcp" || true)
test "$http_code" = "405" -o "$http_code" = "200"
echo "canonical config URLs ok"

python -m venv "$WORK/.venv"
. "$WORK/.venv/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet "PyYAML~=${PINNED_VERSION}"
python - <<'PY'
import yaml
sample = '''
mcpServers:
  mslearn:
    type: http
    url: https://learn.microsoft.com/api/mcp
    tools: ['*']
    headers: {}
  Playwright:
    type: local
    command: cmd
    args: ['/c', 'npx', '-y', '@playwright/mcp@0.0.42', '--isolated', '--headless']
    tools: ['*']
'''
data = yaml.safe_load(sample)
assert data['mcpServers']['mslearn']['type'] == 'http'
assert data['mcpServers']['Playwright']['args'][-2:] == ['--isolated', '--headless']
PY
echo "sample config YAML parse ok"
```

**Expected output** must contain (substring match):

- `pinned SHA verified`
- `canonical config URLs ok`
- `sample config YAML parse ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Playwright MCP SHA | ✅ | `pinned SHA verified` |
| Config docs and endpoints | ✅ | `canonical config URLs ok` |
| YAML sample parse | ✅ | `sample config YAML parse ok` |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 5. Known issues at this pin

No known issues are tracked for this pin. Note: `https://learn.microsoft.com/api/mcp`
returns 405 to HEAD, so validation checks that endpoint with GET while using HEAD
for documentation URLs.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/microsoft/playwright-mcp main
   ```
2. **Update front-matter** with the new SHA and commit subject. If PyYAML is
   refreshed for validation, update `packages[0].version` too.
3. **Run the validation script**:
   ```bash
   PINNED_SHA=<new-sha> PINNED_VERSION=<version> bash -c "$(yq '.validation.script' upstream-pin.md)"
   ```
4. **Verify expected output** from § 3.
5. **Update audit trail**.
6. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
7. **Open PR** touching only this file and `SKILL.md`.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://docs.github.com/copilot/github-copilot-in-the-cli>
- <https://github.com/microsoft/playwright-mcp>
- <https://github.com/Azure/azure-mcp>
- <https://pypi.org/project/PyYAML/>

---

## 8. Cross-references worth bookmarking

- `microsoft/playwright-mcp` — primary SHA drift signal for the Playwright MCP launch shape.
- `Azure/azure-mcp` — secondary MCP server reference checked as a URL.
- `https://learn.microsoft.com/api/mcp` — endpoint used by the mslearn MCP server; GET-only for validation.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. Run `validation.script`; it uses public GitHub, PyPI, and URL probes only.
> 2. Do not edit `references/mcp-config.*.json` or `settings.example.json` unless
>    a separate issue explicitly asks for a skill rewrite.
> 3. If the smoke passes, update this pin and PATCH-bump `SKILL.md` only.
> 4. Never edit `references/data-realism/**`.
