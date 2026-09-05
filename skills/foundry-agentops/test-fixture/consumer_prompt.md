# Customer goal - foundry-agentops smoke.

You are a developer on a customer team. Prove that the future
`foundry-agentops` skill executes against the owner-approved Foundry
project (CI or a separately authorized manual equivalent) by onboarding one temporary Foundry prompt agent into an isolated
temporary workspace, running one AgentOps analysis/eval/evidence cycle, and
cleaning up the temporary assets. Execution, eval quality and Doctor readiness
are separate outcomes; no smoke result certifies production readiness.

**This is a self-contained EXECUTION smoke, not a catalog-inspection task.**
Read `skills/foundry-agentops/SKILL.md` before acting. If that file does not
exist yet, treat the contract as unresolved: skip all later steps and finish
with the FAIL marker in Step 8 using the literal one-line reason
`missing skills/foundry-agentops/SKILL.md`.

**CRITICAL - never invoke `copilot` recursively from a Bash tool.** You ARE the
running Copilot CLI process. Do NOT run `copilot -p ...`, `copilot --version`,
`npm install -g @github/copilot`, or any other `copilot ...` command. The
workflow already captures your output through its outer `tee`; execute the
smoke steps directly.

**Hard scope guardrails.** Do NOT generate any Threadlight manifest or files.
Do NOT modify APIM, Citadel, RBAC, networking, branch protection, GitHub
environments, or environment approvals. Do NOT create or edit workflow files.
Do NOT provision shared infrastructure. This smoke is limited to:

1. reading the `foundry-agentops` and `foundry-prompt-agents` skill contracts,
2. creating one temporary prompt agent with a UUID suffix,
3. creating one isolated temporary AgentOps workspace,
4. running one AgentOps analyze/eval/doctor cycle there,
5. deleting the temporary prompt agent and local workspace,
6. writing exactly one marker file.

---

## Step -1 - Acknowledge the skill contract (mandatory FIRST action)

Your first Bash action must be:

```bash
echo "skills/foundry-agentops/SKILL.md"
```

This lightweight line is the workflow's audit breadcrumb. Do not substitute a
different path and do not skip the later real `SKILL.md` read.

---

## Step 0 - Auth context (route-aware presence, not credential proof)

The parent owner must establish the SKILL.md **PRE-EXECUTION credential isolation**
contract **before launching** this fixture or making any CLI/native call.
Require process-local `AZURE_CONFIG_DIR`, `AZD_CONFIG_DIR`, and exactly
one approved `AZURE_TOKEN_CREDENTIALS` value: `AzureCliCredential` for an
owner-provisioned cache containing only the approved identity, or
`EnvironmentCredential` / `WorkloadIdentityCredential` with a fresh empty CLI
directory. Inherit the identical paths and selector in **every Bash** call,
including helpers, eval, Doctor and cleanup; do not rely on a prior Bash export.
Missing or changed isolation means STOP, not fallback to global caches.
For **all three** modes (including approved cached CLI), `AZD_CONFIG_DIR` must
be private and **fresh empty**, with **no login or token cache** copied into or
created in it. Keep it credential-empty throughout the run; never mutate/repoint
it, authenticate azd, or deliberately execute azd commands against it.

AgentOps v0.14.0's shared factory prefers available CLI credentials even when
approved environment credentials exist. An empty CLI cache alone is insufficient:
the explicit selector constrains but does not fully determine the default chain.
The factory's **`exclude_developer_cli_credential=False`** overrides that selector
and retains **AzureDeveloperCliCredential** beside the selected credential.
Doctor resource/RBAC paths use this default. The native leg can still attempt
azd noninteractively; the same inherited empty directory must make it unavailable,
never allow a global login. This is usable-credential isolation, not a promise
of one constructed credential or no azd subprocess. The owner must
authorize the actual selected identity and pre-grant its source/inference scopes.
No login, account switching, global account inspection, cache copying or RBAC
changes are allowed. No intentional azd operation is authorized by this fixture;
if one is required, STOP and hand off to its existing owner separately.

**CI runner context is authoritative**: preserve show-don't-assert; do not add
cache availability, subscription equality or membership assertions in CI.
For a separately authorized manual run, perform any read-only membership check
only in its approved isolated cache per SKILL.md, never in a global cache.
The parent workflow must establish isolation before its authentication step;
the fixture cannot repair an inherited wrong identity. Select the parent's recorded route, not one inferred from whichever credentials
happen to exist. These labels are **fixture arguments**, not native config fields:

