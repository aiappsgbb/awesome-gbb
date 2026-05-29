---
schema_version: 2
freshness_tier: A
automation_tier: auto

upstream:
  type: github_repo
  repo: Azure/azure-sdk-for-python
  ref: main
  pinned_sha: 99ed7476c82bb6b02363ce4cc6c0d2a5d01f2c97
  pinned_commit_message: |
    do not validate res
  license: MIT
  notes: |
    This skill wraps the Foundry evaluation APIs surfaced through the Azure SDK for Python
    (`azure-ai-projects`) plus the public evaluation samples in the upstream repository.
    Full validation creates a live eval definition and run in a Foundry project, so drift
    issues are human-triaged rather than assigned to GHCP automation.

docs_to_revalidate:
  - "https://github.com/Azure/azure-sdk-for-python"
  - "https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_continuous_evaluation_rule.py"
  - "https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py"
  - "https://pypi.org/project/azure-ai-projects/"
  - "https://learn.microsoft.com/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard"

known_issues: []

validation:
  requires:
    - foundry_project
    - pypi
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — requires live Foundry project + judge model access
    # Run this from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill
    set -euo pipefail

    : "${AZURE_AI_PROJECT_ENDPOINT:?Set the Foundry project endpoint}"
    : "${AZURE_AI_AGENT_NAME:?Set a hosted or prompt agent name in the project}"
    : "${JUDGE_MODEL_DEPLOYMENT:=gpt-5.4-mini}"

    PINNED_SHA="${PINNED_SHA:-99ed7476c82bb6b02363ce4cc6c0d2a5d01f2c97}"
    ROOT_DIR="$(pwd)"
    WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/foundry-evals}"

    rm -rf "$WORKDIR"
    mkdir -p "$WORKDIR"
    git clone --quiet https://github.com/Azure/azure-sdk-for-python "$WORKDIR/azure-sdk-for-python"
    cd "$WORKDIR/azure-sdk-for-python"
    git checkout --quiet "$PINNED_SHA"

    python -m venv .venv
    . .venv/bin/activate
    python -m pip install --upgrade pip --quiet
    pip install --quiet "azure-ai-projects~=2.0" "azure-identity~=1.19" "python-dotenv~=1.0"

    python - <<'PY'
    import os
    import time
    import uuid
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient

    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    agent_name = os.environ["AZURE_AI_AGENT_NAME"]
    judge_model = os.environ.get("JUDGE_MODEL_DEPLOYMENT", "gpt-5.4-mini")

    with DefaultAzureCredential() as credential:
        project = AIProjectClient(endpoint=endpoint, credential=credential, allow_preview=True)
        agent_client = project.get_openai_client(agent_name=agent_name)
        response = agent_client.responses.create(
            input="Reply with one sentence containing the token upstream-pin-smoke.",
            stream=False,
        )
        response_text = getattr(response, "output_text", "") or ""
        if "upstream-pin-smoke" not in response_text.lower():
            raise SystemExit(f"agent smoke response did not contain token: {response_text!r}")

        eval_client = project.get_openai_client()
        eval_name = f"upstream-pin-eval-{uuid.uuid4().hex[:8]}"
        eval_def = eval_client.evals.create(
            name=eval_name,
            data_source_config={
                "type": "custom",
                "item_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "response": {"type": "string"},
                    },
                    "required": ["query", "response"],
                },
                "include_sample_schema": True,
            },
            testing_criteria=[
                {
                    "type": "azure_ai_evaluator",
                    "evaluator_name": "builtin.task_adherence",
                    "initialization_parameters": {"deployment_name": judge_model},
                    "data_mapping": {
                        "query": "{{item.query}}",
                        "response": "{{item.response}}",
                    },
                }
            ],
        )
        run = eval_client.evals.runs.create(
            eval_id=eval_def.id,
            name=f"{eval_name}-run-{int(time.time())}",
            data_source={
                "type": "jsonl",
                "source": {
                    "type": "file_content",
                    "content": [
                        {
                            "item": {
                                "query": "Did the agent return the requested validation token?",
                                "response": response_text,
                            }
                        }
                    ],
                },
            },
        )
        print(f"FOUNDRY_EVAL_RUN_CREATED {run.id} {getattr(run, 'status', 'unknown')}")
    PY

    echo "FOUNDRY_EVALS_VALIDATION_PASS"
  expected_output:
    - "FOUNDRY_EVAL_RUN_CREATED"
    - "FOUNDRY_EVALS_VALIDATION_PASS"
  failure_signatures: []

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 0
---

# Upstream pin — `foundry-evals` skill

This file is the **machine-readable validation contract** for the
`foundry-evals` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `Azure/azure-sdk-for-python` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `99ed7476c82bb6b02363ce4cc6c0d2a5d01f2c97` |
| **Pinned commit subject** | `do not validate res` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-15` |

Refresh procedure:
```bash
git ls-remote https://github.com/Azure/azure-sdk-for-python main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Verification checklist (the executable contract)

