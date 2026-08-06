"""Canonical live T3 verification probe for the AGT 4.1.0 / AF 1.13.0 pin.

Source of truth for the prose example in `../../SKILL.md § Verification status`.

This is the ONLY script in this skill that touches real Azure resources. It
proves, against a real `<ci-foundry-account>` deployment in
`<ci-resource-group>`, everything `contract_probe.py` cannot prove offline:

  - the 5 workflow-provided OIDC/Foundry environment variables are present
  - the exact pinned package versions are installed (mirrors, and adds exact
    ``*_VERSION=`` lines on top of, ``contract_probe.check_versions()``)
  - a real async ``DefaultAzureCredential`` acquires a real Entra token for
    the ``https://ai.azure.com/.default`` scope
  - a real ``FoundryChatClient`` runs one benign prompt through a real,
    governed ``Agent`` (the same real AGT factory middleware stack
    ``contract_probe.build_factory_stack`` assembles, plus a counting
    ``ChatMiddleware`` proven against the released AF 1.13 ``call_next()``
    no-argument shape) and gets back a real, non-empty response
  - the SAME real ``CapabilityGuardMiddleware`` instance deterministically
    allows the allowed tool exactly once and denies the denied tool before
    it ever executes, reusing ``contract_probe.exercise_capability_hook``
    verbatim rather than duplicating that hook path
  - the shared ``AuditLog`` accumulates real, integrity-verified evidence
    (CloudEvents) from that real allow/deny cycle

It deliberately reuses ``contract_probe.py``'s already-proven no-network
symbols (``EXPECTED_VERSIONS``, ``POLICY_DIR``, ``check_imports``,
``check_versions``, ``build_factory_stack``, ``exercise_capability_hook``)
via a normal local-module import rather than redefining any of that logic.

Pre-implementation API proof (see the skill's SKILL.md § Verification status
for the summary) empirically confirmed two things this probe relies on. Both
were independently re-litigated a second time, live, against the exact
pinned package set in a disposable venv — after a report claimed the
opposite of each — and both re-confirmed the original finding:

  1. Released AF 1.13's ``ChatMiddleware.process(self, context, call_next)``
     calls ``call_next()`` with NO arguments — data flows through the
     mutable ``context``, not through a return value or an argument to
     ``call_next``. Re-verified live: driving this exact probe's
     ``run_live_inference`` through the real AGT governance stack plus a
     ``ChatMiddlewareLayer``-composed stub client (the same base classes the
     real ``FoundryChatClient`` is actually built from) succeeds with the
     committed no-argument ``await call_next()``; the identical middleware
     changed to ``await call_next(context)`` instead raises a real
     ``TypeError: ...final_wrapper() takes 0 positional arguments but 1 was
     given`` from ``agent_framework``'s own ``ChatMiddlewarePipeline``. The
     one call site anywhere in the installed dependency tree that DOES pass
     an argument (``await call_next(request)`` in an unrelated
     ``agent_os/server/app.py`` HTTP handler) is the Starlette/FastAPI HTTP
     middleware convention, a different API entirely from
     ``agent_framework.ChatMiddleware``.
  2. The real ``CapabilityGuardMiddleware`` auto-logs to a supplied
     ``AuditLog`` on both allow (``tool_invocation`` start + complete) and
     deny (``tool_blocked``) — this probe never appends a manual fallback
     audit entry because the empirical proof showed one is never needed, and
     appending one would silently double-count real evidence the guard
     already recorded. Re-verified live at two levels of granularity: (a) in
     isolation, a bare ``cp.build_factory_stack`` + ``cp.exercise_capability_hook``
     cycle, with zero manual ``audit_log.log(...)`` calls anywhere, produces
     exactly 3 real CloudEvents from the guard alone (2
     ``ai.agentmesh.tool.invoked`` for the allowed execution's start/complete
     pair, 1 ``ai.agentmesh.tool.blocked`` for the denied execution) —
     confirmed both black-box, via ``export_cloudevents()`` before any manual
     log call, and by reading the guard's own installed source, whose legacy
     ``_process_v4`` path unconditionally calls ``self.audit_log.log(...)`` at
     all three points whenever ``self.audit_log`` is set; and (b) end-to-end,
     driving this probe's real, full ``run_live_inference`` then
     ``check_capability_hook_live`` sequence against one shared ``AuditLog``
     deterministically (reproduced identically across repeated runs)
     accumulates exactly 6 real CloudEvents: the first 3 (2
     ``ai.agentmesh.agent_invocation`` + 1 ``ai.agentmesh.policy.evaluation``)
     come from ``AuditTrailMiddleware``/``GovernancePolicyMiddleware`` --
     also members of the same real governance ``stack`` -- auto-logging the
     live chat call inside ``run_live_inference``'s own governed
     ``Agent.run()``; the next 3 are the guard's own allow/deny cycle from
     ``check_capability_hook_live``, as in (a).

Run directly, with the exact bounded package set from ``../upstream-pin.md``
installed and the 5 required environment variables present in the shell:

    python3 references/python/live_t3_probe.py

Never prints secret values, tokens, or identifiers — only presence/absence
markers and counts.
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from types import SimpleNamespace

# Normal local-module import that works when this file is executed by path:
# contract_probe.py lives in this same directory, so this makes `import
# contract_probe` resolve regardless of the caller's working directory,
# without redefining anything contract_probe.py already proves.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import contract_probe as cp  # noqa: E402  (sys.path mutated immediately above)

REQUIRED_ENV_VARS = (
    "AZURE_CLIENT_ID",
    "AZURE_TENANT_ID",
    "AZURE_SUBSCRIPTION_ID",
    "FOUNDRY_PROJECT_ENDPOINT",
    "FOUNDRY_MODEL_DEPLOYMENT",
)

# Exact distribution -> printed-line mapping for the approved pin. Values
# installed are re-validated against cp.EXPECTED_VERSIONS (the schema-
# validated source of truth); these are only the extra exact print lines
# this live probe's contract additionally requires. These literals are a
# static contract (grepped verbatim elsewhere) and must NOT be derived away
# -- check_exact_pinned_versions() below instead re-derives the expected
# line from EXACT_VERSION_LABELS + cp.EXPECTED_VERSIONS and asserts it
# equals the literal here, so a pin bump that forgets to update this dict
# fails loudly instead of silently printing stale evidence.
EXACT_VERSION_LINES = {
    "agent-governance-toolkit": "AGT_VERSION=4.1.0",
    "agent-framework-core": "AF_CORE_VERSION=1.13.0",
    "agent-framework-foundry": "AF_FOUNDRY_VERSION=1.10.4",
    "agent-framework-openai": "AF_OPENAI_VERSION=1.12.0",
    "azure-identity": "AZURE_IDENTITY_VERSION=1.25.3",
}

# Label prefix for each EXACT_VERSION_LINES entry (same keys). Used only to
# recompute f"{label}={cp.EXPECTED_VERSIONS[distribution]}" at runtime for
# the drift check -- never printed directly.
EXACT_VERSION_LABELS = {
    "agent-governance-toolkit": "AGT_VERSION",
    "agent-framework-core": "AF_CORE_VERSION",
    "agent-framework-foundry": "AF_FOUNDRY_VERSION",
    "agent-framework-openai": "AF_OPENAI_VERSION",
    "azure-identity": "AZURE_IDENTITY_VERSION",
}

ENTRA_SCOPE = "https://ai.azure.com/.default"

# Benign, harmless prompt only -- this probe must never send SQL/destructive/
# denied chat text to the real model.
BENIGN_PROMPT = "Reply with one short, friendly sentence greeting a colleague."

AGENT_INSTRUCTIONS = (
    "You are a benign assistant used only for a live verification smoke test. "
    "Respond briefly and harmlessly."
)


def check_oidc_env_present() -> None:
    """Require the 5 workflow-provided env vars to be non-empty.

    Existence only -- this never prints a value, so no secret or identifier
    ever reaches stdout from this check.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise AssertionError(f"missing required environment variables: {missing}")
    print("OIDC_ENV_PRESENT=1")


