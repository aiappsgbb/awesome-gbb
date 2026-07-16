# Trustworthy Evaluation Workflow

Step-by-step procedure for calibrating a Foundry agent evaluation stack before
promoting any evaluator to a production quality gate.

> This document is referenced from
> [`../../SKILL.md § Trustworthy Evaluation Workflow`](../../SKILL.md).
> The canonical Python helper that emits the output artefacts is
> [`../python/eval_trust.py`](../python/eval_trust.py).

---

## Why Calibration Comes First

Assigning `role: gate` to an evaluator without first measuring its reliability
against known data is the single most common source of false-positive and
false-negative quality blocks in production. An evaluator that scores the same
session differently across repeated runs (high flip_rate) or that only agrees
with human labels 60% of the time (low agreement) is not ready to block a
release.

The workflow below gates gate assignment on observable calibration evidence.

---

## Step 1 — Prepare Held-Out Known-Good / Known-Bad Session Data

Collect a representative set of sessions that **human reviewers have already
labelled** as definitively good or definitively bad:

- **Known-good**: sessions where the agent completed the task correctly,
  responses were grounded, and no hallucinations were observed.
- **Known-bad**: sessions where the agent failed — wrong answers, hallucinated
  facts, incomplete task completion, or policy violations.

Minimum set: ≥ 10 known-good and ≥ 5 known-bad sessions.
Recommended set: 50 known-good and 20 known-bad (as in `calibration-run.json`).

**No production traces.** Do NOT use sessions that contain personally identifiable
information, real customer data, or proprietary content. Use anonymised or
synthetic session transcripts only.

Export sessions in the JSONL format documented in `SKILL.md § Phase 2: Score
with Foundry Evaluators` so they can be fed directly into the calibration runs.

---

## Step 2 — Run at Least Four Independent Scoring Passes

Score the held-out set with your evaluator stack **at least four times**,
treating each pass as an independent run:

```bash
# Example: four independent runs — each produces a timestamped result file
for i in 1 2 3 4; do
  python3 -c "
import json, sys
sys.path.insert(0, 'skills/foundry-evals/references/python')
from eval_trust import build_trust_evidence, write_trust_evidence
profile  = ...   # load from trust-profile.yaml or trust-profile.valid.json
calib    = ...   # load the run-$i result
evidence = build_trust_evidence(profile, calib)
write_trust_evidence(evidence, f'evals/runs/run-$i-evidence.json')
print(json.dumps(evidence, indent=2))
"
done
```

Each run must use **the same evaluator configuration** (same judge deployment,
same evaluator_version, same JSONL seed data) so the results are comparable.

A "run" is one complete scoring pass of the 70-session held-out set. Do not
split the held-out set across runs — score all sessions each time.

---

## Step 3 — Calculate Agreement and Flip Rate

After all runs complete, compute:

- **agreement** — fraction of (session, evaluator) pairs that received the same
  pass/fail verdict across all run pairs. Formula:

  ```
  agreement = (consistent verdicts) / (total verdicts across all run pairs)
  ```

- **flip_rate** — fraction of sessions that changed verdict direction (pass → fail
  or fail → pass) at least once across runs. Formula:

  ```
  flip_rate = (sessions with at least one verdict change) / (total sessions)
  ```

Record the summary stats plus the per-run detail in a calibration record matching
the shape of `calibration-run.json`:

```json
{
  "$schema": "foundry-evals-calibration/v1",
  "captured_at": "<ISO-8601 timestamp>",
  "known_good": 50,
  "known_bad": 20,
  "repeated_runs": 5,
  "agreement": 0.92,
  "flip_rate": 0.05,
  "runs": [ ... ]
}
```

Save the calibration record to `evals/runs/<timestamp>-calibration.json`.

---

## Step 4 — Tune Local Thresholds Against Calibration Data

Use the calibration data — **not** production traffic — to choose thresholds:

1. For each evaluator, plot the score distribution on known-good vs known-bad
   sessions.
2. Choose the threshold that maximises separation between the two populations
   while minimising false positives (blocking good sessions) and false negatives
   (passing bad sessions).
3. Document the chosen threshold and the reasoning in `threshold_rationale`
   in your trust profile.

---

## Step 5 — Assign Gate Only When Reliable

An evaluator is eligible for `role: gate` when **all** of the following hold:

| Criterion | Required |
|-----------|----------|
| `known_good` | > 0 |
| `known_bad` | > 0 |
| `repeated_runs` | ≥ 4 |
| `agreement` | ≥ 0.80 |
| `flip_rate` | ≤ 0.10 |

The `eval_trust.build_trust_evidence()` function enforces this: it raises
`ValueError` if `groundedness` is assigned `role: gate` when these conditions
are not met.

Do **not** promote any evaluator to gate on the first calibration run. Run at
least two calibration cycles (on different session samples) before gate assignment.

---

## Step 6 — Default Groundedness to human_review / trend

`groundedness` is the evaluator most sensitive to hallucination detection, but it
also has the highest variance across judge model versions and prompt templates.

Default assignment rules:
- **Before calibration**: `role: human_review`
- **After one calibration pass that meets the gate criteria**: `role: trend`
- **After two independent calibration passes that both meet gate criteria**: eligible for `role: gate`

This two-pass rule prevents false confidence from a lucky first calibration run.

---

## Step 7 — Emit Output Artefacts via eval_trust.py

Use the canonical helper to emit both output files. Do **not** hand-write the
trust evidence JSON — `build_trust_evidence` enforces the contract and the
groundedness-gate safeguard.

```python
import sys
sys.path.insert(0, "skills/foundry-evals/references/python")
from eval_trust import build_trust_evidence, write_trust_evidence, validate_profile_with_schema
import json, yaml

# Load profile (YAML or JSON)
with open("skills/foundry-evals/references/data/trust-profile.yaml", encoding="utf-8") as f:
    profile = yaml.safe_load(f)

# Load calibration record
with open("evals/runs/<timestamp>-calibration.json", encoding="utf-8") as f:
    calibration = json.load(f)

# Validate and build
validate_profile_with_schema(profile)
evidence = build_trust_evidence(profile, calibration)

# Emit canonical artefact
write_trust_evidence(evidence, "specs/evals-trust-evidence.json")
print("Trust evidence written.")
```

**Output artefacts:**

| File | Purpose |
|------|---------|
| `evals/runs/<timestamp>-calibration.json` | Per-calibration-run record (read-only input); archive one per calibration cycle |
| `specs/evals-trust-evidence.json` | Normalized trust evidence written by `write_trust_evidence`; canonical gate declaration checked into source control |

---

## Checklist Before Promoting to Production

- [ ] Held-out session set labelled by human reviewers (no production traces)
- [ ] At least 4 independent scoring runs completed
- [ ] `agreement ≥ 0.80` and `flip_rate ≤ 0.10` confirmed
- [ ] Thresholds tuned against calibration data, not production traffic
- [ ] `groundedness` role is `human_review` or `trend` (never `gate` on first pass)
- [ ] USR-8 baseline collected if simulator sessions are used as evidence
- [ ] `specs/evals-trust-evidence.json` committed to source control
- [ ] Benchmark block populated if release-to-release delta comparison is needed
