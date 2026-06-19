**Skill under test:** `azure-resource-diagnostics`

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. (AGENTS.md
§9.7 Pattern 27.)

This is an EXECUTION smoke, not a catalog inspection.

### Step −1 — Acknowledge skill contract

```bash
echo "skills/azure-resource-diagnostics/SKILL.md"
```

### Step 0 — Verify CI auth contract

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited)"
```

### Step 1 — Install SDKs + run probe

```bash
pip install -q "azure-mgmt-monitor~=6.0.0" \
                "azure-mgmt-resource~=23.1.0" \
                "azure-identity~=1.19.0"
mkdir -p out/ard-smoke
AZURE_RESOURCE_DIAGNOSTICS_OUT=out/ard-smoke \
  python skills/azure-resource-diagnostics/references/python/__main__.py \
    --sub "$AZURE_SUBSCRIPTION_ID" \
    --rg  "${CI_RESOURCE_GROUP:-<ci-resource-group>}"
```

### Step 2 — Validate shape

```bash
ls out/ard-smoke/*.json | head -1 | xargs -I{} python -c "
import json, sys
d = json.load(open(sys.argv[1]))
required = {'finding_id','skill','subscription_id','resource_group','resources','findings','summary','manifest_path','probed_at'}
missing = required - set(d.keys())
assert not missing, f'missing keys: {missing}'
assert d['skill'] == 'azure-resource-diagnostics'
assert 'target_resource_types_filter' in d['summary']
print('shape OK')
" {}
```

### Step N — Write the result marker (MANDATORY)

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-resource-diagnostics-smoke-result
```

On failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-resource-diagnostics-smoke-result
```

The marker file is single-source-of-truth (Pattern 12). Do not print
the marker token anywhere else in your reply — no echoes, no summaries,
no fenced code blocks containing the literal string. The Bash tool
`printf` is the only legitimate emission path.
