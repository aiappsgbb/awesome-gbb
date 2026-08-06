"""Canonical live-import + shape contract probe for the AGT 4.1.0 pin.

Source of truth for the prose example in `../../SKILL.md § Wiring snippet`.

This is the durable regression harness behind the ``agent-governance-toolkit``
4.1.0 / Agent Framework Core 1.13.0 pin (see ``../upstream-pin.md``). It is
executed verbatim by ``validation.script`` on every refresh and asserts,
against the REAL installed packages — no mocks of AGT or MAF internals — that:

  - every pinned distribution is installed at its exact version
  - the public symbols this skill's SKILL.md tells consumers to import
    actually exist
  - the constructor / factory signatures SKILL.md's prose depends on still
    carry the parameters that prose promises
  - a stub ``FoundryChatClient`` constructs with no network access
  - a stub chat response round-trips through a real ``Agent.run``
  - every current policy YAML (``../policies/*.yaml``) denies/allows the
    inputs SKILL.md documents, including all four SSN separator forms, when
    evaluated in isolation via ``PolicyEvaluator.evaluate``
  - ``AuditLog`` integrity verification and CloudEvents export both work
  - the three-middleware governance factory stack assembles correctly
  - the real ``GovernancePolicyMiddleware.process`` hook — driven through a
    real ``AgentContext`` built from a real ``Agent``/``Message``, the exact
    shape the legacy v4 evaluation context actually has — calls ``call_next``
    exactly once for a benign message and raises ``MiddlewareTermination``
    with zero ``call_next`` calls for the destructive-SQL and inbound-SSN
    policy patterns
  - the real ``CapabilityGuardMiddleware.process`` hook allows exactly the
    allowed tool and denies exactly the denied tool
  - ``../maf-middleware-snippet.py``'s ``build_governed_agent`` factory
    still returns a real, middleware-wired ``Agent`` whose
    ``allowed_tools=None`` default is preserved as "no allowlist" (not
    coerced to a deny-all ``[]``) and whose middleware stack keeps the
    factory's ``AuditTrail -> GovernancePolicy -> CapabilityGuard`` order

Run directly after installing the exact bounded package set from
``../upstream-pin.md`` into an active virtual environment:

    python3 references/python/contract_probe.py
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

POLICY_DIR = Path(__file__).resolve().parents[1] / "policies"
SNIPPET = Path(__file__).resolve().parents[1] / "maf-middleware-snippet.py"

# Exact versions pinned in ../upstream-pin.md. Keep in sync — the pin file
# is the schema-validated source of truth; this dict is the executable
# mirror of it.
EXPECTED_VERSIONS = {
    "agent-governance-toolkit": "4.1.0",
    "agent-governance-toolkit-core": "4.1.0",
    "agent-governance-toolkit-integrations": "4.1.0",
    "agent-governance-toolkit-cli": "4.1.0",
    "agent-governance-toolkit-protocols": "4.1.0",
    "agent-framework-core": "1.13.0",
    "agent-framework-foundry": "1.10.4",
    "agent-framework-openai": "1.12.0",
    "azure-identity": "1.25.3",
}

STUB_PROJECT_ENDPOINT = "https://stub.services.ai.azure.com/api/projects/stub-project"
STUB_MODEL = "stub-model"
SSN_FORMATS = ("123-45-6789", "123 45 6789", "123.45.6789", "123456789")


class StubCredential:
    """Async credential that never touches the network."""

    async def get_token(self, *scopes: str, **kwargs: object):
        from azure.core.credentials import AccessToken

        # 4102444800 == 2100-01-01T00:00:00Z: far enough out that no caller
        # in this probe will ever observe an expiry.
        return AccessToken("stub-token", 4102444800)

    async def close(self) -> None:
        return None


def check_versions() -> None:
    """Assert every pinned distribution is installed at its exact version."""
    for distribution, expected in EXPECTED_VERSIONS.items():
        installed = importlib.metadata.version(distribution)
        print(f"{distribution}={installed}")
        if installed != expected:
            raise AssertionError(
                f"{distribution} installed version {installed!r} != pinned {expected!r}"
            )


def check_imports() -> SimpleNamespace:
    """Import every real symbol SKILL.md tells consumers to import."""
    from agent_framework import (
        Agent,
        AgentContext,
        ChatResponse,
        FunctionInvocationContext,
        FunctionTool,
        Message,
        MiddlewareTermination,
    )
    from agent_framework.foundry import FoundryChatClient
    from agent_os.integrations.maf_adapter import (
        AuditTrailMiddleware,
        CapabilityGuardMiddleware,
        GovernancePolicyMiddleware,
        create_governance_middleware,
    )
    from agent_os.policies import PolicyEvaluator
    from agentmesh.governance import AuditLog
    from azure.core.credentials import AccessToken

    return SimpleNamespace(
        Agent=Agent,
        AgentContext=AgentContext,
        ChatResponse=ChatResponse,
        FunctionInvocationContext=FunctionInvocationContext,
        FunctionTool=FunctionTool,
        Message=Message,
        MiddlewareTermination=MiddlewareTermination,
        FoundryChatClient=FoundryChatClient,
        AuditTrailMiddleware=AuditTrailMiddleware,
        CapabilityGuardMiddleware=CapabilityGuardMiddleware,
        GovernancePolicyMiddleware=GovernancePolicyMiddleware,
        create_governance_middleware=create_governance_middleware,
        PolicyEvaluator=PolicyEvaluator,
        AuditLog=AuditLog,
        AccessToken=AccessToken,
    )


def check_signatures(ns: SimpleNamespace) -> None:
    """Assert the constructor / factory parameters SKILL.md's prose depends on."""
    factory_params = set(inspect.signature(ns.create_governance_middleware).parameters)
    required_factory_params = {
        "policy_directory",
        "allowed_tools",
        "denied_tools",
        "agent_id",
        "enable_rogue_detection",
        "audit_log",
    }
    missing_factory_params = required_factory_params - factory_params
    if missing_factory_params:
        raise AssertionError(
            f"create_governance_middleware is missing parameters: {sorted(missing_factory_params)}"
        )

    agent_params = set(inspect.signature(ns.Agent.__init__).parameters)
    missing_agent_params = {"client", "middleware"} - agent_params
    if missing_agent_params:
        raise AssertionError(f"Agent.__init__ is missing parameters: {sorted(missing_agent_params)}")

    foundry_params = set(inspect.signature(ns.FoundryChatClient.__init__).parameters)
    missing_foundry_params = {"project_endpoint", "model", "credential"} - foundry_params
    if missing_foundry_params:
        raise AssertionError(
            f"FoundryChatClient.__init__ is missing parameters: {sorted(missing_foundry_params)}"
        )

    chat_response_params = set(inspect.signature(ns.ChatResponse.__init__).parameters)
    missing_chat_response_params = {"messages", "response_id"} - chat_response_params
    if missing_chat_response_params:
        raise AssertionError(
            f"ChatResponse.__init__ is missing parameters: {sorted(missing_chat_response_params)}"
        )

    print("SIGNATURE_CONTRACT=PASS")


