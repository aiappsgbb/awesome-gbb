# Customer goal — `foundry-toolbox` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-toolbox`
skill works end-to-end against your CI Foundry project.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Azure SDK — read the skill's `SKILL.md` first, and follow
its documented contract.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on any of these
checks — `azure/login@v2` already validated the credentials upstream.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "AZURE_AI_ENDPOINT=${AZURE_AI_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any env var prints empty, the workflow's `env:` block is broken (AGENTS.md
§ 9.7 Pattern 11). That is a workflow bug, not a skill bug. Write the FAIL
marker (Step 2) with reason `auth context missing: <var-name>` and stop.

---

## Step 1 — The goal

Using the `foundry-toolbox` skill, create a toolbox version containing one
single tool, verify the create call returned a toolbox identifier (e.g.
toolbox name + version), then delete the toolbox version.

The skill documents several built-in tool types (`WebSearchTool`,
`AzureAISearchTool`, `MCPTool`, code interpreter, etc.). Pick the one the
skill describes as cheapest and that does NOT require an external resource
connection (no AI Search index, no MCP server URL, no extra subscription
plumbing). Use whatever tool the skill itself prescribes as the "smoke
test" / minimal choice — if no such recommendation is documented, pick
the tool with the smallest set of required init args. A no-arg tool like
`WebSearchTool()` or a built-in code interpreter is preferred over any
tool that needs a connection string or resource ID.

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, the exact `create_version` call signature, and how to delete
a toolbox version. Read it before you write any code. Note: per SKILL.md
the SDK exposes `project.beta.toolboxes.create_version(...)` —
`create_toolbox_version` is the older Learn-doc name and may not exist on
the installed SDK. If you fall back to a REST call instead of the SDK, the
`Foundry-Features: Toolboxes=V1Preview` header is mandatory.

If the skill's instructions conflict with anything you remember from
training data, the skill wins.

Foundry project endpoint: `$AZURE_AI_ENDPOINT`
Model deployment available in that project: `gpt-5.4-mini` (only needed if
the chosen tool requires a model)

Give every Azure resource you create a CI-safe name that includes a short
UUID suffix (Pattern 15.3) so parallel runs don't collide. Suggested pattern:
`ci-smoke-tbx-$(uuidgen | cut -c1-8)`.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write the
marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (all of: toolbox version created, identifier returned, version
deleted):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-toolbox-smoke-result
```

On ANY failure (auth, skill not found, SDK error, create returned no
identifier, cleanup failure):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-toolbox-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