| Route argument | Actual principal / required values |
|---|---|
| `cached-user` | Isolated cached CLI **user**; `AzureCliCredential`. Leave `AZURE_CLIENT_ID` unset: a user is not an application credential. Never invent the CLI public application ID or use `N/A` as a credential value. |
| `ci-cli` | CI service-principal authenticated by the workflow into its isolated CLI cache; `AzureCliCredential`. Preserve the real `AZURE_CLIENT_ID`, tenant and subscription exported by CI. |
| `environment` | `EnvironmentCredential`; real client/tenant plus approved secret or certificate settings. CLI cache stays empty. |
| `workload` | `WorkloadIdentityCredential`; real client/tenant plus readable `AZURE_FEDERATED_TOKEN_FILE`. CLI cache stays empty. |

There are still three credential selectors; the two CLI cases truthfully
distinguish the principal type. All routes require tenant/subscription, project
endpoint and stable isolated config paths. The unchanged CI service-principal
path is **not tested by a manual cached-user run**.

Execute this whole Python block with `python3 - "<route>"` and the block on
stdin (a quoted heredoc). Do not use optimization. It checks presence/selection
only; the owner verifies the isolated cache, token-file access, actual principal
and approved scopes before launch. No tokens or credential values are printed.

```python
# BEGIN AGENTOPS AUTH CONTEXT CHECK
import os
import sys

try:
    if not __debug__:
        raise ValueError("assertions required")
    route, = sys.argv[1:]
    selectors = {
        "cached-user": "AzureCliCredential", "ci-cli": "AzureCliCredential",
        "environment": "EnvironmentCredential", "workload": "WorkloadIdentityCredential",
    }
    assert os.environ.get("AZURE_TOKEN_CREDENTIALS") == selectors[route]
    required = [
        "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_TOKEN_CREDENTIALS",
    ]
    if route == "cached-user":
        assert not os.environ.get("AZURE_CLIENT_ID")
    else:
        required.append("AZURE_CLIENT_ID")
    if route == "environment":
        assert os.environ.get("AZURE_CLIENT_SECRET") or os.environ.get("AZURE_CLIENT_CERTIFICATE_PATH")
    if route == "workload":
        required.append("AZURE_FEDERATED_TOKEN_FILE")
    for key in required:
        value = os.environ.get(key, "").strip()
        assert value and value.casefold() not in {"n/a", "not applicable", "none"}
        assert not value.startswith("<")
except Exception:
    raise SystemExit("auth context missing or inconsistent with approved route") from None

for key in required:
    print(f"{key}=set")
if route == "cached-user":
    print("AZURE_CLIENT_ID=unset (cached user; not required)")
# END AGENTOPS AUTH CONTEXT CHECK
```

On failure stop and finish Step 8 with
`auth context missing or inconsistent with approved route`; never synthesize values.

Do NOT run `command -v`, `find /`, or `curl -fsSL` to hunt for tooling. Use
the preinstalled `python3`, `pip`, and `az` already on the runner.

---

## Step 1 - Read the source-of-truth skill contracts

Before writing any code or creating any resource:

1. Read `skills/foundry-agentops/SKILL.md`.
2. Read `skills/foundry-prompt-agents/SKILL.md` because this smoke creates and
   later deletes a temporary prompt agent using that dependency contract.

If either file is missing, unreadable, or conflicts with the hard guardrails
above, stop immediately and finish with Step 8 using the shortest precise
literal one-line reason. Do NOT improvise from training data when the skill
contracts are available.

### PRE-EXECUTION telemetry approval — required before resources or native operations

Follow the gate in
`skills/foundry-agentops/references/day2-runbook.md#pre-execution-telemetry-approval`.
Require an existing owner approval record identifying the actual tenant-local
telemetry destination, payload capture, access and retention for this run.
Reconcile it with the effective environment, selected workspace dotenv and
Foundry-attached App Insights before invoking eval or Doctor; recheck after
workspace setup. Include explicit exporter settings and possible auto-discovery/
fallback destinations. The provided project endpoint/auth variables and this
fixture are **not** that approval; do not run eval/Doctor to find out where they
export. If the record or any resolved destination/capture/retention is unverified
or unauthorized, STOP and hand off to `foundry-observability`, then finish Step 8
with `telemetry destination/capture/retention unapproved`. Do not change existing
exporter configuration, disable required checks/sources or invent opt-out flags.

Only the synthetic row below may be sent in this smoke, and a synthetic row is not authorization
to export to an unknown destination. Doctor may capture finding text, workspace/
dataset context and shared-project signals: verify the approved sources and
LLM-assist scope cannot send sensitive or unauthorized shared payloads. Otherwise
STOP with the same reason; do not use a shared project as blanket consent.
Private logs and `env -u GITHUB_STEP_SUMMARY` only control local/summary output.
`AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=false` does not suppress native full
input/expected spans or Doctor finding exports. No verified supported blanket
native opt-out exists in this pinned path, so the smoke requires approved
telemetry; a hypothetical opt-out is not an alternative.

