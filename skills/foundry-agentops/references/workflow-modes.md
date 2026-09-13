# Workflow ownership and safe native generation

Use only the [exact upstream pin](upstream-pin.md). This reference describes
configuration/approval contracts, not a custom pipeline implementation.
Complete [credential isolation](../SKILL.md#pre-execution-credential-isolation)
before any CLI/native analysis, generation or runner execution. Presence guards
below require the same parent-approved paths/selector in every Bash call; they
do not prove authorization. Never inherit arbitrary global credentials.

## Select scope and owner before analysis

Follow [SKILL.md](../SKILL.md)'s explicit-root/unique-marker selection first.
Multiple agent roots or targets require an explicit choice. All reads/writes
stay inside that selected root; no repository-wide recursive analysis across
sibling agents. `--dir` sets the native analysis/generation root, not an
automatically inferred CI working directory.

Inspect `specs/manifest.json` or existing CI conventions identifying a
Threadlight-managed project. These are **ownership hints**, not permission to
edit the manifest and not a native AgentOps mode flag. A generic manifest may
need owner confirmation. Also honor known Threadlight ownership when the marker
is absent. Resolve ambiguity before writing; never infer standalone permission
from a native recommendation.

| Mode | Allowed action | Final workflow owner |
|---|---|---|
| Threadlight | AgentOps configuration, approved native operations/evidence, prerequisite and gap handoff; **no `workflow generate`**, new pipeline, or competing manifest | `threadlight-cicd` |
| Standalone | Read-only analysis first; generate only after separate approval of exact platform, files, triggers, gates, and scope | Existing repository/pipeline owner |
| Unknown/shared roots | Stop generation; resolve owner and one-agent root | Existing owner |

Native [workflow analysis](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/workflow_analysis.py)
is local/heuristic. Its `manifest.json` landing-zone detection is **not**
Threadlight's `specs/manifest.json` contract. Its recommendations can include
deployment/adaptation; they are untrusted suggestions, not authorization.

## Analyze, review, approve

Use the private execution block for `agentops workflow analyze --format json` in
[day2-runbook.md](day2-runbook.md). Native options:

| Command/option | v0.14.0 contract |
|---|---|
| `workflow analyze --dir <root>` | Defaults to `.`; analyzes that local root. |
| `--format json` (`-f`) | `text` (default), `markdown`, `json`. |
| `--out <file>` (`-o`) | Optional analysis file, otherwise stdout; no workflow generated. Existing output can be overwritten. |

Require raw JSON `version == 1`, correct `directory`, and review `classification`,
`recommended_deploy_mode`, `recommended_eval_runner`, `deployment_strategy`,
`eval_strategy`, `complexity`, `requires_copilot_adaptation`, `signals`, `warnings`,
`recommended_commands`, `stages` and `next_steps`. No result proves credentials,
network access, branch protection or approval configuration. Record missing
prerequisites; never auto-run recommended commands.

For a nested agent root, inspect where CI actually checks out source. The native
generator writes workflows **under `--dir`**; a nested `.github/workflows` will
not become a repository-root GitHub Actions workflow. There is no native
`--working-directory` switch. Have the owner explicitly review run-step cwd,
`--config`/Doctor workspace, dataset/baseline paths and artifact paths against the
selected root (GitHub `working-directory` / Azure DevOps `workingDirectory` where
appropriate). Do not generate in the parent repo to evade multi-root isolation.
If relocation/adaptation is needed, hand it off; this skill authors no substitute
pipeline. A config-path override alone does not rebase every step or artifact.

## Standalone-only generation after user approval

[Tagged CLI options](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/cli/app.py)
and [generator](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/cicd.py):

| Option | Accepted values / default |
|---|---|
| `--platform` (`-p`) | `github` (default), `azure-devops` |
| `--kinds` | Comma-separated `pr,dev,qa,prod,doctor`; empty defaults to `pr,dev,qa,prod`; legacy `watchdog` aliases `doctor` |
| `--deploy-mode` | `auto` (default), `azd`, `prompt-agent`, `placeholder`; auto prefers azd with `azure.yaml`, otherwise prompt-agent for a prompt target |
| `--doctor-gate` | `critical` (default), `warning`, `none`; affects the PR template only; deploy Doctor gates remain critical |
| `--dir` | Output/detection root, default `.` |
| `--force` | Overwrites existing files; prohibited in this runbook |

After approval, substitute `<selected-agent-root>` and `<agentops-bin>` with the
verified absolute paths; substitute `<platform>` with **one** approved literal
(`github` or `azure-devops`) and `<run-id>` with a new local log directory name.
This narrow example requests only a PR gate, not deployment stages. It remains
**unsafe to submit or run until the generated files pass the review below**:

```bash
cd "<selected-agent-root>" &&
: "${AZURE_CONFIG_DIR:?owner-approved isolation required}" "${AZD_CONFIG_DIR:?credential-empty isolation required}" "${AZURE_TOKEN_CREDENTIALS:?approved selector required}" &&
umask 077 &&
mkdir -p ".agentops/operations/<run-id>" &&
"<agentops-bin>" workflow generate --dir . --platform "<platform>" \
  --kinds pr --deploy-mode placeholder --doctor-gate critical \
  > ".agentops/operations/<run-id>/workflow-generate.log" 2>&1
```

GitHub writes `.github/workflows/agentops-pr.yml`; Azure DevOps writes
`.azuredevops/pipelines/agentops-pr.yml`. Other kinds use
`agentops-deploy-dev.yml`, `agentops-deploy-qa.yml`, `agentops-deploy-prod.yml`,
`agentops-doctor.yml` in the same platform directory. Without `--force`, existing
files are **skipped**, not validated or upgraded. Check created/skipped paths
and diff; exit 0 may mean nothing changed. Approval to generate missing files
never authorizes overwriting existing workflows.

`placeholder` limits the deploy-template choice, **not the eval runner**:
the latter is selected independently from configuration/support analysis and can
be local, cloud, azd or official evaluation. Inspect the resulting commands,
candidate target/version and data publication path; do not silently change the
approved engine to make a template run.

## Mandatory review before submission or execution

1. **Exact support:** a clean installed 0.14.0 release already generates
   `==0.14.0` through `_agentops_install_spec`; it is incorrect to say its core
   package default is always unpinned. Development/invalid-version fallbacks
   can point at upstream main; optional ASSERT/Red Team installs and other
   dependencies can be unpinned. The [support pin](upstream-pin.md) is authoritative:
   reject moving refs/unreviewed versions, resolve optional dependency locks
   with their owner, and verify Doctor's required extras.
2. **Payload suppression is more than one environment variable.** Unset
   `GITHUB_STEP_SUMMARY` on **every native eval process**, including baseline
   invocations, and capture raw stdout/stderr privately without `tee`.
   The native [GitHub PR template](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/templates/workflows/agentops-pr.yml)
   separately concatenates native reports into the step summary, posts a PR
   comment, and uploads raw artifacts. Suppression at the eval process does
   **not** stop those later publishers. The
   [Azure DevOps template](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/templates/pipelines/azuredevops/agentops-pr.yml)
   also publishes results/report artifacts. Block submission until the owner
   removes/replaces all raw publishers with approved metadata-only summaries
   and restricted tenant-local retention. Inspect every selected template, not
   only PR. Never broaden repository visibility or artifact access to make
   delivery convenient.
   These controls affect local logs/reports and downstream publication, **not
   network exports**. BEFORE any generated eval/Doctor step runs, including
   candidate/baseline runs and retries, require the
   [PRE-EXECUTION telemetry approval](day2-runbook.md#pre-execution-telemetry-approval)
   for the effective runner environment and native auto-discovery/fallback paths.
   `foundry-observability` owns destination, payload capture and retention
   approval; inference access or an attached App Insights resource is not that
   approval. Unknown/unauthorized export means STOP and handoff, not execution
   with only `GITHUB_STEP_SUMMARY` unset or the SDK GenAI tracing flag false.
   Keep existing workflow/config owners; this skill does not install a filter
   or rewrite exporter settings.
3. **Policy/scope:** verify existing identities, secret-variable names, endpoint
   routing, runner network, permissions, triggers, target version, evaluator
   coverage, baseline provenance and Doctor severity. No RBAC, Citadel/APIM,
   branch-protection, environment-approval or network mutations. Do not create
   service connections or bypass access paths here.
   Establish process-local `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR`
   **before authentication** and before any CLI/native call; inherit unchanged
   through every job step, helper and retry. With a runner-provisioned approved
   CLI cache, select `AZURE_TOKEN_CREDENTIALS=AzureCliCredential`; for approved
   environment/federated authentication use an empty isolated CLI config plus
   the single matching selector and `azure-identity~=1.25.3` from SKILL.md.
   AgentOps's shared factory prefers available CLI cache over environment
   credentials; env secrets alone do not select the native identity.
   For **all three** routes, even approved CLI mode, provide private **fresh empty**
   `AZD_CONFIG_DIR` with **no login or token cache** copied into or created in it.
   Do not mutate/repoint it or deliberately run azd during this execution. The
   native `exclude_developer_cli_credential=False` retains
   `AzureDeveloperCliCredential` beside the selected source; constructors need
   not match direct SDK chains. That leg can attempt azd noninteractively, but
   must inherit the same credential-empty directory and fail unavailable rather
   than use a global login. Offline boundary tests do not prove authentication.
   Deployment stages that need intentional azd use belong to a separate
   owner-approved execution, not a login/cache mutation inside this gate.
   The CI runner context remains authoritative: preserve show-don't-assert,
   not new subscription-equality/cache assertions or credential rediscovery.
4. **Gate preservation:** preserve native exit 2; other errors stop. An
   `always()` evidence step cannot upgrade a failed/missing eval to success.
   Reject swallowed errors, advisory gates substituted for agreed blocking
   policy, public raw reports and unreviewed deployment commands.

Keep the generated draft local pending owner approval; do not commit/push it
as a way to "test" its safety. Cleanup only newly generated, identified files
after review; restore a prior approved copy only with overwrite approval.
Never delete pre-existing skipped files or change policy to repair a template.
Threadlight uses [the ownership boundary](threadlight-boundary.md) instead of
this generation path.
