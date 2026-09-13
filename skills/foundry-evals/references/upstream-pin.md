---
schema_version: 2
freshness_tier: A
automation_tier: auto

upstream:
  type: github_repo
  repo: Azure/azure-sdk-for-python
  ref: refs/tags/azure-ai-projects_2.6.0
  pinned_sha: f90b55500941d7b161afb94b9ba45e53a865c4e2
  pinned_commit_message: "Update CHANGELOG for version 2.6.0 release, add new samples, and impr… (#48900)"
  license: MIT
  notes: |
    The SDK release tag is the source pin. The bounded runtime set below is
    azure-ai-projects~=2.6.0, azure-identity~=1.25.3, openai~=3.8.0.
    Validation imports and calls the repository's canonical eval_runner;
    it does not clone/reimplement the scorer. A static synthetic Q/A pair
    isolates score-only validation from target agent availability.
    Agent-target and explicit invoke+score are separate live fixture paths.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.6.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/CHANGELOG.md
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md
  - name: openai
    source: pypi
    version: "3.8.0"
    upstream_changelog: https://github.com/openai/openai-python/blob/main/CHANGELOG.md

docs_to_revalidate:
  - "https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent"
  - "https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation-targets"
  - "https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation-results"
  - "https://github.com/Azure/azure-sdk-for-python/tree/azure-ai-projects_2.6.0/sdk/ai/azure-ai-projects/samples/evaluations"
  - "https://pypi.org/project/azure-ai-projects/"

known_issues: []

validation:
  requires:
    - foundry_project
    - pypi
    - github_only
  runnable: false
  script: |
    #!/usr/bin/env bash
    # CI supplies credentials. Manual callers first use azure-tenant-isolation.
    set -euo pipefail
    : "${FOUNDRY_PROJECT_ENDPOINT:?Set the Foundry project endpoint}"
    : "${JUDGE_MODEL_DEPLOYMENT:=gpt-5.4-mini}"
    export JUDGE_MODEL_DEPLOYMENT
    ROOT_DIR="${PIN_VALIDATION_REPO_ROOT:-$(pwd)}"
    WORKDIR="${WORKDIR:-$(pwd)/.upstream-pin-work/foundry-evals}"
    export ROOT_DIR WORKDIR
    EXPECTED_SHA=f90b55500941d7b161afb94b9ba45e53a865c4e2
    ACTUAL_SHA=$(git ls-remote https://github.com/Azure/azure-sdk-for-python refs/tags/azure-ai-projects_2.6.0 | awk '{print $1}')
    test "$ACTUAL_SHA" = "$EXPECTED_SHA"
    mkdir -p "$WORKDIR"
    python3 -m venv "$WORKDIR/.venv"
    "$WORKDIR/.venv/bin/python" -m pip install --quiet \
      "azure-ai-projects~=2.6.0" "azure-identity~=1.25.3" "openai~=3.8.0"
    "$WORKDIR/.venv/bin/python" - <<'PY'
    import json
    import os
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(os.environ["ROOT_DIR"]) / "skills/foundry-evals/references/python"))
    from eval_runner import smoke_score
    evidence = pathlib.Path(os.environ["WORKDIR"]) / "score-evidence.json"
    metrics = smoke_score(
        "What is the capital of France?",
        "The capital of France is Paris.",
        artifact_path=evidence,
    )
    report = json.loads(evidence.read_text())
    assert report["cleanup"] == "deleted", "Disposable eval cleanup unverified"
    print("FOUNDRY_EVAL_RUN_CREATED", report["run_id"])
    print("FOUNDRY_EVAL_RUN_TERMINAL", report["status"])
    print("FOUNDRY_EVAL_NUMERIC_SCORE", metrics["coherence"])
    print("FOUNDRY_EVALS_VALIDATION_PASS")
    PY
  expected_output:
    - "FOUNDRY_EVAL_RUN_CREATED"
    - "FOUNDRY_EVAL_RUN_TERMINAL"
    - "FOUNDRY_EVAL_NUMERIC_SCORE"
    - "FOUNDRY_EVALS_VALIDATION_PASS"
  failure_signatures: []

last_validated: 2026-09-13
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `foundry-evals`

## 1. Pin and support boundary

Source: `Azure/azure-sdk-for-python`, release tag
`azure-ai-projects_2.6.0`, SHA
`f90b55500941d7b161afb94b9ba45e53a865c4e2` (MIT).
Runtime: `azure-ai-projects~=2.6.0`, `azure-identity~=1.25.3`,
`openai~=3.8.0`. The scorer accesses **the project's OpenAI sub-client**,
not `AIProjectClient.evals`. HTTP URL checks use `httpx~=0.28.1`.
Package drift is tracked independently of the immutable source tag.