**Resolve the effective read/export scope before execution.** Discover the
actual linked App Insights component and its `WorkspaceResourceId`, then the
linked LAW's default and table retention, using the runbook's read-only metadata
steps. Do not guess names or execute Doctor to discover consent. This smoke
uses the component's `app_insights_resource_id`, not a broader workspace-wide
query. Native `lookback_days` has a minimum of **1 day**: its four
component-scoped aggregates cover requests/errors/duration, safety hits, tokens
and 429s. They have no per-agent/run filter; historical 24h aggregates are
**not fresh per-agent ingestion**. All four sources must remain enabled.
If that shared read scope or finding/judge/export scope is unacceptable, STOP.

**Separate retention surfaces.** An approved **7-day local raw retention** cap
is an operator deletion obligation, not service configuration. Observed service
table retention of **90 days** is illustrative, not a default or a guarantee;
record the actual component/LAW/table values and separately approved Responses
storage policy. In native 0.14.0 the Responses call omits `store=false` and drops
the returned **response ID** from persisted results. Agent deletion does **not**
prove stored responses deleted. Synthetic-only, retention-approved execution is
mandatory: if the owner requires zero storage or verified immediate deletion,
STOP before inference. No existing-conversation searches, fake cleanup claims,
interception/monkeypatch or package fork to recover IDs or alter the request.

---

## Step 2 - Create isolated local workspace and install the exact AgentOps pin

Create a per-run workspace with a short UUID suffix so parallel runs do not
collide. The workspace must be disposable and isolated from the repository
checkout; do not write AgentOps artifacts into the tracked repo.

Bash tool calls are stateless. Do NOT assume shell variables, the current
directory, or virtual-environment activation survive from one Bash call to the
next. Persist every file path and resolved value you need for later steps, and
invoke tools by persisted absolute path.

Suggested names:

- workspace: `<owner-private-root>/foundry-agentops-<uuid>`
- prompt agent: `ci-smoke-agentops-pa-<uuid>`

Inside that workspace:

1. create a virtual environment,
2. upgrade `pip`,
3. install **exactly** `agentops-accelerator[cockpit]==0.14.0` with that virtual
   environment's Python: Step 7 runs full Doctor, whose configured or
   auto-discovered Azure Monitor/resource sources require these optional SDKs.
   Do not install unrelated extras. Assert
   `importlib.metadata.version("agentops-accelerator") == "0.14.0"` and import
   `LogsQueryClient` from `azure.monitor.query`,
   `CognitiveServicesManagementClient` from `azure.mgmt.cognitiveservices`,
   `MonitorManagementClient` from `azure.mgmt.monitor`, and
   `AuthorizationManagementClient` from `azure.mgmt.authorization`.
   These are offline local prerequisite checks, not Azure health proof,
4. install `azure-identity~=1.25.3` in both native/helper environments, verify
   the resolved version and the single credential-name selector support.
   Before Step 3, inspect the pinned shared factory and verify its constructor
   chains offline (no token calls; simulate only the CLI-probe boundary)
   using SKILL.md's expected branches for all three selectors and both
   `exclude_developer_cli_credential=True` and `False`, including the factory's
   omitted default. Inspect nested credentials: with an unavailable CLI cache,
   explicit False retains the developer-CLI leg, True does not. Direct helpers
   omitting that keyword use the selector alone. Check the SDK azd subprocess
   helper's inherited empty directory with an inert process stand-in returning
   unavailable, never a real token/auth call. Construction/boundary tests do not
   prove permission or real authentication failure; authorization is the owner's gate.
   If the `foundry-prompt-agents` skill requires Azure SDK helpers for prompt
   agent creation, install only the bounded packages and versions that skill
   documents - do NOT widen or replace the `agentops-accelerator==0.14.0` pin,
5. define a stable absolute AgentOps executable path inside that workspace
   (for example `$WORKSPACE/.venv/bin/agentops`) and persist it together with
   the UUID, workspace path, and requested prompt-agent name so later Bash
   calls can reuse them without re-activating the virtual environment.

In the later snippets, `$AGENTOPS_BIN` denotes that persisted absolute executable
path, not a variable inherited from Step 2. Replace it with the absolute path
(quoted) in every Bash call, or explicitly reload it in that same call.
Likewise, `cd` to the persisted selected workspace path in the **same call**
before each command or relative artifact read/write; prior calls do not set cwd.