def check_exact_pinned_versions() -> None:
    """Reuse cp.check_versions(), then assert+print the exact approved lines.

    cp.check_versions() already asserts every distribution in
    cp.EXPECTED_VERSIONS against what's actually installed and prints its
    own ``distribution=version`` evidence lines; this adds the additional
    exact ``*_VERSION=`` lines this probe's contract requires on top of
    that reused evidence, re-checking the same installed versions rather
    than trusting cp's assertion alone.

    Before printing each hardcoded EXACT_VERSION_LINES literal, this also
    recomputes ``f"{label}={expected}"`` from EXACT_VERSION_LABELS and the
    CURRENT cp.EXPECTED_VERSIONS pin and asserts it equals the literal.
    Without this, a pin bump (cp.EXPECTED_VERSIONS changes, and the real
    installed package correctly moves with it) would satisfy the
    installed-vs-expected check below while this file's own hardcoded
    evidence string silently kept asserting the OLD version -- i.e. the
    pin could drift out from under the printed evidence with no failure
    anywhere. This check makes that drift fail loudly instead.
    """
    cp.check_versions()

    for distribution, exact_line in EXACT_VERSION_LINES.items():
        expected = cp.EXPECTED_VERSIONS[distribution]
        label = EXACT_VERSION_LABELS[distribution]
        computed_line = f"{label}={expected}"
        if exact_line != computed_line:
            raise AssertionError(
                f"EXACT_VERSION_LINES[{distribution!r}] is stale: hardcoded "
                f"{exact_line!r} != {computed_line!r} recomputed from the "
                f"current cp.EXPECTED_VERSIONS pin ({expected!r}); update the "
                "literal in EXACT_VERSION_LINES to match the new pin"
            )

        installed = importlib.metadata.version(distribution)
        if installed != expected:
            raise AssertionError(f"{distribution} installed {installed!r} != pinned {expected!r}")
        print(exact_line)


