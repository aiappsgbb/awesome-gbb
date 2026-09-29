# Editorial and delivery review

Review content before rendering, then confirm that rendering preserved it.
For a targeted edit, inspect the changed claims and neighboring transitions,
not an unnecessary rewrite of the entire deck.

## Editorial pass

| Check | Question | Repair |
|---|---|---|
| Audience fit | Can this audience understand the terms and see why the message matters? | Add necessary context or a concrete example; remove irrelevant detail |
| Audience confirmation | Was audience/depth supplied by the user, brief or authorized coordinator? | Resolve missing/conflicting direction before finalizing a new storyline; do not re-ask settled questions |
| Complete-deck framing | Does a new complete deck have a cover, framing, development and meaningful closing? | Add the missing role or combine it deliberately; do not inflate an excerpt or targeted edit |
| Cover metadata | Are presentation date and speaker/team confirmed or explicitly omitted? | Ask for missing facts; do not substitute the generation date or invented attribution |
| Storyline | Do titles form a reasoned sequence that resolves the opening question? | Expose missing premises, reorder, merge redundant slides |
| Slide contribution | What is lost if this slide is removed? | Give it a distinct role or remove it while preserving required content |
| Evidence fit | Does the source actually support the title at this strength and scope? | Qualify the title, find the missing proof or omit the unsupported claim |
| Implication | Is the "so what" explicit, and does it follow? | Explain the consequence without turning inference into fact |
| Alternatives | Are relevant objections and competing options treated fairly? | Add shared criteria, trade-offs and the option of not acting where relevant |
| Uncertainty | Could a hidden limitation change the audience's decision? | Move that qualification beside the claim |
| Delivery mode | Does a read-ahead make sense without hidden notes? | Put essential context in the reading path |
| Time and scope | Can the argument, examples and discussion fit the requested time? | Trim deliberately; label estimates until rehearsed |
| Ending | Does it resolve the purpose? | State decision/next step, learning check, conclusion or unresolved question as appropriate |

For data, apply the [evidence rules](evidence.md): sources alone do not prove
comparability, causality or the accuracy of calculations.

Record findings as **slide ID -> problem -> why it matters -> proposed repair**.
Classify them as:

- **Blocking:** fabricated or materially unsupported claims, contradictions,
  missing required content, misleading comparisons or lost consequential caveats.
- **Major:** unclear argument, audience mismatch, unjustified recommendation,
  missing mechanism or unusable standalone reading.
- **Minor:** local wording or redundancy that does not change meaning.

Resolve blocking issues before calling a deck ready. An explicitly labeled draft
may retain visible gaps when the user wants one; label them in the deliverable
as well as the handoff. Do not hide a blocking defect behind an average score.

## Post-render preservation

Reopen the actual output file. Compare it with the reviewed storyboard:

1. Titles and sequence retain the intended argument.
2. Material numbers, units, denominators and qualifications remain accurate.
3. Chart and table data agree with the cited values; visual axes do not distort.
4. Sources, full note locators and appendix references are present and usable.
5. Notes explain rather than contradict the slide; no essential caveat lives
   only in notes when the audience will receive a slide-only export.
6. No placeholders, duplicate slides or generator instructions remain.

Inspect rendered pages for clipping, text overlap, reading size, contrast,
chart-label clarity and unintended emphasis. If a rendering or opening tool is
unavailable, distinguish successful file parsing from unverified visual output.
Source text extraction is not proof that every text box is visible.

For the optional [browser-first path](browser-first.md), also compare the
exported deck with its approved browser rendering. Check slide count after
animation/click expansion, fonts and text wrapping, note/source preservation,
and which objects remain editable. Exercise a representative required edit
(for example, change a heading or table cell) in the target application when
available; mere text extraction is not proof of useful editability.
If only XML inspection is possible, report structural evidence separately from
unverified application behavior. A browser screenshot or image-only PPTX cannot
certify native editability. Unapproved rasterization of required editable
content blocks delivery; use a permitted fallback or obtain an explicit change
to the output contract.

For revisions, compare the approved content and required facts before/after,
not just slide count. An aesthetic change that loses meaning is a regression.
Do not silently overwrite the user's original file.

## Acceptance and stopping

Batch related repairs and recheck the affected argument and output. If another
pass adds no material improvement, stop and identify the unresolved decision
instead of producing cosmetic variants.

Separate **mechanical checks**, **editorial assessment**, **observed reader
understanding**, and **user acceptance**. A model's self-rating or a test that
looks for instruction keywords establishes neither comprehension nor persuasion.

For meaningful before/after acceptance, use the same input, audience, purpose
and time allowance. Preserve the baseline; use anonymous A/B versions where
practical. Ask a representative reader to state the message, supporting evidence,
remaining uncertainty and resulting decision or learning. Record actual answers,
not predicted reader reactions. A synthetic example cannot replace the user's
real disappointing deck.