If the exact AgentOps install fails, finish with Step 8 using the literal
one-line reason `agentops install failed`. If an optional SDK import fails,
use `doctor local SDK prerequisite missing`; do not misclassify this as missing
telemetry or permissions, provision resources, or mutate RBAC. The upstream
pin's separate base-package import smoke remains unchanged.

---

## Step 3 - Create one temporary Foundry prompt agent (UUID-suffixed)

Using the `foundry-prompt-agents` contract, create exactly one temporary prompt
agent in the CI Foundry project at `$FOUNDRY_PROJECT_ENDPOINT`.

Requirements:

- The name MUST include the same short UUID suffix from Step 2.
- Use a chat-capable deployment already present in the project (the current CI
  baseline uses `gpt-5.4-mini`).
- Keep the instructions deterministic so one eval row can succeed repeatably.
  Recommended instructions: `Reply with exactly PASS and nothing else.`
- Capture the resolved agent name and version returned by Foundry and persist
  them for later steps.
- Use the parent-approved credential route from Step 0 without substitution.
  The direct SDK DefaultAzureCredential must inherit the same selector and
  isolated config paths as eval/Doctor, not an unrestricted developer chain.
  Its constructed credentials can differ from the native factory's default;
  the extra developer-CLI leg must remain unable to use a logged-in azd cache.

If agent creation fails, finish with Step 8 using the literal one-line reason
`prompt agent create failed`.

---

## Step 4 - Create the minimal valid AgentOps workspace contract

In the isolated workspace, create the smallest valid release-gate setup for
that exact prompt agent and exactly one dataset row.

You MAY use `agentops init --no-prompt` to scaffold `.agentops/` support files,
but the final checked config at the project root must be a minimal
`agentops.yaml` for the exact created agent and dataset path:

```yaml
version: 1
project_endpoint: "<value of $FOUNDRY_PROJECT_ENDPOINT>"
agent: "<resolved-agent-name>:<resolved-agent-version>"
dataset: .agentops/data/smoke.jsonl
```

Then write exactly one JSONL dataset row at `.agentops/data/smoke.jsonl`. Keep
it minimal and deterministic. A valid example is:

```json
{"id":"smoke-1","input":"Reply with exactly PASS and nothing else.","expected":"PASS"}
```

Do not add extra rows, Threadlight files, workflow files, or deployment
artifacts. If `agentops.yaml` or the dataset row cannot be created, finish with Step 8
using the literal one-line reason `agentops workspace contract failed`.

Also create `.agentops/agent.yaml` with these exact native fields, after resolving
and approving the component and source scopes in Step 1. This is a smoke-specific
1-day lookback, not a change to the native 7-day default. Leave checks/severity
unchanged and sources enabled; no generated workflow or optional governance suite.

```yaml
version: 1
lookback_days: 1
sources:
  results_history:
    enabled: true
  azure_monitor:
    enabled: true
    app_insights_resource_id: "<approved-linked-component-arm-id>"
  foundry_control:
    enabled: true
    project_endpoint: "<value of $FOUNDRY_PROJECT_ENDPOINT>"
    agent_ids: ["<resolved-agent-name>"]
  azure_resources:
    enabled: true
    subscription_id: "<approved-subscription-id>"
    resource_group: "<approved-resource-group>"
    cognitive_services_account: "<approved-foundry-account>"
```

`agent_ids` is a native Foundry-control field, **not** an Azure Monitor filter
or proof that every project-level rule listing is agent-scoped. Set the confirmed
`AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` in the effective environment too; the fixture's
`FOUNDRY_PROJECT_ENDPOINT` alias alone is not consumed by every native path.
The parent must also supply the approved **eval judge** deployment through
`AZURE_OPENAI_DEPLOYMENT` (or its native fallback
`AZURE_AI_MODEL_DEPLOYMENT_NAME`), and the approved **Doctor judge** through
`AZURE_AI_MODEL_DEPLOYMENT_NAME`. They need not equal the target agent's
deployment. Reconcile `AZURE_OPENAI_ENDPOINT`, when set, against the approved
account; when absent native eval derives it from the confirmed project endpoint.
Review inherited SDK API-key/connection-string settings and dotenv overrides
with the parent so they cannot substitute another credential/endpoint for the
selected route. Stop on conflicting/unapproved settings; do not silently
rewrite owner configuration, discover a different judge, or change evaluators.

---

## Step 5 - Run `$AGENTOPS_BIN eval analyze --format json`

From the isolated workspace, run:

```bash
$AGENTOPS_BIN eval analyze --format json
```

Requirements:

- the command must succeed,
- the JSON payload must parse cleanly,
- `version == 1` must hold.

Persist the JSON output for the run log or later inspection if helpful. If the
analyze command errors, the JSON is invalid, or `version != 1`, finish with
Step 8 using the literal one-line reason `eval analyze contract failed`.

