# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

## What Are Skills?

Skills are reusable, composable building blocks for AI agents. Each Skill encodes domain expertise as a structured markdown file (`SKILL.md`) that an agentic runtime — such as GitHub Copilot CLI, Microsoft Foundry, or any compatible host — can load and execute.

## Repository Structure

```
skills/
  <skill-name>/
    SKILL.md          # Skill definition (frontmatter + instructions)
    README.md         # Optional: extended docs, examples, changelog
```

## Skills Catalog

| Skill | Description |
|-------|-------------|
| [threadlight-design](skills/threadlight-design/) | Design agentic workflows — turn any business process into a structured folder of Skills + AGENTS.md, ready for Foundry deployment |
| [threadlight-deploy](skills/threadlight-deploy/) | Generate all deployment artifacts for Microsoft Foundry Hosted Agents (container.py, Dockerfile, azd project, Teams bot) |
| [foundry-hosted-agents](skills/foundry-hosted-agents/) | Reference guide for the refreshed Foundry hosted agents preview (April 2026) — Agent + FoundryChatClient + ResponsesHostServer pattern, RBAC, troubleshooting |
| [pptx](skills/pptx/) | Generate professional PowerPoint (PPTX) presentations using python-pptx with dark/light themes |
| [auto-demo-producer](skills/auto-demo-producer/) | Produce narrated video demos of web apps automatically — Playwright recording + edge-tts narration + ffmpeg assembly |

## Contributing

1. **Fork & branch** — create a feature branch from `main`.
2. **Add your Skill** — place it under `skills/<your-skill-name>/SKILL.md`.
3. **Open a PR** — describe the scenario, target audience, and any dependencies.
4. **Peer review** — at least one GBB team member must approve before merge.

### Skill Quality Checklist

- [ ] Clear, concise `description` in frontmatter
- [ ] Well-defined trigger phrases (when should the skill activate?)
- [ ] Actionable instructions (the agent *does* the work, not just advises)
- [ ] No secrets or credentials embedded
- [ ] Tested with at least one agentic runtime

## License

This project is licensed under the [MIT License](LICENSE).

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
