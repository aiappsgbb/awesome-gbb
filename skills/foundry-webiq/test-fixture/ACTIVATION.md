# Activating the `foundry-webiq` live CI fixture

The Copilot-CLI live fixture for this skill is **dormant**. It is parked at
`consumer_prompt.md.pending` (not `consumer_prompt.md`) on purpose:

- `scripts/validate-skills.py` (Check 3) **errors** if a skill has a
  `test-fixture/consumer_prompt.md` but no `.github/skill-deps.yml` entry.
- Adding the skill-deps entry **auto-enrolls** the skill in the live
  `copilot-cli-matrix` job.
- That job would **fail** today because CI does not hold a `WEBIQ_API_KEY`
  secret and the gated Web IQ contract (header name, scope, endpoint, tool
  names, REST route, response schema) has not been confirmed against the
  live service.

So the fixture is fully authored but kept inert until a human can satisfy
AGENTS.md § 2.8 / § 2.9 (live-test-before-merge) for real.

## Activation steps (human, one-time)

1. **Get Web IQ access + a credential.** Approved via
   [`aka.ms/webiq-waitlist`](https://aka.ms/webiq-waitlist). Obtain an API
   key (and/or an Entra app authorized for the Web IQ scope).

2. **Confirm the gated contract.** Sign into
   <https://webiq.microsoft.ai/documentation/> and record the real values
   (see SKILL.md § "What you must capture from your Web IQ docs"):
   - `WEBIQ_MCP_ENDPOINT` (streamable-HTTP MCP URL)
   - `WEBIQ_API_KEY_HEADER` (exact header name for the key)
   - `WEBIQ_ENTRA_SCOPE` (if using Entra)
   - REST route + response field names (only if you exercise the REST path)
   Update the `# CONFIRM:` markers in the reference Python if the response
   field names differ from the conservative defaults.

3. **Add the CI secrets.** In repo *Settings → Secrets and variables →
   Actions*, add `WEBIQ_API_KEY`, `WEBIQ_MCP_ENDPOINT`, and
   `WEBIQ_API_KEY_HEADER` (plus `WEBIQ_ENTRA_SCOPE` for the Entra variant).
   Add matching placeholders to `.env.ci.example` (already stubbed) and your
   local `.env.ci`.

4. **Wire the secrets into the workflow.** In
   `.github/workflows/skill-test.yml`, add the `WEBIQ_*` env vars to the
   `copilot-cli-matrix` step env block (both the main run and the retry
   steps — Pattern 11 byte-identical env contract).

5. **Activate the fixture file.** Rename
   `consumer_prompt.md.pending` → `consumer_prompt.md`.

6. **Register the skill for the matrix.** Add to `.github/skill-deps.yml`:
   ```yaml
   foundry-webiq:
     depends_on: [foundry-hosted-agents]
   ```

7. **Run + stabilize.** Push and confirm the `foundry-webiq` matrix leg goes
   green. Once it passes, update the pin's `last_validated`, close the
   `gated-contract` known issue in `references/upstream-pin.md`, and note the
   live evidence in the PR per AGENTS.md § 2.9.