async def acquire_entra_token(cleanup: AsyncExitStack):
    """Construct a real async DefaultAzureCredential and acquire a real token.

    Uses the workflow-provided OIDC environment contract (AZURE_CLIENT_ID /
    AZURE_TENANT_ID / the federated-token env DefaultAzureCredential's own
    WorkloadIdentityCredential step reads) implicitly -- DefaultAzureCredential
    reads these from the environment itself; this probe passes no explicit
    kwargs so it takes the same code path a real consumer following SKILL.md
    would. Never prints the token itself.

    ``credential.close`` is registered on the shared ``cleanup`` stack
    immediately after construction and BEFORE ``get_token`` is awaited, so a
    raised or empty-token failure here still closes the credential exactly
    once via the stack's own unwind -- no broad try/except needed in this
    function, and no risk of the credential leaking if ``get_token`` fails.
    """
    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()
    cleanup.push_async_callback(credential.close)
    token = await credential.get_token(ENTRA_SCOPE)
    if not token.token:
        raise AssertionError("acquired Entra token was empty")
    print("ENTRA_TOKEN_ACQUIRED=1")
    return credential


async def run_live_inference(ns: SimpleNamespace, client, stack) -> int:
    """Run one real benign prompt through a real governed Agent.

    ``client`` is a real, already-constructed ``FoundryChatClient``. ``stack``
    is the real 3-middleware AGT governance stack from
    ``cp.build_factory_stack`` (``AuditTrailMiddleware``,
    ``GovernancePolicyMiddleware``, the ``CapabilityGuardMiddleware`` guard),
    attached to the same ``Agent`` alongside a counting ``ChatMiddleware`` so
    this one real model call is provably observed. Returns the exact number
    of real model calls the counting middleware saw.
    """
    from agent_framework import ChatContext, ChatMiddleware

    class CountingChatMiddleware(ChatMiddleware):
        """Counts real chat-completion calls made by the live FoundryChatClient.

        Proven against released AF 1.13's ``call_next()`` no-argument shape
        during this task's pre-implementation API proof: ``call_next`` takes
        no arguments and returns ``None`` -- the response is read back from
        the mutated ``context`` by the client's own middleware layer, not by
        this middleware.
        """

        def __init__(self) -> None:
            self.calls = 0

        async def process(self, context: ChatContext, call_next) -> None:
            self.calls += 1
            await call_next()

    counter = CountingChatMiddleware()
    agent = ns.Agent(
        client,
        AGENT_INSTRUCTIONS,
        name="live-t3-probe-agent",
        middleware=[*stack, counter],
    )

    response = await agent.run(BENIGN_PROMPT)

    if counter.calls < 1:
        raise AssertionError("counting chat middleware observed zero real model calls")
    response_text = (response.text or "").strip()
    if not response_text:
        raise AssertionError("live model response text was empty")
    if not response.response_id:
        raise AssertionError("live model response_id was empty")

    print("LIVE_RESPONSE_NONEMPTY=1")
    print("LIVE_RESPONSE_ID_PRESENT=1")
    print(f"MODEL_CALLS_AFTER_ALLOW={counter.calls}")
    return counter.calls


async def check_capability_hook_live(ns: SimpleNamespace, guard) -> None:
    """Deterministically exercise the SAME real guard used by the live Agent.

    Reuses ``cp.exercise_capability_hook`` verbatim (the exact real
    ``FunctionTool``/``.invoke(..., skip_parsing=True)`` path Task 1 and this
    task's Part A proved) rather than duplicating it here.
    """
    result = await cp.exercise_capability_hook(ns, guard)

    if result.allow_executions != 1:
        raise AssertionError(f"allowed tool executed {result.allow_executions} times, expected exactly 1")
    if not result.denial_observed:
        raise AssertionError("denied tool invocation did not raise MiddlewareTermination as expected")
    if result.deny_executions != 0:
        raise AssertionError(f"denied tool executed {result.deny_executions} times, expected exactly 0")

    print("ALLOWED_TOOL_EXECUTIONS=1")
    print("CAPABILITY_DENY_OBSERVED=1")
    print("DENIED_TOOL_EXECUTIONS=0")