---

## Step 6 - Run one eval and verify `.agentops/results/latest/results.json`

Run exactly one AgentOps evaluation for the temporary prompt agent, only after
rechecking the pre-execution telemetry approval against the completed workspace
and effective process environment. If missing or mismatched, STOP as in Step 1.

**Suppress the native CI summary export at the process boundary.** v0.14.0
automatically appends the full eval report (input/response/expected) when
`GITHUB_STEP_SUMMARY` is set. Run this block in the selected workspace, reloading
the absolute `$AGENTOPS_BIN` in the same Bash call as required by Step 2.
This does not stop network exporters or replace telemetry approval:

```bash
umask 077
mkdir -p .agentops/results
if env -u GITHUB_STEP_SUMMARY "$AGENTOPS_BIN" eval run \
    > .agentops/results/eval-command.log 2>&1; then
  eval_status=0
else
  eval_status=$?
fi
printf '%s\n' "$eval_status" > .agentops/results/eval-exit-code
exit "$eval_status"
```

Read the saved numeric exit code in the next call; the Bash action itself must
return the original eval status. Never use `|| true`, retry without suppression,
or treat a later successful file/summary write as the eval result. Unsetting is
child-process-only; do not overwrite or clear the runner's summary file.
Never print/`tee` the raw command log, report, results, or row payloads into the
transcript or job summary. Parse artifacts locally and report only sanitized,
metadata-only status/counts and approved provenance/restricted artifact pointers.
This applies even to the smoke's synthetic dataset; a summary must not copy the
native report. On errors report a sanitized reason, not the raw exception.

**Exit `2` is not proof of execution.** At v0.14.0,
[`exit_code_from` / `_summarize`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/pipeline/orchestrator.py)
also return `2` for captured invocation or evaluator failures. The native
[`RunResult`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/core/results.py)
contains `rows` (`RowResult`) and `rows[*].metrics` (`RowMetric`), not
`EvalRowResult` / `EvaluatorResult` objects. A metric may have `value: null`
without an error when unscored/not applicable; that is not execution proof.

Keep Step 4's minimal config and exact synthetic JSONL row unchanged. Its
[tagged default evaluator selection](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/core/evaluators.py)
is Coherence, Fluency, Similarity, ResponseCompleteness and average latency.
The checks below bind **that smoke profile**, not a general quality policy.
Do not change evaluators, thresholds, execution engine or response source to
make this check pass; the smoke requires target invocation, not dataset responses.

In the same isolated workspace, execute the **entire Python block below**
using the persisted workspace venv Python, passing exactly two positional
arguments: the **Step 3 persisted Foundry-returned name and version**. Load those
independently in this Bash call; never derive expected identity from the result
under test or substitute the configured target after a mismatch. Do not run with
Python optimization. This local check makes no Azure calls and does not change
the saved native exit code.