async def check_stub_foundry_construction(ns: SimpleNamespace) -> None:
    """Construct a real FoundryChatClient against a stub endpoint — no network."""
    client = ns.FoundryChatClient(
        project_endpoint=STUB_PROJECT_ENDPOINT,
        model=STUB_MODEL,
        credential=StubCredential(),
    )
    if client.model != STUB_MODEL:
        raise AssertionError(f"FoundryChatClient.model was {client.model!r}, expected {STUB_MODEL!r}")
    print("STUB_FOUNDRY_CONSTRUCTION=PASS")


async def check_stub_response_shape(ns: SimpleNamespace) -> None:
    """Round-trip a stub chat response through a real Agent.run."""

    class StubChatClient:
        async def get_response(self, messages, **kwargs: object):
            return ns.ChatResponse(
                messages=[ns.Message("assistant", ["READY"])],
                response_id="stub-response-id",
                model=STUB_MODEL,
                finish_reason="stop",
            )

    agent = ns.Agent(StubChatClient(), "You are a probe agent.", name="probe")
    response = await agent.run("probe")
    if response.text != "READY":
        raise AssertionError(f"Agent.run response text was {response.text!r}, expected 'READY'")
    if response.response_id != "stub-response-id":
        raise AssertionError(
            f"Agent.run response_id was {response.response_id!r}, expected 'stub-response-id'"
        )
    print("STUB_RESPONSE_SHAPE=PASS")