def check_audit_integrity(audit_log) -> None:
    """Assert the shared AuditLog accumulated real, intact, EXACT evidence.

    Empirically confirmed during the pre-implementation API proof, and
    independently re-verified live end-to-end during this task's audit-API
    alignment pass (reproduced identically across repeated runs): by the
    time this runs, the shared audit log has already been auto-logged to
    twice over by real AGT middleware -- with zero manual
    ``audit_log.log(...)`` calls anywhere in this probe, since appending any
    would silently double-count real evidence the governance stack itself
    already recorded -- and holds exactly 6 real, non-fallback CloudEvents:

      - 3 from ``run_live_inference``'s own governed ``Agent.run()`` call,
        auto-logged by ``AuditTrailMiddleware``/``GovernancePolicyMiddleware``
        (also members of the same real ``stack``): 2
        ``ai.agentmesh.agent_invocation`` + 1 ``ai.agentmesh.policy.evaluation``
      - 3 from ``check_capability_hook_live``'s direct exercise of the SAME
        ``CapabilityGuardMiddleware`` guard: 2 ``ai.agentmesh.tool.invoked``
        (the allowed execution's start/complete pair) + 1
        ``ai.agentmesh.tool.blocked`` (the denied execution)
    """
    verified, detail = audit_log.verify_integrity()
    if not verified:
        raise AssertionError(f"AuditLog.verify_integrity() failed: {detail}")

    cloud_events = audit_log.export_cloudevents()
    if len(cloud_events) != 6:
        raise AssertionError(
            f"expected exactly 6 CloudEvents from the real run_live_inference + "
            f"check_capability_hook_live sequence, got {len(cloud_events)}: "
            f"{[event.get('type') for event in cloud_events]}"
        )

    print("CLOUDEVENTS_COUNT=6")
    print("AUDIT_INTEGRITY=1")


async def _run() -> None:
    check_oidc_env_present()
    check_exact_pinned_versions()

    # A single AsyncExitStack covers token acquisition, setup (imports,
    # factory stack, FoundryChatClient construction), and inference/hook/
    # audit -- every cleanup is registered via push_async_callback right
    # after the resource it belongs to is constructed, so a failure at ANY
    # point (including inside acquire_entra_token's own get_token call)
    # still triggers every callback registered so far, in LIFO order, with
    # no broad try/except and no risk of skipping a close because an
    # earlier step raised. AsyncExitStack also guarantees that if one
    # callback itself raises, the remaining registered callbacks still run
    # before the (possibly chained) exception propagates -- no double-close
    # risk either, since each resource registers its own close exactly
    # once.
    #
    # Released async close/context-manager semantics, re-verified live
    # against the exact pinned FoundryChatClient MRO (FunctionInvocationLayer,
    # ChatMiddlewareLayer, ChatTelemetryLayer, RawFoundryChatClient,
    # RawOpenAIChatClient, BaseChatClient): none of those classes define
    # __aenter__, __aexit__, or close -- Agent's own async-context-manager
    # support therefore has nothing client-side to close here, so it is
    # correctly NOT used. Because no `project_client=` kwarg is passed
    # below, FoundryChatClient constructs (and thus owns) its own real
    # async `AIProjectClient` internally, stored on `client.project_client`;
    # both it and `azure.identity.aio.DefaultAzureCredential` are confirmed
    # real, independent async context managers with their own `close()`.
    async with AsyncExitStack() as cleanup:
        credential = await acquire_entra_token(cleanup)

        ns = cp.check_imports()
        audit_log = ns.AuditLog()
        guard, audit_log, stack = cp.build_factory_stack(ns, audit_log=audit_log, agent_id="live-t3-probe-agent")

        client = ns.FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL_DEPLOYMENT"],
            credential=credential,
        )
        # Pushed AFTER credential.close, so the stack's LIFO unwind closes
        # the project client BEFORE the credential -- exactly once each.
        cleanup.push_async_callback(client.project_client.close)

        await run_live_inference(ns, client, stack)
        await check_capability_hook_live(ns, guard)
        check_audit_integrity(audit_log)

    # Printed only after the AsyncExitStack has fully and successfully
    # unwound both real close() calls. If either raises, AsyncExitStack
    # still runs the other registered callback (LIFO) but then re-raises
    # before this line is reached, so PASS is never emitted on a cleanup
    # failure and the process still exits nonzero.
    print("T3_PROBE=PASS")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