The 1.4.0 skill refresh removes an obsolete universal agent-target ban.
Microsoft documents agent-target evaluation for prompt/hosted Responses
agents and a distinct freeform input shape for hosted Invocations agents.
The canonical smoke covers Responses only; custom transports must capture
real output before the explicit score-only path. No automatic fallback
or assumption that every project exposes every documented preview surface.

The static pin smoke proves a real numeric evaluation result and disposable
eval cleanup, not agent invocation, quality acceptance or all hosted protocols.
`last_run_summary` and its EVAL-201 artifact contract are unchanged.

## 2. Verification checklist (executable mirror)

CI runs this credentialed pin only via `--include-azure`. Standard pin
validation skips it. Manual callers must establish the approved isolated
Azure CLI/azd context first; neither this script nor the helper logs in or
changes accounts. The judge deployment must already exist.
The runner supplies `PIN_VALIDATION_REPO_ROOT` for source imports while executing
in a separate working directory. Manual execution falls back to the repository
CWD. Venv/evidence output stays under the execution CWD (or explicit `WORKDIR`),
not the runner-supplied source tree.

```bash
#!/usr/bin/env bash
# CI supplies credentials. Manual callers first use azure-tenant-isolation.
set -euo pipefail
: "${FOUNDRY_PROJECT_ENDPOINT:?Set the Foundry project endpoint}"
: "${JUDGE_MODEL_DEPLOYMENT:=gpt-5.4-mini}"
export JUDGE_MODEL_DEPLOYMENT
ROOT_DIR="${PIN_VALIDATION_REPO_ROOT:-$(pwd)}"
WORKDIR="${WORKDIR:-$(pwd)/.upstream-pin-work/foundry-evals}"
export ROOT_DIR WORKDIR
EXPECTED_SHA=f90b55500941d7b161afb94b9ba45e53a865c4e2
ACTUAL_SHA=$(git ls-remote https://github.com/Azure/azure-sdk-for-python refs/tags/azure-ai-projects_2.6.0 | awk '{print $1}')
test "$ACTUAL_SHA" = "$EXPECTED_SHA"
mkdir -p "$WORKDIR"
python3 -m venv "$WORKDIR/.venv"
"$WORKDIR/.venv/bin/python" -m pip install --quiet \
  "azure-ai-projects~=2.6.0" "azure-identity~=1.25.3" "openai~=3.8.0"
"$WORKDIR/.venv/bin/python" - <<'PY'
import json
import os
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(os.environ["ROOT_DIR"]) / "skills/foundry-evals/references/python"))
from eval_runner import smoke_score
evidence = pathlib.Path(os.environ["WORKDIR"]) / "score-evidence.json"
metrics = smoke_score(
    "What is the capital of France?",
    "The capital of France is Paris.",
    artifact_path=evidence,
)
report = json.loads(evidence.read_text())
assert report["cleanup"] == "deleted", "Disposable eval cleanup unverified"
print("FOUNDRY_EVAL_RUN_CREATED", report["run_id"])
print("FOUNDRY_EVAL_RUN_TERMINAL", report["status"])
print("FOUNDRY_EVAL_NUMERIC_SCORE", metrics["coherence"])
print("FOUNDRY_EVALS_VALIDATION_PASS")
PY
```

## 3. Refresh procedure

Verify the release tag, install the bounded set and run the script above.
Every expected marker must be present. For runtime changes also run the
consumer fixture or its approved live equivalent; the pin's static pair
cannot prove an agent-target path. Record execution, quality and cleanup
separately. Re-pin only after inspecting upstream API/sample changes, then
update this frontmatter and the skill version together.

The previous May 2026 pin used source SHA
`99ed7476c82bb6b02363ce4cc6c0d2a5d01f2c97` and a duplicated inline scorer.
Its history is not evidence for the current helper or agent-target path.

## 4. Sanitized live verification — 2026-09-13

Using an owner-approved isolated CLI credential and existing CI project/model:

- One UUID-named disposable prompt agent; no shared infrastructure/RBAC changes.
- Agent-target: one generated non-empty response, completed run, coherence `5.0`.
- Explicit invoke+score: one captured non-empty response, completed run,
  coherence `5.0`.
- Both evals and the prompt agent deleted; subsequent reads returned HTTP 404.
- The executable pin script independently scored its static synthetic pair
  (`4.0`), completed, deleted its eval and emitted every expected marker.
- The actual `scripts/run-pin-validation.py::run_one` subsequently passed from
  its isolated working directory using the runner-supplied canonical source root.
- The corrected citation helper resolved two public Microsoft Learn URLs.

This proves the two **prompt-agent Responses** paths and the score helper, not
hosted-agent runtime behavior, Invocations/freeform input, full tool-aware
quality, continuous evaluation or production readiness. The operational
IDs/raw per-item artifacts are retained privately by the operator, not here.