def check_policies(ns: SimpleNamespace) -> None:
    """Load every current policy YAML and assert the documented decisions."""
    evaluator = ns.PolicyEvaluator()
    evaluator.load_policies(str(POLICY_DIR))

    drop_table = evaluator.evaluate({"message": "DROP TABLE users"})
    if drop_table.action != "deny":
        raise AssertionError(f"'DROP TABLE users' was not denied: {drop_table.action!r}")

    hello = evaluator.evaluate({"message": "hello"})
    if hello.action != "allow":
        raise AssertionError(f"'hello' was not allowed: {hello.action!r}")

    long_message = evaluator.evaluate({"message": "a" * 16001})
    if long_message.action != "deny":
        raise AssertionError(f"16,001-char message was not denied: {long_message.action!r}")

    for ssn in SSN_FORMATS:
        decision = evaluator.evaluate({"message": f"my ssn is {ssn}"})
        if decision.action != "deny":
            raise AssertionError(f"SSN format {ssn!r} was not denied: {decision.action!r}")

    print("POLICY_EVALUATION=PASS")


def check_audit_log(ns: SimpleNamespace) -> None:
    """Log two probe events and assert integrity + CloudEvents export."""
    audit_log = ns.AuditLog()
    audit_log.log(
        event_type="tool.invoked",
        agent_did="contract-probe-agent",
        action="safe_tool.invoke",
        outcome="success",
    )
    audit_log.log(
        event_type="tool.denied",
        agent_did="contract-probe-agent",
        action="dangerous_tool.invoke",
        outcome="denied",
    )

    verified, detail = audit_log.verify_integrity()
    if not verified:
        raise AssertionError(f"AuditLog.verify_integrity() failed: {detail}")

    cloud_events = audit_log.export_cloudevents()
    if len(cloud_events) != 2:
        raise AssertionError(f"expected exactly 2 CloudEvents, got {len(cloud_events)}")

    print("AUDIT_LOG=PASS")


def build_factory_stack(ns: SimpleNamespace, *, audit_log=None, agent_id: str = "contract-probe-agent"):
    """Assemble the governance middleware factory stack and select the guard.

    Accepts an optional pre-created ``audit_log`` so callers that need to
    observe the guard's own audit evidence afterward (e.g. ``live_t3_probe.py``,
    which shares one ``AuditLog`` across live inference and the capability
    hook exercise) can supply it; a fresh one is created when omitted so this
    function's original no-argument behavior is unchanged. Returns
    ``(guard, audit_log, stack)`` — the audit log and the full assembled
    middleware stack (``AuditTrailMiddleware``, ``GovernancePolicyMiddleware``,
    the returned ``guard``) are always returned so a caller that needs to wire
    the whole real stack onto a real ``Agent`` (as ``live_t3_probe.py`` does)
    does not have to reassemble it separately.
    """
    audit_log = audit_log if audit_log is not None else ns.AuditLog()
    stack = ns.create_governance_middleware(
        policy_directory=str(POLICY_DIR),
        allowed_tools=["safe_tool"],
        denied_tools=["dangerous_tool"],
        agent_id=agent_id,
        enable_rogue_detection=False,
        audit_log=audit_log,
    )

    types_present = {type(middleware).__name__ for middleware in stack}
    required_types = {"AuditTrailMiddleware", "GovernancePolicyMiddleware"}
    missing_types = required_types - types_present
    if missing_types:
        raise AssertionError(f"factory stack is missing {sorted(missing_types)}: got {sorted(types_present)}")

    guard = next(
        (middleware for middleware in stack if isinstance(middleware, ns.CapabilityGuardMiddleware)),
        None,
    )
    if guard is None:
        raise AssertionError(f"factory stack has no CapabilityGuardMiddleware: got {sorted(types_present)}")

    print("FACTORY_STACK=PASS")
    return guard, audit_log, stack


