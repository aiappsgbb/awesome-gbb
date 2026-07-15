# Customer goal — `foundry-agt` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-agt` skill works
end-to-end on a CI runner with **no Azure resources, no model deployments,
no ACA, no dataplane calls** — `foundry-agt` is in-process MAF middleware
that fires before any model dispatch on a denied capability, so the entire
smoke runs locally in a Python venv.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Agent Governance Toolkit (AGT) or the Microsoft Agent
Framework (MAF) — read the skill's `SKILL.md` first, and follow its
documented contract.

---

## Step 0 — Auth context (show, do not assert)

`foundry-agt` itself does **no Azure dataplane calls** in the in-process
middleware path you're exercising. The inventory below is printed only for
run-log consistency with other fixtures in the catalog — do NOT gate flow
on any of these checks (Pattern 17), and an empty `az account show` cache
is not a failure for this skill.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited — fine; this skill does no Azure calls)"
```

---

## Step 1 — The goal

Using the `foundry-agt` skill, prove that the in-process MAF middleware
integration surface documented in `SKILL.md` is wired correctly against
the pinned versions of AGT and the Microsoft Agent Framework. Specifically
prove all of the following:

1. **The documented install produces a working `agt` CLI.** Use the exact
   `pip install` command the skill prescribes (note the `[full]` extras —
   they are required for `agt doctor` / `agt verify` to work). Then run
   `agt --version`, `agt doctor`, and `agt verify` and confirm `agt verify`
   prints `OWASP ASI 2026` somewhere in its output.

2. **The five public surfaces the skill documents are importable and
   their signatures are stable.** Print `inspect.signature(...)` for each
   of these symbols to stdout — the audit trail cites these prints as
   evidence of the actual 3.7.x / 1.7.x API surface:
   - `agent_os.integrations.maf_adapter.create_governance_middleware`
   - `agent_os.policies.PolicyEvaluator.evaluate`
   - `agent_os.policies.PolicyEvaluator.load_policies`
   - `agentmesh.governance.AuditLog.log`
   - `agentmesh.governance.AuditLog.export_cloudevents`
   - `agent_framework.Agent.__init__`

3. **MAF accepts `middleware` as a constructor parameter.** The skill's
   integration story is `Agent(..., middleware=create_governance_middleware(...))`,
   so the literal parameter name `middleware` MUST appear in the
   `Agent.__init__` signature. Assert this — if it's missing, the
   integration contract is broken regardless of whether AGT works in
   isolation.

4. **`create_governance_middleware()` returns a middleware stack of
   length ≥ 2.** Call the factory with `policy_directory` pointing at
   `skills/foundry-agt/references/policies` (the canonical policies
   shipped with the skill), `allowed_tools=[]`, `denied_tools=[]`, a
   CI-safe `agent_id`, and **`enable_rogue_detection=False`** (Known
   Issue #4 in the SKILL — RogueDetection needs a pre-built capability
   profile and breaks without it). Assert the return value is a `list`
   of length ≥ 2.

5. **The canonical policy YAML loads and evaluates the expected way.**
   Load `skills/foundry-agt/references/policies/default.yaml` via
   `PolicyEvaluator.load_policies(...)` (structural — a malformed YAML
   would raise). Then run two policy evaluations through the loaded
   evaluator:
   - A SQL-injection-shaped message containing `DROP TABLE users` MUST
     produce a `deny` decision (per `default.yaml`'s `block-sql-injection`
     rule on field `message`).
   - A benign greeting (`"hello"`) MUST produce a non-deny decision.

   Because `PolicyEvaluator`'s decision return type has evolved across
   releases (could be a dataclass, dict, or plain string), introspect
   the returned object across several plausible attribute names —
   `action`, `decision`, `effect`, `result`, `allowed`, `message`,
   `reason`, plus `str(decision).lower()` as a fallback — and assert
   that the resulting text-form contains `"deny"` (SQL case) or does
   NOT contain `"deny"` (benign case). A version-tolerant check
   prevents an `allow`/no-op object from silently passing.

6. **AuditLog hash-chain round-trip.** Create an `AuditLog`, append two
   entries via `log(...)`, call `verify_integrity()` and assert the
   result is truthy, then call `export_cloudevents()` and assert it
   returns an iterable of length 2. This is the skill's headline
   tamper-evidence story — it must work.

7. **`AuditLog` produces a valid runtime audit evidence record.**

   Using the same `AuditLog` from step 6 (the hash-chain round-trip),
   confirm that the evidence export contract — documented in
   `skills/foundry-agt/SKILL.md § Runtime audit evidence` and the
   run-book at `skills/foundry-agt/references/runtime-audit-export.md`
   — holds end-to-end:

   a. Create an `AuditLog`. Append **one ALLOW event** and **one DENY
      event** using `log(...)` calls. Use generic placeholder values for
      all fields — no real secrets, no real tool argument values.

   b. Call `verify_integrity()` and assert the result is truthy.

   c. Call `export_cloudevents()` and assert it returns an iterable of
      length 2.

   d. Import `build_evidence` and `write_evidence` from
      `skills/foundry-agt/references/python/runtime_evidence.py`
      (verbatim — do NOT redefine).

   e. Construct `safe_events` containing only the ten required fields for
      each event (`event_id`, `timestamp`, `event_type`, `agent_id`,
      `session_id`, `policy_name`, `tool_name`, `decision`, `reason`,
      `evaluation_ms`). Do NOT include prompt text, model responses, tool
      argument values, credentials, or personal data.

   f. Call `build_evidence(safe_events, ...)` and assert:
      - `evidence["allow_count"] >= 1`
      - `evidence["deny_count"] >= 1`
      - `evidence["integrity_verified"] is True`
      - `evidence["schema"] == "foundry-agt-runtime-evidence/v1"`

   g. Call `write_evidence("specs/agt-runtime-evidence.json", evidence)`.

   h. Read back `specs/agt-runtime-evidence.json` and assert its contents
      pass all four checks in (f) above.

   i. Assert that the file's raw JSON does NOT contain any of these
      sentinel strings: `"DROP TABLE"`, `"credential-leak-sentinel-7f9c"`,
      `"api_key="`. These sentinels are the canonical negative test for
      accidental sensitive-data leakage into the committed artifact.

Anchor every filesystem reference to `$GITHUB_WORKSPACE` (`cd
"$GITHUB_WORKSPACE"` upfront) so the Python script can find the policy
YAML regardless of where the venv ends up. Read
`skills/foundry-agt/SKILL.md` for the canonical import paths,
factory contract, and Known Issues — and read
`skills/foundry-agt/references/maf-middleware-snippet.py` for the
already-vetted shape of the integration code. If anything you remember
from training data conflicts with the skill, the skill wins.

There are **no Azure resources to clean up** — this is an in-process
smoke. Process exit handles all teardown.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after the Python smoke prints all assertions and
signature dumps — is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

On success (all of: `pip install` succeeded, `agt --version` /
`agt doctor` / `agt verify` all returned 0, `agt verify` output
contained `OWASP ASI 2026`, all 6 signatures printed, the `middleware`
parameter assertion held, the factory returned a list of length ≥ 2,
`load_policies` did not raise, both policy evaluations matched the
expected text, the AuditLog round-trip held, the runtime audit evidence
record was written to `specs/agt-runtime-evidence.json` with
`allow_count >= 1`, `deny_count >= 1`, `integrity_verified true`, and no
sentinel secrets present):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-agt-smoke-result
```

On ANY failure (install error, missing CLI, missing signature, broken
integration contract, policy decision mismatched, AuditLog integrity
broken):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-agt-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
