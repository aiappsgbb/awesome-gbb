# foundry-iq

Enterprise RAG for Microsoft Foundry via Foundry IQ — Azure AI Search Knowledge
Bases with agentic retrieval (multi-hop reasoning, query planning,
citation-backed responses).

## Roadmap

**Planned for v0.7.0 — private-endpoint posture audit
([#269](https://github.com/aiappsgbb/awesome-gbb/issues/269)).**
An `audit()` method that introspects each knowledge source's AI Search backing
and reports private-endpoint / public-network-access state. Threadlight's
`sibling-skills-map.md` already names the expected contract:
`audit(subscription_id, resource_group, private_endpoint_required=True) -> dict`.
Deferred from v0.6.0 because it intersects private-endpoint discovery
(`foundry-vnet-deploy`, an `issue_only` manual-validation skill) and needs its own
design conversation. This unblocks threadlight finding **MDL-010**, which **must
stay `kind: manual` until this method ships** — the threadlight map currently lists
MDL-010 without the `(planned)` tag, but no such method exists here yet.

## See also

- [`SKILL.md`](SKILL.md) — the skill contract
- [#269](https://github.com/aiappsgbb/awesome-gbb/issues/269) — the deferred work