async def check_policy_middleware(ns: SimpleNamespace, stack) -> None:
    """Drive the real ``GovernancePolicyMiddleware.process`` hook end to end.

    Selects the ``GovernancePolicyMiddleware`` instance ``build_factory_stack``
    already assembled (no duplicate factory construction) and drives it
    through a real ``AgentContext`` built from a real ``Agent`` and a real
    ``Message`` — the exact legacy v4 evaluation-context shape
    (``agent``/``message``/``timestamp``/``stream``/``message_count``, built
    internally by ``GovernancePolicyMiddleware._process_v4``), not a
    synthetic dict shaped like a tool-call payload. This is what makes the
    proof real: the deleted ``hitl-gate.yaml`` policy's ``tool_name`` /
    per-tool-argument fields never appear in that context, so a rule keyed
    on them could never match here or in a real deployed agent.
    """
    policy_middleware = next(
        (middleware for middleware in stack if isinstance(middleware, ns.GovernancePolicyMiddleware)),
        None,
    )
    if policy_middleware is None:
        raise AssertionError("factory stack has no GovernancePolicyMiddleware to exercise")

    class StubChatClient:
        async def get_response(self, messages, **kwargs: object):
            raise AssertionError("call_next should be stubbed, not the real chat client")

    agent = ns.Agent(StubChatClient(), "You are a probe agent.", name="policy-middleware-probe")

    async def drive(text: str) -> tuple[int, bool, str | None]:
        calls = 0

        async def call_next() -> None:
            nonlocal calls
            calls += 1

        context = ns.AgentContext(agent=agent, messages=[ns.Message("user", [text])])
        terminated = False
        reason: str | None = None
        try:
            await policy_middleware.process(context, call_next)
        except ns.MiddlewareTermination as exc:
            terminated = True
            reason = str(exc)
        return calls, terminated, reason

    hello_calls, hello_terminated, _ = await drive("hello")
    if hello_calls != 1:
        raise AssertionError(f"benign message called call_next {hello_calls} times, expected exactly 1")
    if hello_terminated:
        raise AssertionError("benign message was terminated by policy middleware, expected allow")

    sql_calls, sql_terminated, sql_reason = await drive("DROP TABLE users")
    if sql_calls != 0:
        raise AssertionError(f"destructive SQL called call_next {sql_calls} times, expected exactly 0")
    if not sql_terminated:
        raise AssertionError("destructive SQL was not terminated by policy middleware")
    if sql_reason != "Destructive SQL pattern blocked by default policy.":
        raise AssertionError(f"destructive SQL termination reason was {sql_reason!r}")

    ssn_calls, ssn_terminated, ssn_reason = await drive("my ssn is 123-45-6789")
    if ssn_calls != 0:
        raise AssertionError(f"inbound SSN called call_next {ssn_calls} times, expected exactly 0")
    if not ssn_terminated:
        raise AssertionError("inbound SSN was not terminated by policy middleware")
    if ssn_reason != "US SSN pattern detected.":
        raise AssertionError(f"inbound SSN termination reason was {ssn_reason!r}")

    print("POLICY_MIDDLEWARE=PASS")


@dataclass(frozen=True)
class CapabilityHookExerciseResult:
    """Outcome of exercising a real ``CapabilityGuardMiddleware.process`` hook."""

    allow_executions: int
    deny_executions: int
    denial_observed: bool
    allowed_result: object


async def exercise_capability_hook(ns: SimpleNamespace, guard) -> CapabilityHookExerciseResult:
    """Drive ``guard.process`` through one real allow and one real deny.

    Constructs a real ``safe_tool`` and a real ``dangerous_tool``, each backed
    by an actual zero-arg Python function with its own execution counter,
    wraps them as ``agent_framework.FunctionTool(..., func=...)``, builds real
    ``FunctionInvocationContext`` objects, and drives each through
    ``guard.process(context, call_next)`` where ``call_next`` invokes the tool
    via ``FunctionTool.invoke(arguments={}, context=context,
    skip_parsing=True)`` — the exact tool-execution path a real governed agent
    takes when it decides to call a tool. This is the single source of truth
    for the capability-hook exercise: ``check_capability_hook`` below and
    ``live_t3_probe.py``'s live capability-hook check both call this helper
    directly instead of duplicating the hook-exercise logic.
    """
    allow_executions = 0

    def _safe_tool_fn() -> str:
        nonlocal allow_executions
        allow_executions += 1
        return "safe-result"

    deny_executions = 0

    def _dangerous_tool_fn() -> str:
        nonlocal deny_executions
        deny_executions += 1
        return "dangerous-result"

    safe_tool = ns.FunctionTool(name="safe_tool", description="allowed probe tool", func=_safe_tool_fn)
    dangerous_tool = ns.FunctionTool(
        name="dangerous_tool", description="denied probe tool", func=_dangerous_tool_fn
    )

    allow_context = ns.FunctionInvocationContext(function=safe_tool, arguments={})

    async def allow_call_next() -> None:
        allow_context.result = await safe_tool.invoke(arguments={}, context=allow_context, skip_parsing=True)

    await guard.process(allow_context, allow_call_next)

    deny_context = ns.FunctionInvocationContext(function=dangerous_tool, arguments={})

    async def deny_call_next() -> None:
        deny_context.result = await dangerous_tool.invoke(
            arguments={}, context=deny_context, skip_parsing=True
        )

    denial_observed = False
    try:
        await guard.process(deny_context, deny_call_next)
    except ns.MiddlewareTermination:
        denial_observed = True

    return CapabilityHookExerciseResult(
        allow_executions=allow_executions,
        deny_executions=deny_executions,
        denial_observed=denial_observed,
        allowed_result=allow_context.result,
    )


