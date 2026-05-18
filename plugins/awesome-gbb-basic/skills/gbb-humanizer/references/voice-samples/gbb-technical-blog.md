# GBB Technical Blog — voice sample

Use this sample as the calibration anchor when humanizing prose in
technical write-ups: generated README sections, internal "lessons learned"
docs, technical blog posts, post-mortem prose.

**Voice profile.** Hands-on. Specific about tooling — version numbers,
config flags, error messages, file paths. Comfortable with uncertainty
("we tried this, it half-worked, here's what we changed"). Prefers active
voice. Uses first-person plural ("we") when describing team work,
first-person singular ("I") when describing personal observation. Avoids
buzzwords. Will say "broke", "wrong", "slow" instead of "suboptimal" or
"opportunity for optimization". Includes the ugly bits.

---

We spent two days last week debugging an intermittent timeout in our
hosted Foundry agent. The symptom was simple. About one in twenty calls
would hang for the full 60-second client timeout, then return a
successful response a moment later. App Insights showed the trace
completing in 4 seconds. The client said 60. Something between the two
was lying.

The first thing we tried was raising the client timeout. That is always
the wrong fix and we knew it but we tried it anyway because the demo was
the next morning. The timeouts moved from 60 seconds to 180. Not helpful.

The actual cause turned out to be a stale connection in the SDK's
underlying HTTP pool. The agent was using `azure-ai-projects` 1.0.0 at
the time, which inherited a connection-pool default from the
`azure-core` transport that did not refresh idle connections. When the
agent had been quiet for more than about 90 seconds — which happens a
lot in demos when the seller is talking — the next call would pick up
a half-dead connection, the TCP layer would eventually figure that out,
and the call would silently retry on a fresh connection. The retry was
fast. The timeout was the dead-connection detection.

The fix was to bump `azure-ai-projects` to 1.1.2 and pass an explicit
`HttpTransport` with `connection_timeout=10` and a smaller
`pool_max_idle_seconds`. The change was three lines. Finding it took
two days. Most of the time went into reading SDK source and convincing
ourselves that the App Insights trace was telling the truth.

A few things we learned.

App Insights is not always the source of truth for the client. The
trace records what the server saw. If the client and server disagree,
they may both be right. We added explicit client-side spans for the
HTTP call boundary, which made the dead-connection retry visible.

`configure_azure_monitor()` had to be called before the first SDK
import for the spans to attach. We had it after, which is why the
client-side span took an extra hour to wire up.

The Bicep change to add `customSubDomainName` to the AI Services
resource so that the SDK could resolve the endpoint correctly was
documented in passing in one Microsoft Learn page and nowhere in the
SDK README. We found it by grepping the Foundry samples repo.

If you are seeing intermittent agent timeouts that look like the
client and the server disagree on what happened, check the SDK
version first, then the connection-pool config, then the App Insights
client span. In that order.
