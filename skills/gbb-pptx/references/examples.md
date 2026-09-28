# Worked content examples

All organizations, situations and measurements below are **synthetic**. These
are examples of reasoning and qualification, not customer outcomes or benchmark
evidence. Do not reuse their numbers as facts in a real presentation.

## Decision: replace benefits with a bounded recommendation

**Brief:** an operations lead must decide whether to run a controlled pilot.
**Source S1:** supplied synthetic exercise notes: 20 selected requests; mean
elapsed handling time was 40 minutes before and 30 minutes after a workflow
change. No control group; request mix, quality and costs were not measured.

**Before**

Title: "Automation benefits"

Body: "25% lower costs. Better quality. Unlimited scalability."

**Why it fails:** only time was measured. Cost, quality, scale and causality
are unsupported; even the time change may reflect the selected request mix.

**After: storyboard**

| Slide | Title and role | Support and visible qualification |
|---|---|---|
| D1 | "Run a controlled pilot before committing to rollout" — recommendation | The observed time signal warrants investigation, not a claim of proven savings. Proposed decision, not a measured fact. |
| D2 | "Observed handling time fell 25% in 20 selected requests" — evidence | Synthetic S1: 40 -> 30 minutes, `(40 - 30) / 40 = 25%`. On-slide caveat: uncontrolled sample; request mix may explain the change. |
| D3 | "Cost and quality remain unmeasured" — decision boundary | S1 contains neither measure. A comparison of stop / controlled pilot / rollout uses the same criteria: learning value, exposure and reversibility. |
| D4 | "Agree the pilot owner, measures and stop criteria" — next action | Proposed measures: elapsed time, errors/rework and actual operating cost. Owner and thresholds need a decision; do not invent approval or targets. |

D2 notes explain the calculation and full S1 locator, not a claim of cost savings.
For standalone reading, include the sample/method limitation visibly. A bar
comparison may explain the observation; decorative arrows add no evidence.

## Technical explanation: replace a component list with a mechanism

**Source S2:** synthetic design specification: a request can return a cached
answer only when its version key matches; otherwise the service recomputes it.
No latency benchmark or availability guarantee is supplied.

**Before:** "Architecture" / "API, cache, worker, database" plus four logos.

**After title:** "A matching version key allows reuse; other requests recompute"

**Support:** a request-path diagram with a version-check branch: match -> cached
answer; mismatch/missing entry -> recomputation. Label this a proposed design
from S2, not a deployed behavior.

**Implication:** reuse is conditional, not guaranteed for every request.
**Visible limit:** key/version correctness is required; no measured latency claim.
**Notes:** walk through one matching and one missing-key example. The diagram
explains a mechanism without inventing a service-level guarantee.

## Training: replace a slogan with a learning check

**Before:** "Master critical thinking" / "Understand data. Draw insights. Act."

**After objective:** distinguish an observed time reduction from a cost claim.

Use synthetic S1 above as a worked example, then ask:
"Which conclusion is supported: lower observed time, lower operating cost,
or higher quality? What additional evidence would you need for the others?"

**Expected answer:** lower observed time in the selected sample only; measured
cost and quality, comparable cases and a suitable comparison design are needed
for stronger claims. Do not require a sales CTA on this exercise slide.
Keep the exercise question as a question, not an artificial assertion title.

## Update: distinguish movement from activity

**Source S3:** synthetic status note: of eight planned reviews, five were complete
last week and six are complete today; two await access. No completion forecast.

**Before:** "Progress" / "Meetings held. Reviews ongoing. Strong momentum."

**After:** "Six of eight reviews are complete; two await access"

Show the change from five to six, the two blocked reviews and the requested
access decision. Attribute the baseline dates from the real source when using
this pattern. Do not infer a launch date or "on track" from one completed review.

## Revision scope: preserve what was approved

If asked only to clarify D2, repair its title, caveat and explanation while
preserving D1/D3/D4. If content is already approved and the user requests
rendering, do not restart the storyline workshop. Flag a newly noticed factual
contradiction, but do not use this skill to overwrite approved wording silently.