async def check_capability_hook(ns: SimpleNamespace, guard) -> None:
    """Exercise the real CapabilityGuardMiddleware.process hook, allow and deny."""
    result = await exercise_capability_hook(ns, guard)

    if result.allowed_result != "safe-result":
        raise AssertionError(f"allowed function result was {result.allowed_result!r}, expected 'safe-result'")
    if not result.denial_observed:
        raise AssertionError("denied function did not raise MiddlewareTermination")

    # Assert the exact counts BEFORE printing the literal lines below — the
    # print statements are gated by real behavioral checks, not hardcoded
    # for their own sake.
    if result.allow_executions != 1:
        raise AssertionError(f"allowed function executed {result.allow_executions} times, expected exactly 1")
    if result.deny_executions != 0:
        raise AssertionError(f"denied function executed {result.deny_executions} times, expected exactly 0")
    print("CAPABILITY_HOOK_ALLOW_EXECUTIONS=1")
    print("CAPABILITY_HOOK_DENY_EXECUTIONS=0")
    print("CAPABILITY_HOOK=PASS")


async def check_snippet_import(ns: SimpleNamespace) -> None:
    """Import ../maf-middleware-snippet.py and build real governed Agents from it."""
    spec = importlib.util.spec_from_file_location("maf_middleware_snippet", SNIPPET)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load a module spec from {SNIPPET}")
    snippet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(snippet)

    agent = snippet.build_governed_agent(
        name="compat-probe",
        instructions="Construction probe.",
        chat_client=object(),
        policy_dir=POLICY_DIR,
        allowed_tools=["safe_tool"],
        denied_tools=["dangerous_tool"],
    )
    if not isinstance(agent, ns.Agent):
        raise AssertionError(f"build_governed_agent returned {type(agent)!r}, expected a real Agent")
    if not agent.middleware:
        raise AssertionError("build_governed_agent returned an Agent with no middleware")

    print("SNIPPET_IMPORT=PASS")

    # Default-semantics + order proof: allowed_tools=None must remain "no
    # allowlist" (allow every tool not on denied_tools), never coerced to a
    # deny-all [] — and the factory's
    # AuditTrail -> GovernancePolicy -> CapabilityGuard order must be
    # preserved by the in-place replacement inside build_governed_agent
    # (no insert(0, ...) reordering ahead of AuditTrailMiddleware).
    default_agent = snippet.build_governed_agent(
        name="default-semantics-probe",
        instructions="Default-semantics probe.",
        chat_client=object(),
        policy_dir=POLICY_DIR,
        allowed_tools=None,
        denied_tools=["dangerous_tool"],
    )
    middleware_type_names = [type(middleware).__name__ for middleware in default_agent.middleware]
    expected_order = ["AuditTrailMiddleware", "GovernancePolicyMiddleware", "CapabilityGuardMiddleware"]
    if middleware_type_names != expected_order:
        raise AssertionError(
            f"default-semantics agent middleware order was {middleware_type_names}, expected {expected_order}"
        )

    default_guard = next(
        (
            middleware
            for middleware in default_agent.middleware
            if isinstance(middleware, ns.CapabilityGuardMiddleware)
        ),
        None,
    )
    if default_guard is None:
        raise AssertionError("default-semantics agent has no CapabilityGuardMiddleware")
    if default_guard.allowed_tools is not None:
        raise AssertionError(
            f"allowed_tools=None was coerced to {default_guard.allowed_tools!r}, expected None (no allowlist)"
        )

    result = await exercise_capability_hook(ns, default_guard)
    if result.allow_executions != 1:
        raise AssertionError(
            f"default-semantics safe tool executed {result.allow_executions} times, expected exactly 1"
        )
    if result.deny_executions != 0:
        raise AssertionError(
            f"default-semantics dangerous tool executed {result.deny_executions} times, expected exactly 0"
        )
    if not result.denial_observed:
        raise AssertionError("default-semantics dangerous tool was not denied")

    print("SNIPPET_DEFAULT_SEMANTICS=PASS")


async def run_probe(ns: SimpleNamespace) -> None:
    await check_stub_foundry_construction(ns)
    await check_stub_response_shape(ns)
    check_policies(ns)
    check_audit_log(ns)
    guard, _audit_log, stack = build_factory_stack(ns)
    await check_capability_hook(ns, guard)
    await check_policy_middleware(ns, stack)
    await check_snippet_import(ns)


def main() -> None:
    check_versions()
    ns = check_imports()
    check_signatures(ns)
    asyncio.run(run_probe(ns))
    print("CONTRACT_PROBE=PASS")


if __name__ == "__main__":
    main()
