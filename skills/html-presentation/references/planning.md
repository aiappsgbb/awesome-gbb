# Content, evidence and storyboarding

The user-selected GBB PPTX approach is the conceptual starting point:
https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/gbb-pptx
This is an original HTML-specific synthesis, not a copy of its implementation.

## Brief

Establish the listener's question and the change the talk should enable.
Confirm audience/depth, not a stereotype: an executive may understand technical
details, and an engineer may need only a short decision. Identify delivery context,
scope, language, time, required content, assumptions and cover metadata. Reuse
known answers; ask only questions that alter the story.

## Content source of truth

Use a JSON storyboard or equivalent structured artifact:

```json
{
  "brief": {
    "audience": "technical collaborators",
    "confirmation": "user",
    "question": "What changed and what must we verify next?",
    "delivery": "live + reading",
    "duration_minutes_estimate": 5,
    "reporting_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "thesis": "A complete, supported sentence."
  },
  "beats": [{
    "id": "mechanism",
    "role": "explanation",
    "title": "The claim the visual actually supports",
    "support": ["Specific fact or mechanism"],
    "implication": "Why it matters to this audience",
    "caveat": "Qualification that changes the meaning, when applicable",
    "visual": "Boundary-and-flow diagram",
    "visual_reason": "Shows where execution and data access occur",
    "composition": "Sticky explanation alongside a naturally flowing diagram",
    "context": "Explain, give an example and bridge to the next message.",
    "sources": ["S1"],
    "claim_state": "source-reported",
    "interaction": {"action": "select diagram node", "reason": "Explore its responsibility"},
    "seconds_estimate": 45
  }],
  "sources": [{
    "id": "S1",
    "title": "Inspected source",
    "url": "Exact retrieved locator",
    "date": "YYYY-MM-DD",
    "supports": "The specific claim it supports",
    "limits": "Truncated excerpt, proposal, unresolved conflict, etc."
  }]
}
```

Do not ship placeholder fields. Keep a single factual base; prominent text and
visuals carry the guided talk while contextual disclosures support deeper
reading. Keep material limits beside the claims, not in hidden detail.

## Experience direction

Translate the storyline into a web experience. Give
each beat a composition and choose its interaction from the audience's actual
task. Compare two layout concepts before coding: e.g. a dual-track scrolling
map versus a diagram-centered guided exploration. Choose a subject-specific
signature and a restrained visual system; vary composition and density.

Scroll is the narrative connective tissue. Clicks reveal relevant depth,
select a comparison or explain a relationship. Give each beat a content-driven
composition and height. A five-minute guided path and deeper optional reading
share the same continuous experience.

## Editorial review

Read only the titles first. Does the opening question get answered? Is every
step needed? Does a conclusion depend on an unstated premise? Remove duplicate
steps; add missing reasoning rather than filler.

For each title, check its supporting body. Prefer actor + action + consequence.
Use a visual because it explains a relationship, not because a section needs art.
A product-logo inventory is not an architecture. A timeline should mark real
events rather than fabricate progress for a week with no evidence.

For technical talks, show a mental model, interfaces, trust/data boundaries,
failure cases and a concrete example. For updates, separate changes, outcomes,
blockers and proposed actions. Label a suggested demo as a demo plan if it has
not run; say what its result would prove and what it would not.

## Evidence

Retain exact source locators and dates. Distinguish document modification dates,
event dates and reporting windows. Inspect source content rather than treating
a search title as evidence. Record limited retrieval coverage explicitly.

Every number needs a unit, population, period, baseline and claim state.
Derived comparisons should retain the calculation. Do not combine capacity
requested and capacity granted in a chart as if both were deployed. Do not
attribute another contributor's work to the presenter.

For internal information, respect audience and sensitivity. Exclude secrets,
tokens and unnecessary personal contact details. Preserve classification cues.
Plain HTML does not preserve Microsoft 365 rights management; delivery remains
local and internal unless the user authorizes an appropriate destination.