```python
# BEGIN AGENTOPS EVAL RESULT CHECK
import json
import math
from pathlib import Path
import sys

try:
    if not __debug__:
        raise ValueError("assertions required")
    name, agent_version = sys.argv[1:]
    assert name and name == name.strip() and ":" not in name
    assert agent_version and agent_version == agent_version.strip() and ":" not in agent_version
    status = Path(".agentops/results/eval-exit-code").read_text().strip()
    assert status in {"0", "2"}
    result = json.loads(Path(".agentops/results/latest/results.json").read_text())
    assert type(result["version"]) is int and result["version"] == 1

    target = result["target"]
    assert target["kind"] == "foundry_prompt"
    assert target["raw"] == f"{name}:{agent_version}"
    assert target["name"] == name and target["version"] == agent_version
    assert all(target.get(key) is None for key in ("protocol", "url", "deployment"))

    dataset = Path(".agentops/data/smoke.jsonl").resolve()
    assert isinstance(result["dataset_path"], str) and result["dataset_path"]
    assert Path(result["dataset_path"]).resolve() == dataset
    seed = {"id": "smoke-1", "input": "Reply with exactly PASS and nothing else.", "expected": "PASS"}
    assert [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()] == [seed]
    rows = result["rows"]
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert type(row["row_index"]) is int and row["row_index"] == 0
    assert row["input"] == seed["input"] and row["expected"] == seed["expected"]
    assert isinstance(row["response"], str) and row["response"].strip()
    assert row.get("error") is None

    defaults = [
        ("CoherenceEvaluator", "coherence", ">=", 3.0),
        ("FluencyEvaluator", "fluency", ">=", 3.0),
        ("SimilarityEvaluator", "similarity", ">=", 3.0),
        ("ResponseCompletenessEvaluator", "response_completeness", ">=", 3.0),
        ("avg_latency_seconds", "avg_latency_seconds", "<=", 30.0),
    ]
    assert result["evaluators"] == [evaluator for evaluator, *_ in defaults]
    metrics = row["metrics"]
    assert isinstance(metrics, list) and len(metrics) == len(defaults)
    scored = {}
    for metric in metrics:
        assert metric.get("error") is None
        value = metric["value"]
        assert type(value) in (int, float) and math.isfinite(value)
        assert metric["name"] not in scored
        scored[metric["name"]] = value
    assert set(scored) == {metric for _, metric, _, _ in defaults}
    aggregate = result["aggregate_metrics"]
    assert isinstance(aggregate, dict) and set(aggregate) == set(scored)
    for metric, value in aggregate.items():
        assert type(value) in (int, float) and math.isfinite(value)
        assert value == scored[metric]

    checks = result["thresholds"]
    assert isinstance(checks, list) and len(checks) == len(defaults)
    by_metric = {check["metric"]: check for check in checks}
    assert set(by_metric) == set(scored)
    passed_count = 0
    for _, metric, criteria, bound in defaults:
        check = by_metric[metric]
        value = aggregate[metric]
        passed = value >= bound if criteria == ">=" else value <= bound
        assert check["criteria"] == criteria and check["expected"] == f"{criteria}{bound:g}"
        assert check["actual"] == f"{value:g}"
        assert type(check["passed"]) is bool and check["passed"] == passed
        passed_count += int(passed)

    summary = result["summary"]
    for key, expected in (
        ("items_total", 1), ("items_passed_all", 1),
        ("thresholds_total", len(defaults)), ("thresholds_passed", passed_count),
    ):
        assert type(summary[key]) is int and summary[key] == expected
    for key, expected in (
        ("items_pass_rate", 1.0), ("threshold_pass_rate", passed_count / len(defaults)),
    ):
        assert type(summary[key]) in (int, float) and summary[key] == expected
    overall_passed = passed_count == len(defaults)
    assert type(summary["overall_passed"]) is bool
    assert summary["overall_passed"] == overall_passed
    assert status == ("0" if overall_passed else "2")
except Exception:
    raise SystemExit("eval results contract failed") from None

quality = "passed" if overall_passed else "failed"
print(f"eval execution verified; quality gate={quality}; native exit={status}")
# END AGENTOPS EVAL RESULT CHECK
```

Only after this check succeeds may a **threshold-only** native exit `2` count as
an executed smoke, never a passed quality gate or release approval. Exactly one
successful row, non-empty response and every expected metric scored without
errors are mandatory even for exit `0`. Native `items_passed_all` counts rows
without execution errors, **not** rows meeting every quality threshold, so it
must be `1` for both accepted cases. Optional native error fields may be absent
or `null`; any non-null error (even an empty string) fails.

Any failed assertion, missing/malformed artifact, unscored/skipped metric,
invocation/evaluator error or unexpected exit is a hard failure. Finish with
Step 8 using the literal one-line reason `eval results contract failed`; do not
dump exceptions, payloads or raw artifacts. Preserve Step 8's cleanup scope and
deterministic FAIL marker rather than continuing to Doctor or declaring success.

---

## Step 7 - Run `$AGENTOPS_BIN doctor --evidence-pack`

Before invoking Doctor, recheck the pre-execution telemetry approval, including
finding/exception capture, approved read-source scope and LLM-assist data flow.
An authorized read does not approve a telemetry write; STOP as in Step 1 on
any unresolved destination/capture/retention. From the same isolated workspace,
reload the absolute binary in this call and keep Doctor's stdout/stderr private:

```bash
umask 077
mkdir -p .agentops/agent
date -u '+%Y-%m-%dT%H:%M:%SZ' > .agentops/agent/doctor-started-at
if "$AGENTOPS_BIN" doctor --evidence-pack \
    > .agentops/agent/doctor-command.log 2>&1; then
  doctor_status=0
else
  doctor_status=$?
fi
printf '%s\n' "$doctor_status" > .agentops/agent/doctor-exit-code
date -u '+%Y-%m-%dT%H:%M:%SZ' > .agentops/agent/doctor-finished-at
exit "$doctor_status"
```

Read the numeric exit code and artifacts locally in the next call. Never dump
the log/finding payload into the transcript; report only sanitized status/gaps.
This capture protects local logs, not network exports.

Requirements:

- preserve Doctor's public exit-code contract: `2` is a real readiness gate
  failure, not a benign expected exit; `1` or unexpected exits fail execution,
