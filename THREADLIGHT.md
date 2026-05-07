# Threadlight: Design → Deploy → Demo

Threadlight is a **skill pipeline** for going from a vague customer requirement to a
working Foundry agent demo. It's built for rapid, repeatable PoC delivery.

```
Customer brief → threadlight-design → specs + agents + skills
                                              ↓
                    threadlight-deploy → azd up → working demo
                                              ↓
                      foundry-evals → score it    foundry-teams-bot → Teams exposure
```

## The Flow

| Step | Skill | What happens |
|------|-------|-------------|
| **1. Spec it** | `threadlight-design` | Discovery interview → SpecKit specification (business rules, data models, tool contracts, mock data) → AGENTS.md + Skills |
| **2. Mock it** | `foundry-mcp-aca` | Generate FastMCP mock server for inaccessible backend systems — customer sees real MCP tool calls with sample data |
| **3. Deploy it** | `threadlight-deploy` | Generate container.py, Dockerfile, azd project, wire mock MCP → `azd up` → hosted agent running |
| **4. Expose it** | `foundry-teams-bot` | Optional: add Teams bot frontend so customer can chat with the agent in Teams |
| **5. Eval it** | `foundry-evals` | Score the demo with Foundry evaluators using scenarios from the spec |
| **6. Land it** | `citadel-spoke-onboarding` | When the customer wants production: onboard onto Citadel landing zone with APIM gateway + governance |

## Fast-PoC Mode

For rapid demos, `threadlight-design` has a **fast-PoC mode** — minimal questions,
sensible defaults (keyless auth, mock MCP, stateless assumed), everything generated
in one pass. Every PoC ships with:

- ✅ Keyless auth (`DefaultAzureCredential`)
- ✅ Mock MCP server for inaccessible systems (customer swaps URL when onboarding)
- ✅ Eval dataset from spec scenarios
- ✅ Deployable scaffold (`azd up` ready)

## Companion Skills

The Threadlight pipeline leans on these companion skills for specialized tasks:

| Skill | Role in pipeline |
|-------|-----------------|
| `foundry-hosted-agents` | RBAC, identity model, agent.yaml schema, troubleshooting reference |
| `foundry-mcp-aca` | MCP server deployment — including mock MCP for demos |
| `foundry-evals` | Post-deployment evaluation patterns |
| `foundry-teams-bot` | Teams bot integration (optional) |
| `ghcp-hosted-agents` | Alternative runtime for long-running agents (>120s tool loops) |
| `foundry-iq` | Enterprise RAG with agentic retrieval (knowledge grounding) |
