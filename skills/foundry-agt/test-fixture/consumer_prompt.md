# Customer goal — `foundry-agt` skill live T3 smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-agt` skill's
in-process MAF governance middleware works end-to-end **against real Azure
resources** — a real Entra OIDC token, a real `FoundryChatClient` inference
call through the CI Foundry deployment, a real capability-hook allow/deny
pair, and a real `AuditLog` hash-chain — not just a local structural probe.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run the
Bash blocks below in order. Do NOT inspect unrelated repository files, do
NOT run `validate-skills.py`, do NOT rebuild docs, do NOT `git status` —
those are catalog-author concerns, not consumer-smoke concerns. Your only
acceptable terminal state is the final Bash tool call in Step 2, which
writes the marker file.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You ARE
the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call, and do NOT install
or probe the Copilot CLI. Doing so spawns a nested CLI process without the
right auth context, crashes, and clobbers this run's transcript, defeating
the workflow's retry classifier (AGENTS.md § 9.7 Pattern 27). The workflow
already captures your output via its own `tee` — your job is to EXECUTE the
Steps below directly in Bash tool calls, not to "run the smoke".

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Agent Governance Toolkit (AGT) or the Microsoft Agent
Framework (MAF) — the two reference probes in Step 2 are the skill's
canonical, already-vetted evidence source; you are executing them verbatim,
not reimplementing them.

The shared CI Foundry account, project, and model deployment used below are
**read-only** from this fixture's perspective: the smoke performs one
benign chat completion against the existing deployment and reads the
resulting response. It does NOT create, delete, or tear down any Azure
resource, ACR image, ACA app, or role assignment — there is nothing to
clean up when the smoke finishes.

---

## Step −1 — Acknowledge skill contract (mandatory FIRST action)

Run this echo as your first Bash tool call. It is the audit evidence the
workflow's post-hoc step grades on as "agent loaded the skill". Do NOT use
the `view` tool on `SKILL.md` — the file is large and chunked reads inflate
per-turn context past the CI model deployment's per-minute TPM ceiling
(AGENTS.md § 9.7 Pattern 19). This fixture is fully self-contained and does
not require `SKILL.md` to be loaded into context.

```bash
echo "skills/foundry-agt/SKILL.md"
```

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log only. Do NOT gate flow on the `az`
CLI cache — Copilot CLI subshells don't reliably inherit `~/.azure/`, and
the real gate for this smoke is `DefaultAzureCredential` acquiring a real
token in Step 2 (AGENTS.md § 9.7 Pattern 17).

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
az account show --output table || echo "(az cache not inherited — DefaultAzureCredential uses the OIDC environment)"
```

All five lines above MUST print `...=set`. If any prints empty, the
workflow's `env:` block is broken (Pattern 11) — that is a workflow bug,
not a skill bug. In that case go straight to Step 2's failure path with
reason `auth context missing: <var-name>`.

---

## Step 1 — What Step 2 proves

The single Bash tool call in Step 2 builds a throwaway virtualenv, installs
the exact pinned package set the skill documents, and runs the skill's two
canonical reference probes straight through, in order:

1. `skills/foundry-agt/references/python/contract_probe.py` — the
   no-network structural contract: exact pinned package versions, the
   `agent-governance-toolkit` factory stack wiring, the real
   `FunctionTool`/capability-hook allow-then-deny path, the `AuditLog`
   hash-chain round-trip, and the `agt doctor` / `agt verify` CLI surface.
2. `skills/foundry-agt/references/python/live_t3_probe.py` — the live T3
   proof against real Azure: an explicit async `DefaultAzureCredential`
   token acquisition for `https://ai.azure.com/.default`, a real
   `FoundryChatClient` built from `FOUNDRY_PROJECT_ENDPOINT` and
   `FOUNDRY_MODEL_DEPLOYMENT`, one benign prompt run through a real `Agent`
   carrying the real governance middleware stack plus a counting chat
   middleware, a deterministic re-exercise of the same capability guard
   (one allowed execution, one denial, zero dangerous executions), and a
   final `AuditLog` integrity + CloudEvents export check.

Both scripts print their own exact evidence lines as they run and exit
non-zero on any assertion failure — you do not need to parse their output
yourself, you only need to let them run to completion inside the venv and
let the shell's own error handling decide the marker outcome.

---

## Step 2 — Build, run, and mark (deterministic, MANDATORY, single Bash call)

Your FINAL action is to invoke the Bash tool exactly once with the script
below, unmodified, rooted at `$GITHUB_WORKSPACE`. The marker file's literal
byte content is what CI grades — your assistant-text reply is NOT graded.
The success token below is rendered with a leading underscore
(`_MOKE_RESULT`) in this prose and inside the script itself so it can never
match the workflow's anchored grep by accident; the `sed 's/^_/S/'` in the
script is what turns it into the real marker at the moment of the write.
Do not substitute it back to a literal leading `S` anywhere in your own
reply, echoes, or summaries — only the script's own `sed` pipeline may do
that, and only into the marker file.

```bash
MARKER=/tmp/foundry-agt-smoke-result
EVIDENCE=/tmp/foundry-agt-smoke-evidence

on_error() {
  rc=$?
  printf '_MOKE_RESULT=FAIL exit=%s\n' "$rc" | sed 's/^_/S/' > "$MARKER"
  exit "$rc"
}

set -Eeuo pipefail
trap on_error ERR

cd "$GITHUB_WORKSPACE"
: > "$EVIDENCE"

python3 -m venv .venv-foundry-agt-t3
source .venv-foundry-agt-t3/bin/activate
pip install --quiet --upgrade pip
pip install --quiet \
  "agent-governance-toolkit[full]~=4.1.0" \
  "agent-framework-core~=1.13.0" \
  "agent-framework-foundry~=1.10.4" \
  "agent-framework-openai~=1.12.0" \
  "azure-identity~=1.25.3"
pip check

python3 skills/foundry-agt/references/python/contract_probe.py | tee -a "$EVIDENCE"
python3 skills/foundry-agt/references/python/live_t3_probe.py | tee -a "$EVIDENCE"

deactivate
rm -rf .venv-foundry-agt-t3

trap - ERR
printf '_MOKE_RESULT=PASS\n' | sed 's/^_/S/' > "$MARKER"
```

`set -Eeuo pipefail` plus the `ERR` trap means: if venv creation, the pip
install, `pip check`, or either probe exits non-zero — `pipefail` makes a
failure anywhere in a `... | tee -a` pipeline propagate even though `tee`
itself always exits 0 — the trap fires immediately, writes the obfuscated
FAIL line with the real exit code, and re-raises that same exit code. The
PASS line at the very end is reached only if every command above it,
including both probes, exited 0. Do not add a broad `try/catch` or `|| true`
anywhere in this script that would swallow a failure before the trap sees
it.

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks reproducing it outside the script above. The Bash tool write inside
this one script is the only legitimate emission path.
