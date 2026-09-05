# Day-2 operations — one agent, exact v0.14.0

These are operator commands, **not commands executed by offline validation**.
Use the [support pin](upstream-pin.md) and [SKILL.md](../SKILL.md) prerequisites.
No Azure authentication, deployment or live test is authorized by this document
alone. Adopt the basic eval/Doctor loop without installing optional Red Team,
ASSERT or ACS integrations.

## Common execution and rollback rules

- Complete [credential isolation](../SKILL.md#pre-execution-credential-isolation)
  before any CLI/native/context call. The parent provides the approved cache
  paths and approved `AZURE_TOKEN_CREDENTIALS` selector, inherited unchanged
  by every Bash call. If a tool does not inherit them, explicitly reload the
  same owner-approved values in that call; never discover/copy global caches.
  The presence guards below do not certify identity or authorization. No login,
  account switching or credential-source substitution is allowed. For **all three**
  routes, including approved cached CLI, require private **fresh empty**
  `AZD_CONFIG_DIR` with **no login or token cache** copied into or created in it.
  Never mutate/repoint it or deliberately use azd during this execution.
  The native factory's `exclude_developer_cli_credential=False` retains
  `AzureDeveloperCliCredential` despite the selector. Its noninteractive attempt,
  if reached, inherits this same credential-empty directory and must fail
  unavailable, not fall back to global login. This constrains usable credentials,
  not the number of constructed objects; offline construction/boundary tests
  do not prove authentication. Hand operations requiring intentional azd use
  to the existing owner for separate approved execution, not an in-run login.
- Resolve the one-agent root, deployed target/version and environment first.
  Obtain required approvals, existing credentials, representative data and metric
  policy. Never change Citadel, RBAC, networks, protection or approvals.
- Substitute `<selected-agent-root>` with its absolute path and
  `<agentops-bin>` with the absolute executable from the verified
  `agentops-accelerator==0.14.0` virtual environment. Each Bash call explicitly
  changes cwd; neither activation, cwd nor variables survive between calls.
  Optional subprocess executables must resolve from the approved environment
  in that same call, never accidentally from another venv.
- Substitute `<run-id>` with a new operation identifier; the log directory
  `.agentops/operations/<run-id>/` is **our private logging convention**, not a
  native output. Keep it ignored/restricted. Refuse existing log filenames,
  symlinks, or paths escaping the root. Run only the chosen operation, not all
  blocks as a script.
- Before mutable outputs are replaced, archive/hash them with the provenance
  in [artifact-contract.md](artifact-contract.md). Serialize operations on this
  root. No blanket cleanup, no automatic baseline acceptance or threshold edits.
- Blocks leave the native command as the final operation, so its status survives
  even under `bash -e`. Capture any status immediately before further work;
  preserve exit **2** as a native gate failure. Other nonzero/unexpected exits
  stop processing. Never append a successful `echo`, use `|| true`, or pipe into
  a publisher that masks failure. Review artifacts even on zero.
- Local logs, JSON, reports and native errors must remain tenant-local. Never print or
  `tee` them into public transcripts, job summaries, issues or PR comments.
  Report sanitized status/counts/gaps and approved restricted pointers only.
  Cleanup cannot retract a remote inference or data upload; retention and
  incident handling belong to the existing owner.

## PRE-EXECUTION telemetry approval

**BEFORE invoking `eval run` or `doctor` (with or without `--evidence-pack`),
obtain explicit owner approval for the actual tenant-local telemetry destination,
payload capture and retention.** This is separate from approval to invoke the
agent or read telemetry. Record the approved resource/ingestion destination,
tenant, access boundary, captured data classes, retention and reviewer in the
existing restricted operations record. Reconcile that record with the effective
process environment, selected azd environment, `.agentops/.env`, root `.env`,
project attachment and installed exporter dependencies **before execution**.
Do not execute eval/Doctor to discover whether exporting is safe.

The tagged native initializer checks `APPLICATIONINSIGHTS_CONNECTION_STRING`
(then `AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING`) and `AGENTOPS_OTLP_ENDPOINT`.
Without a usable explicit destination, `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` can
trigger Foundry auto-discovery of an attached App Insights connection. Invalid
connection strings can fall through to discovery too. Review all reachable
fallback destinations, not just the first setting. Endpoint inference is **not
authorization** to export, even when the endpoint belongs to the selected project.

`env -u GITHUB_STEP_SUMMARY` blocks only the native eval report append.
Private stdout/stderr redirection and `umask 077` protect local logs, **not
network exports**. `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=false` is not a native
export/capture opt-out: AgentOps still attaches full input and expected strings
to eval-item spans (and an input excerpt to span names). Doctor emits finding
titles, summaries and recommendations; SDK instrumentation and exception spans
can capture additional content. Do not promise metadata-only telemetry from
summary suppression or that SDK flag. Approval must cover these payloads as well
as the destination; a metadata-only approval is insufficient.

**If any destination, payload capture, retention or authorization is unverified
or unauthorized: STOP before invoking the command and hand off to
`foundry-observability`.** There is no verified supported blanket opt-out in this
pinned native path. Do not invent flags, unset project variables to break
discovery, disable required Doctor sources, or remove exporters to evade review.
Only a supported opt-out verified against the exact native version and approved
by that owner could substitute for export approval; none is claimed here.
Preserve approved configuration and architecture: the observability owner
resolves instrumentation/export policy, Citadel owns access/routing, and the
workflow owner owns CI changes. This runbook does not change any of them.

The command-path audit at this tag is:

| Documented path | Initialization and approval boundary |
|---|---|
| `eval run` (candidate, baseline, retry; local/cloud/azd/auto engines) | `run_evaluation` calls `init_tracing` **before** selecting an engine, then flushes on exit. `execution: local` is not offline/no-export. Every invocation needs the approval above; cloud/azd publication needs separate approval too. |
| `doctor` (including `--evidence-pack`) | `_run_doctor_analyze` calls `init_tracing` and emits findings, then flushes. Read-source permissions, preflight and LLM-assist approval do not authorize these writes. |
| `eval analyze`, `eval promote-traces`, `workflow analyze`, `workflow generate`, `init --no-prompt` | These handlers do not call the native tracer initializer. CLI import still loads workspace dotenv. Init can persist settings; review the effective environment again before subsequent eval/Doctor. Generation does not authorize execution of its eval/Doctor steps. |
| `redteam run`, `assert run` | These wrapper handlers do not call that initializer; their SDKs/subprocesses can make independent inference, upload and telemetry calls. Obtain separate destination/capture/retention approval for those dependencies before running; local logs or summary suppression are no opt-out. |

Sources: [native tracing and payload attributes](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/utils/telemetry.py),
[Foundry discovery](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/utils/foundry_discovery.py),
[eval initializer](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/pipeline/orchestrator.py),
[CLI handlers and dotenv loading](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/cli/app.py).

### Effective scope, retention and Responses storage

Before execution, resolve the **actual linked App Insights component and LAW**,
not a guessed name or a telemetry sink inferred by running Doctor. Using the
already-approved route, inspect the selected project's App Insights connection
metadata (native resource discovery returns the first matching component ARM
target from project connections, not necessarily a designated default).
Resolve ambiguity with the owner. Reconcile any explicit exporter destinations/fallbacks
above separately; a read source and export destination need not be the same.
The existing observability owner supplies this metadata for empty-CLI routes;
do not log the CLI in just to run management commands.

For an approved CLI route only, these existing **read-only** commands are useful
after the credential gate. Redirect stdout/stderr to unique restricted files,
with `umask 077` in the selected root, and preserve each nonzero status. Do not
print connection strings or resource inventory in a public transcript:

| Inspection | Existing command (substitute approved placeholders) |
|---|---|
| Linked component metadata | `az resource show --ids "<component-arm-id>" --query '{WorkspaceResourceId:properties.WorkspaceResourceId,retentionInDays:properties.RetentionInDays,appId:properties.AppId}'` |
| Linked LAW metadata | `az resource show --ids "<linked-workspace-arm-id>" --query '{customerId:properties.customerId,retentionInDays:properties.retentionInDays}'` |
| Effective table retention | `az monitor log-analytics workspace table list --subscription "<linked-workspace-subscription>" --resource-group "<linked-workspace-rg>" --workspace-name "<linked-workspace-name>" --query '[].{name:name,retentionInDays:retentionInDays,totalRetentionInDays:totalRetentionInDays}'` |

Use the component's returned `WorkspaceResourceId` for the second/third rows,
including its actual subscription/resource group; authorize it separately if it
differs from the project. Resolve inherited/default retention with the owner;
unknown values are not a deletion guarantee. See
[table retention](https://learn.microsoft.com/azure/azure-monitor/logs/data-retention-configure#get-retention-settings-by-table).
Do not change retention, purge shared tables, fetch workspace keys or broaden access.

The exact [Doctor config](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/agent/config.py)
has root `lookback_days: 7` by default, minimum **1 day**, and
`sources.azure_monitor.app_insights_resource_id` /
`sources.azure_monitor.log_analytics_workspace_id`. The latter is the LAW
**customerId**, not its ARM ID; if both are set the workspace query wins and
can broaden scope. The smoke uses the approved component ARM ID only, with
`lookback_days: 1`, leaving all four sources enabled. Do not add invented
`agent_id`, run-ID, minute-window or KQL override fields.

The pinned [collector](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/agent/sources/azure_monitor.py)
performs **four component-scoped aggregates** on that route:
requests/errors/average and p95 duration, content-filter safety hits, token usage,
and dependency 429 hits. They cover the whole selected component's lookback,
**not fresh per-agent ingestion**. Requests/dependencies/traces may include
unrelated agents. There is no native per-agent/run filter; `foundry_control.agent_ids`
does not scope Monitor. A historical 24h nonzero count or `status: ok` proves at
most queryability. Inspect `safety_status`, `token_status`, `rate_limit_status`
as well as primary status: secondary queries can fail while primary stays `ok`.
Fresh correlated ingestion verification belongs to `foundry-observability`,
with separate authorized scope/budget; do not duplicate its telemetry engine.
If these shared reads or Doctor's findings/judge payloads exceed consent, **STOP**.

**Retention has three separate surfaces:**

- **Local:** an approved **7-day local raw retention** cap covers command logs,
  result/report/evidence files and their private archive. Record a deletion date,
  responsible owner and actual cleanup outcome; without deletion automation,
  a deadline is an obligation, not proof that deletion occurred.
- **Telemetry service:** a service table observed at **90 days** is illustrative
  only, not a universal/native default and not this run's local retention. Record
  actual component, LAW default, table `retentionInDays` and
  `totalRetentionInDays`; table/archive settings can differ. Local deletion
  cannot retract exported spans, finding text or judge calls.
- **Responses storage:** [native prompt invocation](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/pipeline/invocations.py)
  posts `/openai/v1/responses` without `store=false`. `_run_responses_tool_loop`
  returns text/tool calls/elapsed time, **not the response ID**; the final
  `InvocationResult`/persisted rows do not retain that ID. Deleting the prompt
  agent/version therefore does **not** prove stored responses deleted. Telemetry
  table retention does not establish Responses retention.

Use synthetic-only, retention-approved smoke inputs and obtain explicit
acceptance of service storage and this cleanup limitation **before inference**.
If zero storage, a shorter unverified retention period or provable immediate
response deletion is required, **STOP** and hand off to the existing
privacy/observability owner and upstream AgentOps. No existing-conversation
searches, guessed IDs, fake cleanup claims, request interception, monkeypatch
or package fork. This skill must not implement a parallel invocation engine.

## Manual equivalent and outer executor diagnosis

This is the same fixture contract, not a new wrapper or a second test product:

1. The owner separately prepares a **new private** CLI config containing only
   the approved cached **user** (or provides the CI service-principal/workload
   route), and a new private credential-empty azd config. Deleted prior caches
   cannot be reused. Follow tenant isolation before any account selection.
   Set the stable `AZURE_CONFIG_DIR`, `AZD_CONFIG_DIR` and
   `AZURE_TOKEN_CREDENTIALS` in the parent and inherit them into every call.
   For `cached-user`, leave `AZURE_CLIENT_ID` unset: never invent a CLI public
   application ID or use `N/A`. For `ci-cli`, preserve CI's real client ID;
   environment/workload routes require their complete principal credentials.
2. For manual cached-user only, read approved isolated state with
   `az account show --query '{tenant:tenantId,subscription:id,type:user.type}'`
   into a private file. Compare tenant and `allowed_subscriptions` membership
   with the independent approval record and require user type; mismatch means
   STOP. Do not inspect global caches or switch accounts. CI keeps its existing
   authoritative context and show-don't-assert contract; this manual check is
   not added to CI.
3. From the selected root read the fixture and linked skills directly. Execute
   the **whole Step 0 Python assertion block** with `python3 - "<route>"` and
   that block on stdin using a quoted heredoc. Use only one of `cached-user`,
   `ci-cli`, `environment`, `workload` from the parent's approval. This check
   never authenticates. Complete telemetry/retention discovery and approval
   before resource creation. Keep the confirmed native project endpoint alias.
4. Follow fixture Steps 2–5 using the exact install and the existing
   `foundry-prompt-agents` create/delete commands, not a helper product or a
   replacement evaluator. Persist the Foundry-returned name/version independently.
   Use one new private workspace, one synthetic row, the default five metrics,
   and the approved native `.agentops/agent.yaml` 1-day/component-scoped config.
   Provide the approved eval judge as `AZURE_OPENAI_DEPLOYMENT` (fallback
   `AZURE_AI_MODEL_DEPLOYMENT_NAME`) and Doctor judge as
   `AZURE_AI_MODEL_DEPLOYMENT_NAME`; verify any `AZURE_OPENAI_ENDPOINT` override.
   These existing native inputs are not necessarily the target deployment.
   Reconcile inherited SDK API-key/connection-string settings with the single
   approved route before launch; conflicting settings mean STOP, not substitution.
5. Execute Step 6's native eval capture block once. In the next call use
   `"<workspace-python>" - "<created-name>" "<created-version>"` with the **entire
   Step 6 Python assertion block** on stdin. Do not derive those arguments from
   results. Retain the native exit separately from the checker and quality gate.
6. Execute Step 7's Doctor capture block once, then use the same Python/arguments
   with the **entire Step 7 Python assertion block** on stdin. Keep the
   start/finish files and new history record. Doctor exit **2 stays blocked**;
   do not turn successful JSON parsing into readiness. Preserve evidence and
   perform Step 8 scoped cleanup/marker even on failure.

An outer Copilot **skill-loading stall** before workspace creation or any native
operation is an orchestration failure: record the last completed action, timeout
and lack of native artifacts privately. If **no native command** ran, neither
native failure nor native success has been observed. Stop only that identified
outer process; do not invoke Copilot recursively, pollute its transcript, or
re-run native work to diagnose skill loading. A separately authorized **manual
equivalent** can execute the sequence above; label it manual, with its actual
identity route, fixture/input hashes and native exits. It does not prove the
outer fixture orchestration or unchanged CI service-principal route passed.

## 1. Analyze evaluation prerequisites

**Prerequisites:** reviewed `agentops.yaml` and referenced dataset inside the
root. This is local analysis, not a credential or schema-completeness test.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
"<agentops-bin>" eval analyze --format json \
  > ".agentops/operations/<run-id>/eval-analysis.json" 2>&1
```

**Options/artifact:** `--dir` defaults to `.`; `--format` accepts text/markdown/json;
`--out` optionally writes analysis (not eval results). The redirected output
above must parse as JSON with `version == 1`. Require `config_status` and
`dataset_status` ready for this eval path; review `target_kind`, warnings,
`requires_copilot_adaptation`, engine and proposed commands. Missing, invalid,
incomplete or observability-only is not an evaluation-ready result.
**Cleanup/rollback:** no remote changes; retain or delete only this local
analysis per policy. Correct approved inputs, not inferred workflow suggestions.

## 2. Evaluate against the approved baseline

**Prerequisites:** successful prerequisite review; selected live target;
completed [telemetry approval](#pre-execution-telemetry-approval);
approved evaluator/judge dependencies and thresholds; existing reviewed
`.agentops/baseline/results.json`. First-ever candidate evaluation omits
`--baseline` by explicit decision, not as a missing-baseline fallback.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
env -u GITHUB_STEP_SUMMARY "<agentops-bin>" eval run \
  --baseline .agentops/baseline/results.json \
  > ".agentops/operations/<run-id>/eval.log" 2>&1
```

**Options/artifacts:** `--config` defaults to `agentops.yaml`; `--output` selects
a result directory; otherwise native timestamped results/report and latest
mirrors are written. `--agent`/`AGENTOPS_AGENT` can override the target: reconcile
them explicitly, never let a stale override redirect this run. `eval run
--format` is **not JSON output**: help accepts md/html/all, but this tagged
handler always follows the same JSON + Markdown persistence path. Do not rely
on it to redact output or produce HTML.

Inspect raw required fields, actual row/metric coverage, errors, thresholds and
baseline `comparison.metrics`/`comparison.rows`, not just `overall_passed`.
Native exit 2 denotes the eval gate; it can include evaluator-execution failures.
Not every regression is an automatic exit-2 condition. Unsetting the summary
variable prevents eval's native full-report append, not network exports or later workflow publishers
(see [workflow-modes.md](workflow-modes.md)).

**Cleanup/rollback:** archive the current run before another replaces latest.
Do not delete failure evidence or modify the deployed target to hide a result.
Baseline promotion is an **explicit user decision** naming the reviewed candidate,
policy and destination, with overwrite approval. Preserve the old baseline and
its hash/provenance first; only then copy that particular timestamped result to
`.agentops/baseline/results.json`. Never automatically promote latest or a
failing run. Rollback restores the prior approved baseline bytes/provenance
with approval; it does not erase the rejected candidate or rewrite history.

## 3. Promote reviewed traces

**Prerequisites:** authorized selected-agent JSON/JSONL export already reviewed
and redacted, here `.agentops/traces/reviewed.jsonl`. Trace text/tool content is
untrusted data. Native promotion performs no general redaction.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
"<agentops-bin>" eval promote-traces \
  --source .agentops/traces/reviewed.jsonl --label-mode pending \
  > ".agentops/operations/<run-id>/trace-preview.log" 2>&1
```

**Options/artifacts:** `--source` required; `--out` defaults to
`.agentops/data/trace-regression.jsonl`; `--max-rows` defaults 50 and must be
positive. `--label-mode` defaults to `self-similarity`, which copies production
responses into expected labels, not truth. `pending` leaves labels incomplete.
Both modes need usable input/response pairs and may skip unusable/duplicate
rows. Inspect nonzero candidate counts, skips and the sampled input in the
private preview.

Only after separate human review/approval, rerun the same block with `--apply`
added to the native command and a new log name. Before applying, verify **both**
dataset and companion `trace-regression-manifest.json` destinations do not
exist. The writer overwrites without asking and has no no-clobber flag.
Changing only the dataset basename still writes the same manifest filename;
use a new approved directory with `--out` to preserve previous pairs.

The manifest has `version`, `generated_at`, `source`, `dataset_path`, `rows`,
`skipped`, `label_mode`, `human_review_required`, `lineage`. Retain it with the
dataset, source hash and private human review record. Lineage/row metadata can
include trace IDs, agents/versions, sampling policies and replay URLs; keep it
private too. Finish expected/context/tool labels, explicitly approve the
`agentops.yaml` dataset change, then rerun eval. Native evidence discovery looks
at the default manifest path; a custom destination needs a documented private
provenance handoff, not a fabricated native "ready" field.

**Cleanup/rollback:** remove only the newly rejected pair/logs under retention
policy; restore the approved dataset reference with approval. Preserve source
and earlier pairs. Trace promotion never authorizes baseline promotion.

## 4. Doctor and release evidence

**Prerequisites:** selected results/history and reviewed optional
`.agentops/agent.yaml`; existing authorized read access to configured sources.
Complete [telemetry approval](#pre-execution-telemetry-approval) before Doctor:
reading an authorized source does not authorize exporting findings to it.
For configured or inferred Azure Monitor/resource sources use the same venv's
exact `[cockpit]` extra and four offline SDK import checks in
[SKILL.md](../SKILL.md), not an unpinned install or RBAC repair.
Review `sources.results_history`, `azure_monitor`, `foundry_control`,
`azure_resources`, lookback and check configuration. Sources default enabled.
Doctor's LLM-assist checks also default enabled and may call a judge with
workspace/dataset context; approve that data flow and cost beforehand.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
"<agentops-bin>" doctor --evidence-pack \
  > ".agentops/operations/<run-id>/doctor.log" 2>&1
```

**Options/artifacts:** `--workspace` defaults to `.`; Doctor `--config` selects
`agent.yaml`, **not** root eval YAML. `--out` selects the report;
`--evidence-out` selects the evidence directory; `--lookback-days` changes the
telemetry window. Default severity floor is `critical`; `--severity-fail`
accepts info/warning/critical/none, but do not lower the agreed gate.
Evidence packs require full scope, not `--categories`; do not bypass preflight
or exclude required rules to make a run green.

Require report, newly appended history record and
`.agentops/release/latest/evidence.json` / `evidence.md`. Check raw version 1,
timestamps, target association, checks/blockers/warnings, source diagnostics and
actual coverage. Native history append is best-effort, so verify it happened.
Preflight errors normally stop with 1; source collectors can instead fail open
with `skipped`, `disabled`, error or cannot-verify diagnostics while analysis
continues. Missing telemetry/read permissions and disabled required sources
are **unverified**, never healthy. Local missing-SDK diagnostics are dependency
gaps. Record intentional opt-outs as reviewed exceptions, not successful checks.

Doctor exit 2 is based on finding severity. Evidence `blocked` does not itself
introduce an exit status; exit 0 can accompany gaps. Shared-project signals and
enabled-source lists do not prove the selected agent was observed.
Keep execution, eval quality and Doctor readiness separate. A critical
local-auth-enabled finding is a real readiness blocker even after eval exit 0;
retain Doctor exit 2 and hand it to the posture owner, not a source-disable or
shared-resource fix. The fixture's Step 7 executable check preserves that gate.
Native `Foundry observability=ready` with underlying `not_configured`, zero
multi-turn rows and zero rubrics is **not verified coverage**. Missing official
eval, unknown governance and undetected landing-zone evidence stay gaps; preserve
the raw statuses and do not generate artifacts or optional tests to fill them.
**Cleanup/rollback:** archive report, history slice, evidence pair and associated
eval; retain failures privately. Revert only approved configuration changes with
owner approval. Do not truncate history, disable telemetry or alter infrastructure.

## 5. Analyze workflow fit

**Prerequisites:** one selected root and known ownership. This local operation
does not create workflows or change permissions.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
"<agentops-bin>" workflow analyze --format json \
  > ".agentops/operations/<run-id>/workflow-analysis.json" 2>&1
```

**Options/artifact:** `--dir`, `--format`, `--out`; inspect version, directory,
classification, warnings, proposed engine/stages and adaptation requirements as
specified in [workflow-modes.md](workflow-modes.md). Do not execute recommendations.
**Cleanup/rollback:** only a private analysis file. Threadlight stays config/
prerequisites-only with `threadlight-cicd` ownership. Standalone generation is a
separate user-approved step; do not use missing workflows as implicit approval.

## 6. Optional Red Team operation

**Prerequisites:** explicit authorized scan scope/budget; compatible, separately
approved `azure-ai-evaluation[redteam]` dependencies; `RedTeam`, `AttackStrategy`,
`RiskCategory` imports; approved endpoint/credential/judge setup. Keep the
AgentOps distribution at 0.14.0. This reference does not claim a tested optional
SDK version or authorize unbounded installs. Set the confirmed
`AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` for the runner; root eval `project_endpoint`
alone is not its project-env contract.

Configure `redteam` in `agentops.yaml`: `target`, `risk_categories`,
`attack_strategies`, positive `num_objectives`, `output_path` and explicit
`fail_on_attack_success_rate`. Native defaults are four safety categories,
base64/rot13/morse, 10 objectives per category and threshold 0.2; they are not
universal policy. Review target derivation/HTTP mappings and secrets privately.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
env -u GITHUB_STEP_SUMMARY "<agentops-bin>" redteam run \
  > ".agentops/operations/<run-id>/redteam.log" 2>&1
```

**Options/artifacts:** `--config`, `--target` (`model:<deployment>`,
`agent:<name>:<version>`, `endpoint:<url>`), `--num-objectives`, `--output`.
Prefer reviewed config; overrides must match it or fingerprint checks can fail.
Risk categories/strategies are config fields, not invented CLI flags.
Keep gate enabled; no `--no-gate` or null threshold to hide violations.
Default normalized/raw destinations and caveats are in
[artifact-contract.md](artifact-contract.md). A custom `--output` is not
automatically persisted into config for later Doctor discovery.

Inspect positive actual attempts, category/strategy coverage, counts/rate,
timestamp and fingerprint; an empty parsed scan can normalize to zero ASR.
Exit 2 means ASR exceeds the configured threshold; other errors stop.
Native SDK fallback can drop `skip_upload`, so inspect dependency behavior and
authorized storage before scanning. **Cleanup/rollback:** archive evidence before
replacement; clean only identified local raw outputs under retention policy.
No target, mitigation, Citadel or gate changes as cleanup; remote scan artifacts
remain subject to their owner's retention. Suppression here avoids automatic
metadata summaries too; native raw console output still needs the private log.

## 7. Optional ASSERT operation; ACS evidence only

**Prerequisites:** separately approved `assert-ai` executable/dependencies,
reviewed ASSERT eval configuration/spec, authorized target/judges and
credentials. Keep AgentOps exactly pinned. Root `assert` settings are
`config`, `results_dir`, `suite`, `run_id`, `fail_on_violations`, `env`;
secrets do not belong in `env` YAML. The default results directory is
`artifacts/results`. Choose a fresh run identity in the ASSERT configuration.

The native resolver tries `shutil.which("assert-ai")` **first**. An absolute
AgentOps executable does not constrain inherited PATH; setting `assert.env.PATH`
is too late to fix resolution. Use the same verified environment for both tools:
substitute `<approved-env-bin>` with its absolute, non-symlink `bin` directory
(the directory containing `<agentops-bin>`). Before running, review the installed
`assert-ai` launcher, its shebang/interpreter, package provenance and approved
dependency versions using that environment's Python. An interpreter symlink must
resolve to the approved base interpreter while retaining the selected venv's
`sys.prefix`; verify `assert_ai` imports from that venv, not the workspace or an
inherited `PYTHONPATH`. Unverified launchers/import origins mean STOP.

The block exports a controlled PATH and verifies its selected launcher **in the
same invocation** before AgentOps starts. `/usr/bin:/bin` are only for reviewed
system tools; never append the inherited PATH. Review dotenv and `assert.env`
for PATH/Python overrides as well; stop on conflicting/unapproved values rather
than silently rewriting owner configuration. No fallback to a different
executable, `python -m assert_ai`, or import-based runner is authorized here.
Native fallback searches beside the **resolved** `sys.executable`, which can be
the base Python directory rather than the venv; the checks deliberately stop
before that fallback. If the approved launcher is absent, repair that environment
with its owner, then repeat the checks.

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
(
  export PATH="<approved-env-bin>:/usr/bin:/bin" &&
  test "$(command -v assert-ai)" = "<approved-env-bin>/assert-ai" &&
  test ! -L "<approved-env-bin>/assert-ai" &&
  env -u GITHUB_STEP_SUMMARY "<agentops-bin>" assert run
) > ".agentops/operations/<run-id>/assert.log" 2>&1
```

**Options/artifacts:** `--config` (AgentOps YAML), `--assert-config` (ASSERT YAML),
`--results-dir`, `--suite`, `--run-id`. Suite/run selectors help discover outputs;
the wrapper does not pass those selectors as ASSERT subprocess flags. They must
match the actual ASSERT config/run, not silently select old results. Normalized
`.agentops/assert/latest.json` records suite/run paths, metrics,
`dimension_summary`, total/passed/failed/skipped cases, `pass_rate`,
`has_violations`, `exit_code`, `normalized_path`. Raw `metrics.json` and
`scores.jsonl` reside under `<results_dir>/<suite>/<run>/`.

By default the wrapper requests fresh inference (`--force-stage inference`);
`--cached` reuses prior rows and is not fresh evidence. No `--no-gate` or
`fail_on_violations: false` to disguise policy failures. Exit 2 gates detected
violations. **Important native caveat:** the subprocess's nonzero exit is saved
in normalized `exit_code` but is not necessarily propagated by the AgentOps
CLI if it can discover results and finds no violations. Require subprocess
success, fresh matching outputs, positive scored cases and adequate dimensions;
zero/all-skipped/stale outputs are unverified even on CLI exit 0.

**Cleanup/rollback:** archive the normalized file plus the exact private raw
run directory before replacement; remove only newly generated outputs by
retention policy. Do not rewrite specifications or runtime governance to pass.
Existing `assert_path`, `acs_path`, `redteam_path` can reference reviewed
artifacts; ACS contract presence is **not enforcement proof**, and this runbook
provides no ACS execution/provisioning command. Reuse compatible owner evidence
per [threadlight-boundary.md](threadlight-boundary.md), without duplicate tests.

## Tagged implementation map

| Surface | Authoritative v0.14.0 source |
|---|---|
| All command names/options, status propagation, summary writes | [cli/app.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/cli/app.py) |
| Flat config and optional runner blocks | [core/agentops_config.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/core/agentops_config.py) |
| Doctor sources/check defaults | [agent/config.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/agent/config.py) |
| Eval analysis / trace promotion | [eval_analysis.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/eval_analysis.py), [trace_promotion.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/trace_promotion.py) |
| Optional runners and their limits | [redteam_runner.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/redteam_runner.py), [assert_runner.py](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/assert_runner.py) |
