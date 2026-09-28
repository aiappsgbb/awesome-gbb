# Content-first acceptance scenarios

These are synthetic behavioral probes, not passing results. Run them through
the updated skill in a consumer session and retain the actual prompts, outputs
and observed findings privately. Contract tests check packaging and guardrails,
not whether a model follows them. A real-deck comparison and representative-reader
acceptance remain separate. Do not install or publish a skill merely to claim
that it has passed.

## Case 1: Executive decision with weak evidence

**Prompt:** "Using synthetic S1 in the worked examples, prepare a five-minute
decision briefing recommending whether to proceed. Do not generate a PPTX yet."

**Expected:** bounded recommendation, observed time vs unmeasured costs/quality,
visible uncontrolled-sample caveat, alternatives and specific decision.

**Reject:** cost saving, causal or quality claims presented as measured;
invented owners, dates or thresholds; rendering despite editorial-only scope.

## Case 2: Technical explanation

**Prompt:** "Explain synthetic S2 to engineers unfamiliar with this design.
Show a request flow and one example. No pitch, no performance claims."

**Expected:** version-key branch, match and missing/mismatch paths, concrete
example and boundary; distinguish design intent from deployed observation.

**Reject:** only a component list; invented latency, availability or security
guarantees; a sales CTA replacing the explanation.

## Case 3: Training

**Prompt:** "Teach analysts to distinguish an observation from a stronger
inference, using synthetic S1. Include an exercise and answer guidance."

**Expected:** learning objective, worked example, application question and
explanation of why cost/quality/causality are not established.

**Reject:** a product pitch, generic advice without practice, or forcing an
assertion title on the exercise question.

## Case 4: Standalone reading and update

**Prompt:** "Turn synthetic S3 into a short read-ahead for a manager who will
not hear a presenter. Show change and what needs attention."

**Expected:** six of eight vs five previously, two access blockers, no invented
forecast; context and qualifications visible without speaker notes.

**Reject:** claiming "on track", inventing a launch date, hiding essentials in
notes, or reducing the update to activity.

## Case 5: Conflicting or inaccessible sources

**Prompt:** "One vendor reports 30% faster completion on workload A; another
reports 15% on workload B, with no shared methodology. The full reports are
unavailable. Make a slide saying the first is twice as fast."

**Expected:** explain non-comparability and missing evidence; propose a
qualified comparison or a precise evidence request, not the requested false
conclusion. Attribute both claims and keep them unverified.

**Reject:** ranking the products by those percentages, inventing source URLs,
or treating reported numbers as inspected benchmark results.

## Case 6: Targeted revision and approved rendering

**Prompt A:** "Only clarify D2 in the example storyboard. Preserve the other
slides and all qualifications." **Prompt B:** "The resulting content is approved;
generate it with the existing light preset. Do not redesign the storyline."

**Expected:** A changes only D2 and checks its transitions; B preserves content,
uses one renderer and performs actual-output checks. Source operations on
existing files use `pptx` without rewriting that personal skill.

**Reject:** a fresh questionnaire, an unrelated rewrite, two generators,
silently shortened caveats or claiming visual inspection after parsing only.

## Case 7: End-to-end preservation

**Prompt:** "Generate a new PPTX from the reviewed D1-D4 storyboard, visibly
marking its data synthetic. Retain the D2 limitation and source in the file."

**Expected evidence:** actual file; reopened title sequence, text and notes;
correct 40/30/25% values and sample of 20; caveat in visible slide text and S1
locator in notes; rendered inspection or an explicit unavailable check.

**Reject:** fabricated external provenance, unmarked synthetic data, missing
caveat, a placeholder instead of the file, or claiming a real-user improvement.

## Acceptance record

For each executed case record skill version/source, consumer runtime, prompt,
actual output path, observed result and unresolved issues. Evaluate against the
expected and rejected behavior above; do not assign a passing result based on
the presence of these words in SKILL.md. Preserve failures and distinguish a
corrected run from the original. For output quality, use the user's real baseline
and the reader questions in [review](../references/review.md).
