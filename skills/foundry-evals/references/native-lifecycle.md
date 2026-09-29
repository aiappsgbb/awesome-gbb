# Native evaluation lifecycle without a second platform

Keep the existing agent-target and captured-response runners. Use this
checklist for the native service lifecycle they do not implement. The scoped
fallback is the official `microsoft-foundry` **observe**, **eval-datasets** or
**agent-optimizer** workflow, not another deployment or runtime migration.

## Resolve context and inspect existing artifacts

Select one agent root, environment, project endpoint, agent name/version and
approved judge deployment. Reuse its existing suite/data/evaluator metadata;
do not merge sibling agents' caches. Preserve a Threadlight project's
`threadlight-evals-manifest/v1` shape and existing output files. A `.foundry`
cache or this skill's `last_run_summary` is not a replacement manifest.

Discover the current Foundry MCP schemas before calling the operations below.
The operation names are **not** Python methods promised by SDK 2.4, and schema
discovery does not authorize resource creation or data upload.

## Generate, review, version, then execute

| Need | Native operation family | Acceptance boundary |
|---|---|---|
| Discover evaluators | `evaluator_catalog_get` | Match required input fields, metric scale, judge deployment and thresholds |
| Generate a suite | `evaluation_suite_generation_job_create` / `evaluation_suite_generation_job_get` | Review generated dataset and evaluator definitions before any run |
| Register/read reviewed suite versions | `evaluation_suite_create` / `evaluation_suite_get` | Bind the exact reviewed dataset and evaluator versions |
| Regenerate data alone | `data_generation_job_create` / `data_generation_job_get` | Save job ID; require terminal success and nonempty reviewed rows |
| Regenerate one evaluator | `evaluator_generation_job_create` / `evaluator_generation_job_get` | Review rubric, dimensions, metrics and required input schema |
| Version a rubric edit | `evaluator_catalog_update` with `createNewVersion: true` | Preserve the full returned definition; do not replace it with a metadata-only stub |
| Register/read dataset versions | `evaluation_dataset_create`, `evaluation_dataset_get`, `evaluation_dataset_versions_get` | Stable dataset name, new immutable version, returned URI and local hash |
| Run reviewed agent-target rows | `evaluation_agent_batch_eval_create` | Materialize selected dataset rows into `inputData`; suite metadata alone is not input |
| Inspect run/group | `evaluation_get` | Persist `evalId` and `evalRunId`; terminal metadata is not item scores |

Read [suite/data/evaluator generation](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/observe/references/evaluation-suite-generation.md)
for the currently available generator and evaluator refresh schemas. Record
suite name/version, dataset name/version/URI/hash, evaluator definitions and
thresholds, generation provenance and exact agent version. A regenerated
evaluator or changed threshold requires a reviewed suite/eval configuration,
not silent reuse of the old comparison group.

For agent-target MCP execution, use `inputData` (not `data` or `inputItems`).
Resolve `suiteName`/version to the dataset and evaluators, then materialize
reviewed rows; a dataset name/version alone does not supply the required input
rows. Synthetic generation is an explicit alternative with an approved sample
count and generation deployment, not recovery for a malformed request.
Persist IDs immediately so interruption resumes the same run rather than
submitting a duplicate.

## Trace to versioned dataset

1. Bound the time range and agent/environment before extraction. Inspect the
   actual telemetry schema and present the query; do not assume arbitrary
   `customDimensions` keys or request access to unrelated production data.
2. Correlate root/child spans by trace and response IDs. Retain real input,
   response and tool evidence, tool failures and provenance; never manufacture
   expected answers from an unreviewed failed response.
3. Remove secrets/PII under the owner's approved policy. Deduplicate correlated
   turns; require human curation and expected-behavior annotations before upload.
4. Split development and held-out regression cases without conversation leakage.
   Retain failure cases; do not delete hard rows to improve the score.
5. Write a **new** dataset version and record its source window, source IDs,
   transformation, review status and content hash. Treat local files as cache.
   Sync/register remotely only when authorized and keep the suite's exact
   dataset/evaluator references aligned.

Use the official [trace-to-dataset workflow](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/eval-datasets/references/trace-to-dataset.md)
and [curation workflow](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/eval-datasets/references/dataset-curation.md).
Generated data is a candidate, not reviewed acceptance evidence.

## Results and optimization

Download **all** `evals.runs.output_items.list` pages through the project's
OpenAI client, retaining raw results and failures. Separate sample-execution
errors from evaluator errors and threshold failures. Preserve valid zero
scores; missing/null metrics are unknown, not passing. Custom evaluators can
return separate score and label entries: join by item/evaluator identity and
inspect the declared output schema instead of taking the first result.

Cluster failures by retrieval, tool execution, prompt, data and evaluator
configuration. Compare candidate and baseline with the **same pinned dataset,
evaluator versions, judge deployment and thresholds**. If data changes, report
that as a separate experiment; do not attribute the difference solely to the
agent. Keep the unchanged captured-response `smoke_score` for custom transports
and existing response artifacts; it is a one-item coherence gate, not a suite.

For optimization, hand the selected baseline, failure clusters and held-out
dataset to the official [Agent Optimizer workflow](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/agent-optimizer/agent-optimizer.md).
Approve generation/evaluation spend first. Stage a new candidate, evaluate it
on unchanged acceptance criteria, inspect per-item regressions and latency/cost,
then obtain deployment/promotion authority. Keep the previous agent version and
evidence for rollback. Do not weaken evaluators or auto-apply a higher average
score that hides safety failures.

Remove only run-owned disposable datasets/evaluators/suites/runs after checking
references and retention requirements. Preserve audit evidence and report
cleanup separately from scoring. Continuous evaluation additionally needs an
explicit cadence/cap/disable/owner contract; see Plan A in the main skill.