- require the Step 2 exact `[cockpit]` installation and offline SDK imports
  before collecting Azure sources. Inspect source diagnostics; `not installed`
  is a local dependency failure, not a telemetry or permission gap. Unavailable
  telemetry/read permissions remain unverified; do not disable required sources,
  bypass preflight, or change infrastructure/RBAC to obtain a passing result,
- require fresh `.agentops/release/latest/evidence.json` and the newly appended
  `.agentops/agent/history.jsonl` record. This fresh workspace must have one
  Doctor record; do not reuse old latest files or rerun to overwrite a failure.

Execute the **entire block** below with the same venv Python and the same two
independently persisted Step 3 name/version arguments as Step 6. The block is
only this smoke's local assertion/report boundary, not a new evidence schema,
readiness engine or rewrite of native output. It returns **2 on Doctor's gate**,
1 on contract failure, and 0 only on a verified execution without that gate.
Missing/unknown optional coverage remains missing/unknown even on 0.

```python
# BEGIN AGENTOPS DOCTOR EVIDENCE CHECK
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

try:
    if not __debug__:
        raise ValueError("assertions required")
    name, agent_version = sys.argv[1:]
    assert name and agent_version and ":" not in name and ":" not in agent_version
    directory = Path(".agentops/agent")
    status = (directory / "doctor-exit-code").read_text().strip()
    assert status in {"0", "2"}
    started = datetime.fromisoformat((directory / "doctor-started-at").read_text().strip())
    finished = datetime.fromisoformat((directory / "doctor-finished-at").read_text().strip())
    assert started.tzinfo and finished.tzinfo and started <= finished
    evidence = json.loads(Path(".agentops/release/latest/evidence.json").read_text())
    assert type(evidence["version"]) is int and evidence["version"] == 1
    assert Path(evidence["workspace"]).resolve() == Path.cwd().resolve()
    assert evidence["target"] == f"{name}:{agent_version}"
    assert evidence["status"] in {"ready", "ready_with_warnings", "blocked"}
    records = [json.loads(line) for line in (directory / "history.jsonl").read_text().splitlines() if line.strip()]
    assert len(records) == 1
    history = records[0]
    for timestamp in (evidence["generated_at"], history["timestamp"]):
        value = datetime.fromisoformat(timestamp)
        assert value.tzinfo and started <= value <= finished + timedelta(seconds=1)
    assert set(history["sources_enabled"]) == {
        "results_history", "azure_monitor", "foundry_control", "azure_resources",
    }
    assert type(history["lookback_days"]) is int and history["lookback_days"] == 1
    doctor = evidence["doctor"]
    assert doctor["status"] == "ok"
    counts = doctor["counts"]
    assert set(counts) == {"critical", "warning", "info"}
    assert all(type(count) is int and count >= 0 for count in counts.values())
    assert history["findings_by_severity"] == counts
    assert doctor["findings_total"] == history["findings_total"] == sum(counts.values())
    findings = history["findings"]
    assert len(findings) == sum(counts.values())
    assert {level: sum(item["severity"] == level for item in findings) for level in counts} == counts
    maximum = next((level for level in ("critical", "warning", "info") if counts[level]), None)
    assert doctor["max_severity"] == history["max_severity"] == maximum
    assert status == ("2" if counts["critical"] else "0")
    checks = evidence["checks"]
    assert isinstance(checks, list) and checks
    by_name = {}
    for check in checks:
        assert isinstance(check["name"], str) and check["name"] not in by_name
        assert check["status"] in {"ready", "warning", "blocked", "unknown"}
        by_name[check["name"]] = check["status"]
    expected = "blocked" if counts["critical"] else "warning" if counts["warning"] else "ready"
    assert by_name["Doctor readiness"] == expected
    for field in ("blockers", "warnings", "ready"):
        assert isinstance(evidence[field], list)
    if counts["critical"]:
        assert evidence["status"] == "blocked" and evidence["blockers"]
    monitoring = evidence.get("monitoring", {})
    diagnostics = monitoring.get("diagnostics", {})
    aggregates_ok = (
        monitoring.get("status") == "ok"
        and diagnostics.get("enabled") is True
        and diagnostics.get("lookback_days") == 1
        and all(diagnostics.get(key) == "ok" for key in
                ("status", "safety_status", "token_status", "rate_limit_status"))
    )
    official = evidence.get("official_eval", {}).get("status", "missing")
    assert official in {"missing", "invalid", "ok", "unknown", "not_run"}
    observability = evidence.get("observability", {})
    observation_status = observability.get("status", "missing")
    assert observation_status in {"ok", "not_configured", "missing", "unknown"}
    multi_turn_rows = observability.get("multi_turn_rows")
    rubrics_count = observability.get("rubrics_count")
    assert multi_turn_rows is None or (type(multi_turn_rows) is int and multi_turn_rows >= 0)
    assert rubrics_count is None or (type(rubrics_count) is int and rubrics_count >= 0)
except Exception:
    raise SystemExit("doctor evidence contract failed") from None

gate = "blocked" if status == "2" else "not triggered"
print(f"doctor execution verified; readiness gate={gate}; native exit={status}")
print(f"findings: critical={counts['critical']}; warning={counts['warning']}; info={counts['info']}")
print(f"native evidence status={evidence['status']}; blockers={len(evidence['blockers'])}; warnings={len(evidence['warnings'])}")
print(f"native observability={by_name.get('Foundry observability', 'unknown')}; coverage=unverified")
print(f"observability detail={observation_status}; multi-turn rows={multi_turn_rows}; rubrics={rubrics_count}")
print(f"component aggregates={'queried' if aggregates_ok else 'unverified'}; not fresh per-agent ingestion")
print(f"official eval={official}; governance={by_name.get('Governance artifacts', 'unknown')}; landing zone={by_name.get('AI Landing Zone readiness', 'unknown')}")
raise SystemExit(int(status))
# END AGENTOPS DOCTOR EVIDENCE CHECK
```

