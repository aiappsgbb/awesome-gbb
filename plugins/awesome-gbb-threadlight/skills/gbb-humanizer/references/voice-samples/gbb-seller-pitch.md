# GBB Seller Pitch — voice sample

Use this sample as the calibration anchor when humanizing prose that a
seller will read aloud, paste into customer-facing collateral, or use as a
demo intro: `overview.html`, `prep-guide.md`, `demo-script.md`, generated
PPTX speaker notes.

**Voice profile.** Confident without being cocky. Opinionated. Concrete.
Mixes short sentences with the occasional longer one that takes its time.
Comfortable with first person ("I keep coming back to…", "Here's what gets
me about this…"). Concedes complexity instead of papering over it. Names
specifics — products, regions, regulators, real numbers — instead of
generic categories. Avoids marketing triplets. Avoids hyphenated buzzwords
("data-driven", "client-facing"). Will use one em dash per page, not five.

---

Most enterprise AI pitches sound the same. Big number, big promise, vague
architecture diagram with arrows that mean nothing, then a smiling photo of
a customer who may or may not actually be in production. We have all sat
through it. The customer in front of you has too.

Here is what I think actually works in the room. Pick one process. Pick the
hardest sub-step inside it. Build the smallest agent that can do that
sub-step end to end with a real connector and a real eval. Then show the
trace.

The trace is the part nobody else shows. We open App Insights live in the
demo. The agent's reasoning is on the screen. The MCP call to the customer
system is on the screen. The retrieval citations are on the screen. The
evaluator score for the previous run is on the screen. There is nowhere to
hide. Customers stop asking abstract questions about hallucinations and
start asking which connector they should plug in next.

That is the whole pitch. One narrow process. One real connector. One trace.

It does mean we have to be honest about what we are not doing. We are not
replacing the case-management system. We are not building a "data fabric".
We are not promising a payback period because we do not yet know how often
their cases will actually trigger this path. We are saying: here is the
agent doing the work, here is the audit, here is the eval, here is the
gate before it ever touches production. The number is whatever the number
turns out to be.

I have done this 14 times in the last year. The pattern that lands is
always the same. Show the work. Show the trace. Promise less than you can
deliver. The customer's procurement team will believe the second pilot
because the first one was honest.

---

A few mechanics from the field, in case they are useful.

The Foundry agent itself is the easy bit. The hard bit is the connector.
Pick a system you can actually mock convincingly with seeded data — CRM,
collections, claims, whatever the customer's SME says is the bottleneck —
and put an MCP server in front of it. The mock is in scope for V1. The
real connector is V2. Sellers who promise the real connector in V1 lose
the deal in V2 when integration timelines slip.

The eval set is non-negotiable. Twenty named scenarios with expected
behavior. Continuous scoring in CI. The eval set is also the artifact
that survives the pilot — when the customer's compliance team asks how
the model will behave on edge case 17, you point at S-017 and the score
trend.

Identity is where most pilots quietly slip. UAMI everywhere on the
workload side. EntraID with conditional access for users. No keys in
config. The customer security team has seen too many pilots cut corners
here and they are watching for it.

When in doubt, narrow the scope. The pilot that ships is worth more than
the pilot that promises everything.
