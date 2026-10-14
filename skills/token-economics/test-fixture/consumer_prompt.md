# Customer goal — `token-economics` skill smoke

You are a developer on a customer team. Your agent has a growing tool catalog and
you want to prove, with real numbers, that the `token-economics` skill's deferred
tool loading (`tool_search` + `defer_loading`) works against your CI deployment.

**This is an execution smoke, not a catalog inspection.** Do not browse or
summarize other skills. Execute the steps below directly in Bash tool calls.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You ARE the
running Copilot CLI process. Do NOT run `copilot -p ...`, `copilot --version`,
`npm install -g @github/copilot`, or any other `copilot ...` invocation from
inside a Bash tool call. A nested CLI has no GitHub auth, crashes, and overwrites
this run's transcript at `/tmp/token-economics-transcript.log` (AGENTS.md § 9.7
Pattern 27). The workflow already captures your output.

---

## Step −1 — Acknowledge the skill contract

Run exactly this (cheap audit evidence; do NOT `view` large files):

```bash
echo "skills/token-economics/SKILL.md"
sed -n '/^## Measure before and after/,/^## Other levers/p' skills/token-economics/SKILL.md | head -40
```

## Step 0 — Auth context (show, do not assert)

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited — relying on DefaultAzureCredential)"
```

If `FOUNDRY_PROJECT_ENDPOINT` prints empty, write the FAIL marker (Step 3) with
reason `auth context missing: FOUNDRY_PROJECT_ENDPOINT` and stop.

Pre-granted, do NOT re-grant: the CI identity already has **Cognitive Services
OpenAI User** on the shared AI Services account. This fixture creates **no**
Azure resources, so there is nothing to tear down.

## Step 1 — Install the skill's pinned dependencies

```bash
python3 -m venv .venv-token-economics-t3
. .venv-token-economics-t3/bin/activate
pip install --quiet "openai>=3.26,<4" "azure-identity>=1.25,<2"
```

## Step 2 — Run the canonical measurement script (do not rewrite it)

Run the skill's script exactly as documented. Do not write your own client code.

```bash
. .venv-token-economics-t3/bin/activate
set +e
python skills/token-economics/references/python/measure_tool_search.py \
  --endpoint "$FOUNDRY_PROJECT_ENDPOINT" \
  --model gpt-5.4-mini > /tmp/token-economics-report.json
echo "script_exit=$?"
set -e
python - <<'EOF'
import json
r = json.load(open("/tmp/token-economics-report.json"))
if "error" in r:
    print("ERROR", r["error"], r["detail"][:300]); raise SystemExit(0)
e, d = r["eager"]["totals"], r["deferred"]["totals"]
print("eager_input", e["input_tokens"], "eager_cached", e["cached_tokens"])
print("deferred_input", d["input_tokens"], "deferred_cached", d["cached_tokens"])
print("input_change_pct", r["input_token_change_pct"], "output_delta", r["output_token_delta"])
print("deferred_called", r["deferred"]["called_tools"], "search", r["deferred"]["tool_search_arguments"])
EOF
```

Success criteria (ALL must hold):

1. `script_exit=0` (the deferred variant called `get_shipping_record`).
2. The deferred run contains at least one `tool_search` argument entry.
3. `input_change_pct` is negative (deferred used fewer input tokens than eager).

On HTTP 429 / `Too Many Requests`, wait 60 seconds and rerun Step 2 once.

## Step 3 — Write the result marker (deterministic, MANDATORY)

Your FINAL action is a Bash tool call writing the marker file. The file's byte
content is what CI grades, not your reply. Do not print the marker token anywhere
else.

If all three success criteria held:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/token-economics-smoke-result
```

Otherwise (any criterion failed, script exit 1 or 2, auth error):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/token-economics-smoke-result
```