The native **Foundry observability** check can say `ready` for an `auto` dataset
while `observability.status=not_configured`, `multi_turn_rows=0` and
`rubrics_count=0`. Preserve those raw values privately; **do not claim verified
coverage**. This single-turn smoke never certifies multi-turn/rubric coverage.
Likewise, native Runtime monitoring `ready` and nonzero historical component
counts only show a queryable source, not this new agent's ingestion. Inspect the
underlying diagnostics for all four queries; primary `ok` can hide secondary
errors. Unknown/missing governance, official-eval and landing-zone evidence
remain unknown/missing. Do not create files or run optional engines to fill gaps.

On checker exit 2, retain the evidence and native status. If the Step 6 execution
and Step 7 evidence assertions passed, perform Step 8 cleanup and write PASS for
skill execution. Prominently report `doctor readiness blocked` as readiness
**BLOCKED**, preserve native exit `2`, and report eval quality separately. A
critical local-auth-enabled finding is a real readiness blocker; never suppress
it, lower severity, disable sources, or fix shared infrastructure to pass the smoke.

On checker exit 1 write FAIL with `doctor evidence contract failed`. Eval execution
errors, malformed evidence and unscored metrics remain hard failures. A readiness
blocker alone is not a skill-execution failure, and an execution PASS is not a
quality pass or readiness approval.

---

## Step 8 - Teardown and deterministic marker contract

On success **or failure**, attempt cleanup of only assets actually created by
this run before writing the marker. Preserve failure/evidence bytes first in the
owner's restricted archive with the approved 7-day local raw retention/deletion
deadline and responsible owner; deleting a workspace is not evidence retention:

1. delete the temporary prompt agent created in Step 3 using the
   `foundry-prompt-agents` contract,
2. delete the isolated local workspace from Step 2.

Do not broaden cleanup scope beyond those two temporary assets. Never delete or
modify shared CI infrastructure, RBAC, APIM, networking, or GitHub policy
objects while cleaning up.

Bound cleanup to five minutes; report any leftovers privately for the existing
owner. Deleting the prompt agent/version and local workspace does **not** prove
stored responses or App Insights/LAW data deleted. Native 0.14.0 loses the
response ID and omits `store=false`; do not search existing conversations or
other agents' responses, invent deletion evidence, or patch/monkeypatch the
package. Service retention remains the separately approved obligation (90-day
table retention is only illustrative). If immediate deletion was required, this
run should have stopped before inference. Report the remaining privacy constraint,
not “all data cleaned”.

If either or both cleanup actions fail after the hard criteria succeeded, print
exactly one concise `NOTE:` line to stdout naming the leftover prompt agent
and/or workspace, still finish this step, and still write the byte-exact PASS
marker below. Only a prior hard-criteria failure may write the FAIL marker. Do
NOT compensate by touching shared CI infrastructure, RBAC, APIM, networking, or
GitHub policy objects.

### Final action (MANDATORY, deterministic)

Write exactly one marker file as your FINAL Bash action:

On execution success (Step 6 and Step 7 assertions pass, independently of eval
quality or Doctor readiness):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-agentops-smoke-result
```

On execution/evidence failure:

```bash
printf 'SMOKE_RESULT=FAIL %s\n' 'literal one-line reason here' > /tmp/foundry-agentops-smoke-result
```

Substitute the actual literal one-line reason directly into that final command.

The marker-file write is the single source of truth. Do not print the literal
marker token anywhere else in your reply.