> **For coding agents**: `validation.runnable` is `false`. Do not run this in
> GHCP automation; it requires a live Foundry project and model access.

```bash
#!/usr/bin/env bash
# HUMAN EXECUTION ONLY — requires live Foundry project + judge model access
# Run this from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill
set -euo pipefail

: "${AZURE_AI_PROJECT_ENDPOINT:?Set the Foundry project endpoint}"
: "${AZURE_AI_AGENT_NAME:?Set a hosted or prompt agent name in the project}"
: "${JUDGE_MODEL_DEPLOYMENT:=gpt-5.4-mini}"

PINNED_SHA="${PINNED_SHA:-99ed7476c82bb6b02363ce4cc6c0d2a5d01f2c97}"
ROOT_DIR="$(pwd)"
WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/foundry-evals}"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
git clone --quiet https://github.com/Azure/azure-sdk-for-python "$WORKDIR/azure-sdk-for-python"
cd "$WORKDIR/azure-sdk-for-python"
git checkout --quiet "$PINNED_SHA"

python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip --quiet
pip install --quiet "azure-ai-projects~=2.0" "azure-identity~=1.19" "python-dotenv~=1.0"

python - <<'PY'
import os
import time
import uuid
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
agent_name = os.environ["AZURE_AI_AGENT_NAME"]
judge_model = os.environ.get("JUDGE_MODEL_DEPLOYMENT", "gpt-5.4-mini")

with DefaultAzureCredential() as credential:
    project = AIProjectClient(endpoint=endpoint, credential=credential, allow_preview=True)
    agent_client = project.get_openai_client(agent_name=agent_name)
    response = agent_client.responses.create(
        input="Reply with one sentence containing the token upstream-pin-smoke.",
        stream=False,
    )
    response_text = getattr(response, "output_text", "") or ""
    if "upstream-pin-smoke" not in response_text.lower():
        raise SystemExit(f"agent smoke response did not contain token: {response_text!r}")

    eval_client = project.get_openai_client()
    eval_name = f"upstream-pin-eval-{uuid.uuid4().hex[:8]}"
    eval_def = eval_client.evals.create(
        name=eval_name,
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                },
                "required": ["query", "response"],
            },
            "include_sample_schema": True,
        },
        testing_criteria=[
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.task_adherence",
                "initialization_parameters": {"deployment_name": judge_model},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                },
            }
        ],
    )
    run = eval_client.evals.runs.create(
        eval_id=eval_def.id,
        name=f"{eval_name}-run-{int(time.time())}",
        data_source={
            "type": "jsonl",
            "source": {
                "type": "file_content",
                "content": [
                    {
                        "item": {
                            "query": "Did the agent return the requested validation token?",
                            "response": response_text,
                        }
                    }
                ],
            },
        },
    )
    print(f"FOUNDRY_EVAL_RUN_CREATED {run.id} {getattr(run, 'status', 'unknown')}")
PY

echo "FOUNDRY_EVALS_VALIDATION_PASS"
```

**Expected output** must contain (substring match):

- `FOUNDRY_EVAL_RUN_CREATED`
- `FOUNDRY_EVALS_VALIDATION_PASS`

**Failure signatures**: none recorded.

---

## 3. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Issue-only validation procedure | ✅ | Human-run script documented for live Foundry eval creation. |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 4. Known issues at this pin

No linked upstream issues are recorded for this pin.

---

## 5. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/Azure/azure-sdk-for-python main
   ```
2. **Update front-matter**: set `upstream.pinned_sha` to the new value and
   `upstream.pinned_commit_message` to the new commit subject.
3. **Human-run validation**: run the script in § 2 from a shell that has the
   required Foundry project access.
4. **Verify expected output**: each `expected_output[]` substring must appear.
5. **Update audit trail**: set `last_validated`, `validated_by`, and
   `known_issues_count`.
6. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
7. **Open PR**: touch only `references/upstream-pin.md` and the SKILL.md
   frontmatter version line.

---

## 6. URLs to re-validate (link-rot detector input)

- <https://github.com/Azure/azure-sdk-for-python>
- <https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_continuous_evaluation_rule.py>
- <https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py>
- <https://pypi.org/project/azure-ai-projects/>
- <https://learn.microsoft.com/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard>

---

## 7. Cross-references worth bookmarking

- `sdk/ai/azure-ai-projects/samples/evaluations/` — evaluation rule samples
- `sdk/ai/azure-ai-projects/` — Azure AI Projects package source

---

## 8. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. `automation_tier` is `issue_only` and `validation.runnable` is `false`.
>    Do not run the live validation script without explicit credentials from a human.
> 2. Open or update the drift issue with the new SHA and ask a human maintainer to
>    run § 2.
> 3. If the human posts passing evidence, update this pin file and bump only the
>    SKILL.md `metadata.version` PATCH line.
