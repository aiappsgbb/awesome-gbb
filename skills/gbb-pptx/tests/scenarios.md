# Content-first acceptance scenarios

These are synthetic behavioral probes, not passing results. Run them through
the updated skill in a consumer session and retain the actual prompts, outputs
and observed findings privately. Contract tests check packaging and guardrails,
not whether a model follows them. A real-deck comparison and representative-reader
acceptance remain separate. Do not install or publish a skill merely to claim
that it has passed.

## Case 1: Executive decision with weak evidence

**Prompt:** "Using synthetic S1 in the worked examples, prepare a five-minute
executive decision briefing for an operations lead, recommending whether to
proceed. Do not generate a PPTX yet; cover metadata can remain pending in the brief."

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

## Case 8: Complete deck without filler

**Prompt:** "Draft a complete five-minute executive briefing for an operations
lead from synthetic S1. Title: 'Controlled pilot decision'. Presentation date:
15 October 2026. Attribution: 'Operations team'. Use simple slides; no agenda
or separate thank-you page is needed."

**Expected:** cover uses the supplied metadata; framing establishes the decision;
development preserves evidence/uncertainty; substantive wrap-up closes the main
narrative. Roles may combine where appropriate without losing the opening/ending.

**Reject:** replacing the supplied date with today's date, inventing a named
speaker, missing framing/closing, or adding empty dividers/thank-you slides.

## Case 9: Audience confirmation and coordinator handoff

**Prompt A:** "Make a new presentation from synthetic S2. I have not decided
who it is for." **Prompt B:** "The session coordinator confirms: experienced
engineers, ten-minute explanation of request flow, not an executive decision.
Cover date/team are not supplied; leave them pending in the draft brief."

**Expected:** A asks one material audience/depth question before fixing a
storyline. B uses the explicit coordinator decision without re-asking, explains
the mechanism and limits, and does not invent cover metadata.

**Reject:** silently choosing an audience in A, a second routine confirmation
in B, invented attribution, or treating technical depth as an unlimited length.

## Case 10: Same material, different depth, fixed time

**Prompt:** "Using synthetic S2, give two five-minute outlines: one for an
executive deciding whether to investigate, one for engineers understanding the
request flow. Keep both concise. Then suggest how a mixed audience could use
one core narrative with optional technical detail."

**Expected:** executive version emphasizes implication, uncertainty and decision;
technical version explains matching and recomputation with an example and limits.
Mixed version has a primary objective, core context and optional depth. Both
honor the time; no invented performance or business evidence.

**Reject:** identical content with different labels, automatic doubling of slide
count for engineers, or deleting caveats to make the executive version short.

## Case 11: Browser preview is not the final artifact

**Prompt:** "Explore browser-first visuals for a complete deck. Colleagues must
edit titles, body text and table cells in PowerPoint, and notes must survive.
The candidate exporter rasterizes table cells and drops notes. Its browser
preview looks excellent. Can we finalize this export?"

**Expected:** reject that export as meeting the contract; identify both failures.
Propose a compatible/direct path or explicitly renegotiate requirements before
full-deck polishing. Specify a representative early export and actual-PPTX
inspection, not just browser screenshots. No installation is requested.

**Reject:** silent image fallback, accepting the browser as PowerPoint proof,
losing notes, installing a converter, or promising lossless CSS conversion.

## Case 12: Model preference and image-only permission

**Prompt:** "I prefer Opus for visual iteration; keep that as a preference,
not a benchmark. For this presentation only, images in PPTX are acceptable;
retain the speaker notes and provide a readable companion. Propose the path,
without changing session settings or generating files."

**Expected:** respect the stated preference and bounded image-only permission;
disclose lack of native text/chart editing, retain notes/reading access and
include early export proof. Report that no model comparison was measured.

**Reject:** an unsupported GPT-versus-Opus ranking, changing the session model,
generalizing image-only acceptance to later decks, or generating unrequested files.

## Case 13: Italian deck with AI-style copy

**Prompt:** "Rivedi queste slide prima dell'approvazione: titolo 'Una soluzione
innovativa e all'avanguardia', bullet 'efficienza, agilità e innovazione' e
note che iniziano con 'In un mondo in cui'. Le fonti sono S1 e S2."

**Expected:** apply the voice pass before approval; replace slogans with
source-backed claims in natural Italian; keep titles and bullets short and
parallel; preserve S1/S2 facts, numbers and technical names; report which
wording changed.

**Reject:** keeping the generic phrasing, adding unsupported numbers, expanding
bullets into paragraphs, English calques, or claiming a lexical scan proves the
copy is natural.

## Acceptance record

For each executed case record skill version/source, consumer runtime, prompt,
actual output path, observed result and unresolved issues. Evaluate against the
expected and rejected behavior above; do not assign a passing result based on
the presence of these words in SKILL.md. Preserve failures and distinguish a
corrected run from the original. For output quality, use the user's real baseline
and the reader questions in [review](../references/review.md).
