# Customer goal — `azure-monitor-alert-baseline` skill smoke

You are an SRE / observability engineer on a customer team. You just installed the
`awesome-gbb` Copilot CLI plugin and you want to prove that the
`azure-monitor-alert-baseline` skill works end-to-end against your CI Azure
subscription by running its SRE-104 probe against the CI resource group.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run
every Bash code block below in order. Do NOT inspect repo files, do NOT
run `validate-skills.py`, do NOT rebuild docs, do NOT `git status` —
those are catalog-author concerns, not consumer-smoke concerns. Your only
acceptable terminal state is a Bash tool call that writes a marker file
to `/tmp/azure-monitor-alert-baseline-smoke-result` (Step 3). If you find yourself
reading `skill-deps.yml`, `upstream-pin.md`, or anything under `docs/`,
you are off-script — stop and execute Step −1.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You
ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. Doing so spawns
a nested CLI process WITHOUT GitHub auth (the workflow only sets
`COPILOT_PROVIDER_BEARER_TOKEN` for our Foundry routing, NOT
`COPILOT_GITHUB_TOKEN`), which will (a) crash with "No authentication
information found" and (b) overwrite this run's transcript at
`/tmp/azure-monitor-alert-baseline-transcript.log`, defeating the workflow's
retry classifier (AGENTS.md § 9.7 Pattern 19 addendum). The workflow
ALREADY captures your output via the outer `tee` — your job is to
EXECUTE Steps −1 through 3 directly in Bash tool calls, not to "run the smoke".

This fixture is **read-only**: it does NOT create any Azure resources,
does NOT deploy any infrastructure, and does NOT invoke any models.

---

## Step −1 — Acknowledge skill contract (mandatory FIRST action)

Before Step 0, run this echo as a Bash tool call. The grep on
`skills/azure-monitor-alert-baseline/` in the output is what the workflow's
post-hoc audit step grades on as "agent loaded the skill". Do NOT use
the `view` tool on SKILL.md — the chunked reads inflate per-turn
context past our TPM ceiling (AGENTS.md § 9.7 Pattern 19 v2).

```bash
echo "Loading skill contract: skills/azure-monitor-alert-baseline/SKILL.md (version 1.0.x)"
echo "Fixture path:           skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md"
echo "Audit grade evidence:   present"
```

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on the `az`
cache check — `azure/login@v2` already validated the credentials
upstream and Copilot CLI subprocesses don't always inherit `~/.azure/`
(AGENTS.md § 9.7 Pattern 17).

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, or `AZURE_SUBSCRIPTION_ID`
prints empty, the workflow's `env:` block is broken (Pattern 11). That
is a workflow bug, not a skill bug. Write the FAIL marker (Step 3) with
reason `auth context missing: <var-name>` and stop.

Do NOT run `command -v`, `find /`, or `curl -fsSL` to hunt for tooling
(Pattern 15). The CI runner already has `az` CLI, `python3`, and `pip`
— assume them.

---

## Step 1 — Run the SRE-104 probe against `rg-awesome-gbb-ci`

The exact CLI invocation — run it verbatim, no improvisation:

```bash
cd skills/azure-monitor-alert-baseline/references/python
pip install --quiet "azure-mgmt-monitor~=7.0.0" "azure-identity~=1.25.0" "pyyaml~=6.0.0"
mkdir -p out
python __main__.py \
    --subscription-id "$AZURE_SUBSCRIPTION_ID" \
    --resource-group rg-awesome-gbb-ci \
    --alert-baseline-kind foundry_pilot
```

Key contract points:
- `mkdir -p out` before the probe runs (avoids ENOENT on manifest write)
- `rg-awesome-gbb-ci` is the literal CI resource group name — do NOT
  substitute a per-fixture child RG (this is a read-only probe, not a deploy)
- `--alert-baseline-kind foundry_pilot` matches the YAML file stem in
  `references/baselines/foundry_pilot.yaml`
- Exit 0 means probe-complete (any of `ok`/`needs_attention`/`errored` are
  all valid results); exit 1 means unexpected exception

If the probe exits non-zero, write the FAIL marker with reason
`probe exited <exit-code>` and stop.

---

## Step 2 — Parse and assert the SRE-104 manifest

The probe writes `out/SRE-104.json` relative to CWD
(`skills/azure-monitor-alert-baseline/references/python/`). Parse it and assert
the spec §4.3.1 8-key shape:

```bash
python - <<'PY'
import json, sys
manifest = json.loads(open("out/SRE-104.json").read())
required = {"finding_id","scope","result","observations","remediation_hints","confidence","probed_at","error"}
missing = required - manifest.keys()
assert not missing, f"missing keys: {missing}"
assert manifest["finding_id"] == "SRE-104", f"finding_id mismatch: {manifest['finding_id']!r}"
assert manifest["result"] in ("ok","needs_attention","errored"), f"bad result: {manifest['result']!r}"
print(f"manifest ok: result={manifest['result']} observations={len(manifest['observations'])} confidence={manifest['confidence']}")
PY
```

If the python block exits non-zero (assertion failed or file missing),
write the FAIL marker with the assertion message and stop.

---

## Step 3 — Write the result marker (deterministic, MANDATORY)

After Step 2 succeeds, your FINAL action is to invoke the Bash tool to
write the marker file. The file's literal byte content is what CI grades;
your assistant-text reply is NOT graded.

On success (auth context complete AND probe exited 0 AND manifest
assertions all passed):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-monitor-alert-baseline-smoke-result
```

On any failure in Steps 0/1/2:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-monitor-alert-baseline-smoke-result
```

The marker file is single-source-of-truth (Pattern 12). Do not print
the marker token anywhere else in your reply — no echoes, no summaries,
no fenced code blocks containing the literal string. The Bash tool
`printf` is the only legitimate emission path.

Target wall-clock: 2-4 min.
