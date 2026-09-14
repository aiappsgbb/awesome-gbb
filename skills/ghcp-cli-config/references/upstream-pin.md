---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: microsoft/playwright-mcp
  ref: main
  pinned_sha: 8a13ef8e9f7385a0f89477922127f31cbfde9761
  pinned_commit_message: |
    devops: restore npm publishing from GitHub Actions (#1734)
  license: Apache-2.0
  notes: |
    ghcp-cli-config relies on multiple public config references. microsoft/playwright-mcp is the GitHub upstream selected for SHA drift because the skill pins the Playwright MCP launch shape; Azure MCP and GHCP docs are revalidated as URLs.
    This SHA tracks launch-shape documentation, not the shipped npm runtime. SKILL.md and config samples intentionally remain pinned to @playwright/mcp@0.0.42; this refresh does not upgrade runtime packages, SDKs, or permission defaults.
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

    PINNED_SHA="${PINNED_SHA:-8a13ef8e9f7385a0f89477922127f31cbfde9761}"
    PINNED_VERSION="${PINNED_VERSION:-6.0.3}"
    WORK=".upstream-pin-smoke/ghcp-cli-config"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    remote="$(git ls-remote https://github.com/microsoft/playwright-mcp main | awk '{print $1}')"
    # #302: informational drift check only — do NOT hard-fail on SHA drift.
    # Upstream `main` moves continuously; a hard `test` flapped the
    # validate-pins gate on unrelated/docs-only PRs and drove perpetual
    # refresh-PR churn. SHA drift is detected + issue-filed by
    # skill-freshness.yml, which is the correct mechanism. The hard gate
    # for this pin is the canonical-URL + YAML-parse checks below.
    if [ "$remote" = "$PINNED_SHA" ]; then
      echo "upstream SHA in sync: ${PINNED_SHA}"
    else
      echo "upstream SHA drift (informational, non-fatal): pinned=${PINNED_SHA} remote=${remote}"
    fi
    echo "upstream SHA drift check ok"

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
    - "upstream SHA drift check ok"
    - "canonical config URLs ok"
    - "sample config YAML parse ok"
  failure_signatures: []
last_validated: 2026-09-14
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
| **Pinned SHA** | `8a13ef8e9f7385a0f89477922127f31cbfde9761` |
| **Pinned commit subject** | `devops: restore npm publishing from GitHub Actions (#1734)` |
| **License** | `Apache-2.0` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-09-14` |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft/playwright-mcp main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `PyYAML` | PyPI | **6.0.3** | Validation helper for parsing an inline MCP config sample. |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-8a13ef8e9f7385a0f89477922127f31cbfde9761}"
PINNED_VERSION="${PINNED_VERSION:-6.0.3}"
WORK=".upstream-pin-smoke/ghcp-cli-config"

rm -rf "$WORK"
mkdir -p "$WORK"
remote="$(git ls-remote https://github.com/microsoft/playwright-mcp main | awk '{print $1}')"
# #302: informational drift check only — do NOT hard-fail on SHA drift.
# Upstream `main` moves continuously; a hard `test` flapped the
# validate-pins gate on unrelated/docs-only PRs and drove perpetual
# refresh-PR churn. SHA drift is detected + issue-filed by
# skill-freshness.yml, which is the correct mechanism. The hard gate
# for this pin is the canonical-URL + YAML-parse checks below.
if [ "$remote" = "$PINNED_SHA" ]; then
  echo "upstream SHA in sync: ${PINNED_SHA}"
else
  echo "upstream SHA drift (informational, non-fatal): pinned=${PINNED_SHA} remote=${remote}"
fi
echo "upstream SHA drift check ok"

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

- `upstream SHA drift check ok`
- `canonical config URLs ok`
- `sample config YAML parse ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Playwright MCP SHA | ✅ | `upstream SHA drift check ok` |
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

---

## 10. Refresh validation — 2026-09-14

Validated by `copilot-bot` against public upstream
`8a13ef8e9f7385a0f89477922127f31cbfde9761`. Anonymous GitHub API and
pinned README reads succeeded; the comparison from
`b301c372ec741289eff1cf6aab9d3bec553f31e2` contains 24 commits.
The current README retains `mcp-config.json`, `type: local`,
`--isolated`, and `--headless`.

This SHA refresh tracks launch-shape documentation, not a runtime upgrade:
upstream source moved from package version `0.0.76` to `0.0.80`, while
the skill and config samples intentionally retain `@playwright/mcp@0.0.42`.
No SDK, runtime, permission default, or user configuration was changed.
The PyYAML table and executable mirror now match the existing `6.0.3`
front-matter value; the historical smoke record in § 4 is unchanged.

The exact YAML `validation.script` ran in an owned temporary directory
with `PIN_VALIDATION_REPO_ROOT` pointing to the canonical worktree.
The isolated environment retained the bundled Git tool's `GIT_EXEC_PATH`;
without that locator the initial attempt exited 128 before any checks.
The corrected execution exited **0** and produced all three required markers:

```text
upstream SHA drift check ok
canonical config URLs ok
sample config YAML parse ok
```

The script and its § 3 mirror are byte-identical. Requests were bounded
with connection and total timeouts and at most one curl retry.
Validation uses public GitHub/docs/PyPI and the unauthenticated MCP
endpoint's HTTP status only; no Azure or workplace API was executed.
Azure T3 is not applicable to this metadata-only refresh.

The initial online runtime probe was blocked: the local package was
absent, the temporary npm install exited 1 with `ENOTCONN`, and the
canonical registry probe exited 35 with a socket connection failure.
No further online installation attempts were made.

The exact public `0.0.42` package and its dependencies were already in
the standard npm cache. Its tarball matched the published integrity in
the cached registry metadata:

```text
sha512-oYkZnxq6vSPAVUD7Wjensok3IO8m7quCoJLPkRBk4VGx8MGA7zyGTgqjB/fpqB4PABa96TW7dkT/psln0tLipg==
```

An owned-temporary-directory `npm install --offline --ignore-scripts`
completed with exit **0**, using only cached packages. The package's
declared `mcp-server-playwright` executable (`cli.js`) ran with `--help`,
exited **0**, and advertised both `--isolated` and `--headless`.
No browser was launched or user configuration changed.
