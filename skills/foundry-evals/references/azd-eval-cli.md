# `azd ai eval` CLI lifecycle (`azure.ai.evaluations` extension)

Companion to [`../SKILL.md` § azd ai eval CLI](../SKILL.md#azd-ai-eval-cli-azureaievaluations).
The SDK path in SKILL.md (`get_openai_client().evals`) stays authoritative for
custom graders and the canonical smoke. Use this CLI path when a project wants
a checked-in, reviewable eval recipe (`evals/azure.eval.yaml`), a CI quality
gate (`--fail-on`) or the official optimizer handoff (`azd ai agent optimize`).

Labels: **Documented** = stated on Microsoft Learn (link given).
**Tested** = reproduced live on 2026-11-20 with azd 1.37.3,
`azure.ai.evaluations` 1.0.0-beta.2, `azure.ai.agents` 1.2.0, a temporary
prompt agent and a `gpt-5.4-mini` GlobalStandard judge (Sweden Central).
**Reported** = observed by the field (issue #556) but not reproduced here.

Sources:
[Run agent evaluations with the azd CLI](https://learn.microsoft.com/azure/foundry/observability/how-to/azure-developer-cli-evaluation) ·
[Optimize a hosted agent quickstart](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-optimize-hosted-agent) ·
[Optimizer dataset/eval selection](https://learn.microsoft.com/azure/foundry/agents/how-to/create-optimizer-dataset#select-the-evaluation-for-a-run) ·
[Evaluation in GitHub Actions](https://learn.microsoft.com/azure/foundry/how-to/evaluation-github-action#use-the-azd-evaluation-extension-as-a-quality-gate).

## 1. Lifecycle

```bash
azd extension install azure.ai.evaluations     # preview; check: azd ai eval version
azd init --minimal --no-prompt -e eval          # only if no azd project exists
azd env set FOUNDRY_PROJECT_ENDPOINT "<project-endpoint>"

# Optional, billed: rubric evaluator (and/or dataset) from the agent's instructions
azd ai eval generate --evaluator --target <agent> \
  --agent-instruction-file <instructions.txt> \
  --generation-model <generation-deployment> --trace-days 0 --no-prompt

azd ai eval init --target <agent> --source dataset --evaluation-level turn \
  --dataset tests/golden.jsonl \
  --evaluator <rubric-name> --judge-model <judge-deployment> \
  --name <eval-name> --path ./evals --no-prompt
azd ai eval create <eval-name> --no-prompt       # registers dataset, evaluators, eval
azd ai eval run start --eval <eval-name> --name baseline --fail-on pass-rate=0.8 --no-prompt
azd ai eval run output list --eval <eval-name> --failed-only
azd ai eval run output export --eval <eval-name> --output-file run.json
```

- **Documented:** `init` writes `evals/azure.eval.yaml` and adds an
  `azure.ai.eval` service to `azure.yaml`; it never invokes the agent.
  `create` reconciles one eval without provisioning infrastructure.
- **Documented:** `run start` does not pin the agent version; run a named
  baseline before deploying a changed agent.
- **Documented:** the quick-evaluation `eval.yaml` of `azd ai agent eval` and
  `evals/azure.eval.yaml` are different formats and not interchangeable.
- **Documented:** stored mappings are immutable. Changing `dataMapping` or
  evaluators of an existing eval needs a new eval (or criterion) name, then
  `create` again.

## 2. Working `azure.eval.yaml` — gate eval + optimizer-input eval

Two evals on the same dataset: a **gate** with explicit `dataMapping`
(correct inputs for the rubric) and an **optimizer input** without
`dataMapping` (the optimizer refuses mapped evaluators, § 4).
This file, with placeholders filled, was accepted verbatim by
`azd ai eval create` for both evals in the tested run.

```yaml
evaluators:
  - name: returns-rubric                # produced by `azd ai eval generate --evaluator`
    source: ./evaluators/returns-rubric.json
datasets:
  - name: returns-golden
    file: ../tests/returns-golden.jsonl # rows: {"query": "...", "ground_truth": "..."}
evals:
  - name: returns-gate                  # CI gate
    dataset: returns-golden
    evaluationLevel: turn
    evaluators:
      - evaluator: returns-rubric
        initializationParameters:
          model: <judge-deployment>
        dataMapping:
          query: "{{item.query}}"
          response: "{{sample.output_items}}"
          ground_truth: "{{item.ground_truth}}"
    target:
      type: agent
      name: <agent>
  - name: returns-optimize-input        # for `azd ai agent optimize --eval`
    dataset: returns-golden
    evaluationLevel: turn
    evaluators:
      - evaluator: returns-rubric
        initializationParameters:
          model: <judge-deployment>
    target:
      type: agent
      name: <agent>
```

## 3. The `dataMapping` trap

**Tested.** `azd ai eval init` with one built-in and one generated rubric
stored these mappings (read back with `azd ai eval show <eval> -o json`):

| Criterion | `response` mapped to | `ground_truth` |
|---|---|---|
| `builtin.task_completion` | `{{sample.output_items}}` | not mapped |
| custom rubric | `{{sample.output_text}}` | not mapped, and absent from the eval item schema |

So the rubric never sees the expected answer, even though every dataset row has
`ground_truth`. **Documented:** the extension does not infer `context` or
`ground_truth` from dataset columns; map them explicitly. Adding the
`dataMapping` block of § 2 stored `ground_truth` and `sample.output_items` for the
rubric (verified in `show -o json`). On the tested 8-row dataset the rubric pass
rate moved from 7/8 to 8/8 (mean 0.7 → 0.8). Small sample, one run each:
evidence that the mapping takes effect, not a quality benchmark.

Rules: map `messages` **or** `query`/`response`, never both (Documented).
`create` checks that mapped primary inputs exist in every dataset row.

## 4. Optimizer rejects `dataMapping`

**Documented** (optimizer selection rules): the optimizer reuses only
turn-level, dataset-sourced evals with an `agent` target and no evaluator that
sets `dataMapping`. **Tested:**

```text
$ azd ai agent optimize <agent> --eval-config evals/azure.eval.yaml \
    --eval returns-gate --optimize-model <model> --no-wait --no-prompt
ERROR: eval "returns-gate": evaluator "returns-rubric" has dataMapping, which optimization cannot represent
exit code 1
```

With the same file, `--eval returns-optimize-input` passed eval selection
(Tested); outside an azd agent project it then stopped with
`instruction is required for optimization` until baseline instructions are
supplied (`.agent_configs/baseline/metadata.yaml`, a `--config` file, or the
interactive prompt). No optimization job was submitted in this test.

Keep the mapped gate and an unmapped optimizer-input eval side by side (§ 2),
and verify the optimizer's winner with the **gate** eval afterwards.

## 5. `--fail-on` gate and exit codes

```bash
azd ai eval run start --eval returns-gate --name "ci-$GITHUB_RUN_ID" \
  --fail-on pass-rate=0.8 --no-prompt
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "eval gate failed or operational error (exit $rc)"; exit 1
fi
```

- **Documented:** without `--fail-on`, a completed run with failing rows exits 0.
  `pass-rate` counts failed, errored and skipped rows against the run. `azd`
  collapses the extension's exit code, so a quality breach and an operational
  failure both surface as non-zero; read the message
  `evaluation quality gate not met` to tell them apart.
- **Conflict — Tested vs Documented:** Learn (quickstart Step 7, GitHub Actions
  page) and `run start --help` say the breach exits **1**. With azd 1.37.3 and
  extension 1.0.0-beta.2 a breach exited **2** (`pass rate 25.0% is below the
  required 99.0%` and `50.0% is below the required 80.0%`). A passing gate
  (`100.0%` vs `0.8`) exited 0. Treat any non-zero as failure; never test for
  `== 1`.
- **Documented:** an invalid threshold is rejected before submission. For CI,
  Learn recommends `run start --no-wait -o json` then
  `run show <run-id> --wait --fail-on ...` and `run output export <run-id>`.

## 6. Known failures (extension 1.0.0-beta.2)

| Date | Command | Symptom | Status | Workaround |
|---|---|---|---|---|
| 2026-11-20 | `azd ai eval generate --dataset --from traces` | `HTTP 400 invalidPayload ... Invalid seed source for data generation job` | **Tested** on a project without Application Insights; also **Reported** with App Insights connected | Harvest traces yourself (below), or `--from prompt` / `--from agent` |
| Nov 2026 | `azd ai eval generate --evaluator --trace-days 1` | Misleading "Model authentication or authorization failed ... Foundry User role" | **Reported** only. Not reproduced on 2026-11-20 (no App Insights; `--trace-days 1` succeeded) | Use `--trace-days 0` |
| 2026-11-20 | `azd ai eval show <name> -o json` right after `create` | `no eval "<name>" in this project` once; succeeded seconds later | **Tested**, transient | Retry, or pass the eval ID printed by `create` |
| 2026-11-20 | `--fail-on` exit code | 2, not the documented 1 | **Tested** (§ 5) | Check non-zero |
| Nov 2026 | `azd ai agent eval *` (agents extension) | Prints migration guidance only | **Reported** | Use `azd ai eval` |

Trace → dataset workaround (**Reported**): query App Insights for the agent's
`invoke_agent <agent>:<version>` dependency spans, read
`gen_ai.input.messages` / `gen_ai.output.messages`, write `query` rows and
hand-label `ground_truth`. Redact PII before committing the JSONL.

**Reported** hosted-agent precondition: tool calls appear in
`sample.tool_calls` only when the hosted agent emits them as Responses output
items; otherwise tool evaluators see nothing.

## 7. Cost and duration (Tested)

8 rows, two LLM evaluators, `gpt-5.4-mini` judge: about 30–37K prompt and
~4.7K completion judge tokens per run, 38–45 s wall clock. `generate --evaluator`
took ~25 s. Judge cost scales with rows × evaluators × response length; price a
real suite with the
[Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
for your judge model.

## 8. Cleanup

`azd ai eval delete <eval> --force` removes an eval and its runs, not shared
datasets or evaluators (Documented in `delete --help`). Remove those with
`azd ai eval dataset delete` / `azd ai eval evaluator delete`, and delete the
temporary agent you evaluated.
