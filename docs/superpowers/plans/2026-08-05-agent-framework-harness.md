# Agent Framework Harness Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone `agent-framework-harness` skill that is the catalog's canonical contract for Microsoft Agent Framework Python `create_harness_agent`, including accurate defaults, composition, local and hosted recipes, bounded plan-to-execute flow, recovery, and offline plus live-Azure verification.

**Architecture:** Keep the skill contract in one `SKILL.md` and place every non-trivial runnable example in a focused canonical Python reference. A Tier-B upstream pin runs the canonical offline contract smoke, while a registered Copilot CLI fixture imports the hosted reference and proves one real Foundry model call without taking ownership of deployment, RBAC, governance, Skills REST distribution, or eval design.

**Tech Stack:** Markdown skill contracts, Python 3.10+, Microsoft Agent Framework 1.13.x, `agent-framework-foundry` 1.10.x, prerelease `agent-framework-foundry-hosting` and `agent-framework-tools`, Azure Identity, `ResponsesHostServer`, YAML pin metadata, Python `unittest`, Copilot CLI Azure T3 fixtures, and the existing awesome-gbb validation/site-generation scripts.

---

## Scope and file map

This is one cohesive catalog addition. Runtime composition, its canonical
references, pin validation, T3 proof, routing links, and catalog registration
must land together because each is part of the same published skill contract.

| File | Action | Single responsibility |
|---|---|---|
| `skills/agent-framework-harness/SKILL.md` | Create | Decision guidance, factory architecture/defaults, boundaries, security, maturity labels, and imperative links to canonical references |
| `skills/agent-framework-harness/references/python/local_harness.py` | Create | Local Foundry-backed Harness construction with explicit session and file-memory location |
| `skills/agent-framework-harness/references/python/hosted_harness.py` | Create | Build the Harness `Agent`, wrap it in `ResponsesHostServer`, and expose construction seams for T3 without starting HTTP |
| `skills/agent-framework-harness/references/python/plan_execute.py` | Create | Real host approval callback boundary, durable-session callback, plan/execute transition, and bounded todo loop |
| `skills/agent-framework-harness/references/python/session_recovery.py` | Create | Typed full-session serialize/restore helpers that preserve opaque provider state |
| `skills/agent-framework-harness/references/python/test_harness_contract.py` | Create | Credential-free signature/default/composition/hosting-import smoke and stable validation markers |
| `skills/agent-framework-harness/references/upstream-pin.md` | Create | Tier-B package/source/docs/known-issue freshness contract and executable offline validation script |
| `skills/agent-framework-harness/test-fixture/consumer_prompt.md` | Create | Live Foundry T3 construction and model-invocation contract with deterministic marker file |
| `.github/skill-deps.yml` | Modify | Register the fixture and forward dependency on `foundry-hosted-agents` |
| `skills/foundry-hosted-agents/SKILL.md` | Modify | Route runtime-factory composition to `agent-framework-harness` while retaining deployment/RBAC/lifecycle ownership |
| `skills/foundry-agt/SKILL.md` | Modify | Route Harness scaffolding and approval UX away from deterministic governance ownership |
| `skills/foundry-skill-catalog/SKILL.md` | Modify | Route local Harness skills composition away from Foundry Skills REST distribution |
| `README.md` | Modify | Add the public catalog row and update visible catalog totals |
| `scripts/build-site.py` | Modify | Place the new skill in the Foundry Building Blocks category |
| `plugin.json` | Modify | MINOR-bump the catalog plugin and update the skill count |
| `.github/plugin/marketplace.json` | Modify | Match the plugin version and public skill count |
| `AGENTS.md` | Modify | Update current catalog/pin/fixture coverage counts only |
| `docs/index.html` | Generate | Refresh the site landing page |
| `docs/skills/index.html` | Generate | Refresh the skill index |
| `docs/skills/agent-framework-harness/index.html` | Generate | Publish the new skill page |
| `docs/plugins/index.html` | Generate | Refresh the plugin index |
| `docs/plugins/awesome-gbb/index.html` | Generate | Refresh plugin details and totals |
| `docs/llms.txt` | Generate | Refresh the machine-readable catalog |

Do not create `azure.yaml`, Bicep, Docker, RBAC, deployment, AGT policy,
Foundry Skills REST, or eval files. Do not modify
`.github/workflows/skill-test.yml`; its existing environment, retry, audit, and
marker contracts already support this fixture.

### Fixed upstream baseline

Implementation starts from the verified 2026-08-03 baseline below, but Task 1
must re-query the sources before any file freezes these values:

| Surface | Required pin |
|---|---|
| `microsoft/agent-framework` Python tag | `python-1.13.0` |
| Pinned upstream SHA | `e39a8a2e79c8c8987a0b9082d3ccb8665734b897` |
| `agent-framework` | `1.13.0` with validation install `~=1.13.0` |
| `agent-framework-core` | `1.13.0` with validation install `~=1.13.0` |
| `agent-framework-foundry` | `1.10.4` with validation install `~=1.10.4` |
| `agent-framework-foundry-hosting` | `1.0.0b260730` with exact validation install |
| `agent-framework-tools` | `1.0.0b260730` with exact validation install |
| `azure-identity` | `1.25.3` with validation install `~=1.25.3` |

---

### Task 1: Re-verify the upstream contract before freezing pins

**Files:**
- Read: `docs/superpowers/specs/2026-08-05-agent-framework-harness-design.md`
- Read: `scripts/templates/upstream-pin.template.md`
- Read: `skills/foundry-hosted-agents/references/upstream-pin.md`
- No files changed

- [ ] **Step 1: Confirm the repository is clean before implementation**

Run:

```bash
git status --short
git --no-pager log -2 --oneline
```

Expected: `git status --short` is empty; no implementation files exist under
`skills/agent-framework-harness/`; the design commit `8690bfd` and the
implementation-plan commit appear in history.

- [ ] **Step 2: Re-query the Python tag and immutable SHA**

Run:

```bash
git ls-remote https://github.com/microsoft/agent-framework.git \
  refs/tags/python-1.13.0
```

Expected:

```text
e39a8a2e79c8c8987a0b9082d3ccb8665734b897	refs/tags/python-1.13.0
```

If the tag resolves to a different SHA, stop: tags are expected to be
immutable and the approved source baseline must be re-reviewed.

- [ ] **Step 3: Re-query all published package versions**

Run:

```bash
for package in \
  agent-framework \
  agent-framework-core \
  agent-framework-foundry \
  agent-framework-foundry-hosting \
  agent-framework-tools \
  azure-identity
do
  curl -fsSL "https://pypi.org/pypi/${package}/json" |
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["info"]["name"], d["info"]["version"])'
done
```

Expected current rows:

```text
agent-framework 1.13.0
agent-framework-core 1.13.0
agent-framework-foundry 1.10.4
agent-framework-foundry-hosting 1.0.0b260730
agent-framework-tools 1.0.0b260730
azure-identity 1.25.3
```

If a package has moved, update every later exact value in this plan coherently
and repeat the source/API review before implementation.

- [ ] **Step 4: Verify the published `create_harness_agent` signature**

Run:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/microsoft/agent-framework/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/packages/core/agent_framework/_harness/_agent.py |
  rg -n "def create_harness_agent|disable_(compaction|todo|mode|file_memory|web_search|tool_auto_approval)|file_access_store|skills_provider|skills_paths|background_agents|shell_executor|loop_should_continue|loop_max_iterations" \
  -C 2
```

Expected: the six `disable_*` parameters are `False`; opt-in providers and
executors are `None`; `loop_max_iterations` is `10`.

- [ ] **Step 5: Verify factory ordering and conditional composition**

Run:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/microsoft/agent-framework/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/packages/core/agent_framework/_harness/_agent.py \
  > /tmp/agent-framework-harness-factory.py
rg -n "InMemoryHistoryProvider|CompactionProvider|TodoProvider|AgentModeProvider|FileMemoryProvider|FileAccessProvider|SkillsProvider|BackgroundAgentsProvider|ShellEnvironmentProvider|AgentLoopMiddleware|ToolApprovalMiddleware|MessageInjectionMiddleware" \
  /tmp/agent-framework-harness-factory.py
```

Expected: provider creation follows history, conditional compaction, todo,
mode, file memory, optional file access, skills, background agents, shell,
then caller providers. Middleware creation follows optional loop, default tool
approval, always-on message injection, then caller middleware.

- [ ] **Step 6: Verify compaction, option-merging, and validation behavior from upstream tests**

Run:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/microsoft/agent-framework/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/packages/core/tests/core/test_harness_agent.py \
  > /tmp/test-harness-agent.py
rg -n "custom_before_strategy|custom_after_strategy|disable_compaction|max_tokens|output_gte_context|default_max_iterations|forwards_max_iterations|passes_auto_approval_rules" \
  /tmp/test-harness-agent.py -C 4
```

Expected: both budgets create the shared default strategy; before-only and
after-only custom strategies are independent; `disable_compaction=True`
overrides them; caller `max_tokens` wins; invalid budgets raise `ValueError`;
default loop cap is 10; approval rules are forwarded only when supplied.

- [ ] **Step 7: Remove the temporary upstream snapshots**

Run:

```bash
rm -f /tmp/agent-framework-harness-factory.py /tmp/test-harness-agent.py
```

Expected: both files are absent and the worktree is unchanged.

---

### Task 2: Write the offline contract smoke first

**Files:**
- Create: `skills/agent-framework-harness/references/python/test_harness_contract.py`

- [ ] **Step 1: Create the reference directories**

Run:

```bash
mkdir -p skills/agent-framework-harness/references/python
```

Expected: the empty directory hierarchy exists; no other skill directory is
modified.

- [ ] **Step 2: Write the failing offline contract smoke**

Create
`skills/agent-framework-harness/references/python/test_harness_contract.py`
with this structure and assertions:

```python
"""Canonical offline contract smoke for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Offline contract and pin validation`.
"""

from __future__ import annotations

import inspect
import os
import py_compile
import tempfile
from contextlib import contextmanager
from collections.abc import Awaitable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentLoopMiddleware,
    AgentModeProvider,
    BaseChatClient,
    ChatOptions,
    ChatResponse,
    ChatResponseUpdate,
    CompactionProvider,
    FileAccessProvider,
    FileMemoryProvider,
    InMemoryAgentFileStore,
    InMemoryHistoryProvider,
    Message,
    MessageInjectionMiddleware,
    ResponseStream,
    SkillsProvider,
    TodoProvider,
    ToolApprovalMiddleware,
    ToolResultCompactionStrategy,
    create_harness_agent,
)
from agent_framework_foundry_hosting import ResponsesHostServer


class NeverCalledChatClient(BaseChatClient[ChatOptions[Any]]):
    """Minimal client used only to prove construction never calls a model."""

    model = "offline-construction-only"

    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Awaitable[ChatResponse] | ResponseStream[ChatResponseUpdate, ChatResponse]:
        raise AssertionError("offline construction called the model")


@contextmanager
def isolated_working_directory() -> Iterator[Path]:
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="harness-contract-") as directory:
        target = Path(directory)
        os.chdir(target)
        try:
            yield target
        finally:
            os.chdir(previous)


def provider_types(agent: Agent) -> list[type[Any]]:
    return [type(provider) for provider in agent.context_providers or []]


def middleware_types(agent: Agent) -> list[type[Any]]:
    return [type(middleware) for middleware in agent.middleware or []]


def assert_signature() -> None:
    signature = inspect.signature(create_harness_agent)
    for name in (
        "disable_compaction",
        "disable_todo",
        "disable_mode",
        "disable_file_memory",
        "disable_web_search",
        "disable_tool_auto_approval",
    ):
        assert signature.parameters[name].default is False
    for name in (
        "file_access_store",
        "skills_provider",
        "skills_paths",
        "background_agents",
        "shell_executor",
        "loop_should_continue",
    ):
        assert signature.parameters[name].default is None
    assert signature.parameters["loop_max_iterations"].default == 10
    return_annotation = signature.return_annotation
    assert (
        return_annotation is Agent
        or str(return_annotation).startswith("Agent")
        or getattr(return_annotation, "__origin__", None) is Agent
    )


def assert_defaults(client: NeverCalledChatClient) -> None:
    agent = create_harness_agent(
        client=client,
        disable_web_search=True,
    )
    assert isinstance(agent, Agent)
    providers = provider_types(agent)
    middleware = middleware_types(agent)
    assert providers[:1] == [InMemoryHistoryProvider]
    assert TodoProvider in providers
    assert AgentModeProvider in providers
    assert FileMemoryProvider in providers
    assert FileAccessProvider not in providers
    assert SkillsProvider not in providers
    assert CompactionProvider not in providers
    provider_names = {provider.__name__ for provider in providers}
    assert "BackgroundAgentsProvider" not in provider_names
    assert "ShellEnvironmentProvider" not in provider_names
    assert ToolApprovalMiddleware in middleware
    assert MessageInjectionMiddleware in middleware
    assert AgentLoopMiddleware not in middleware
    approval = next(
        item for item in agent.middleware or []
        if isinstance(item, ToolApprovalMiddleware)
    )
    assert approval.auto_approval_rules == ()


def assert_compaction(client: NeverCalledChatClient) -> None:
    complete = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_web_search=True,
    )
    assert complete.compaction_strategy is not None
    complete_provider = next(
        provider for provider in complete.context_providers or []
        if isinstance(provider, CompactionProvider)
    )
    assert complete_provider.before_strategy is None
    assert complete_provider.after_strategy is complete.compaction_strategy
    assert complete.default_options["max_tokens"] == 16_384

    context_only = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        disable_web_search=True,
    )
    assert context_only.compaction_strategy is None
    assert CompactionProvider not in provider_types(context_only)
    output_only = create_harness_agent(
        client=client,
        max_output_tokens=16_384,
        disable_web_search=True,
    )
    assert output_only.compaction_strategy is None
    assert CompactionProvider not in provider_types(output_only)

    before = ToolResultCompactionStrategy()
    after = ToolResultCompactionStrategy()
    before_only = create_harness_agent(
        client=client,
        before_compaction_strategy=before,
        disable_web_search=True,
    )
    assert before_only.compaction_strategy is before
    assert CompactionProvider not in provider_types(before_only)
    after_only = create_harness_agent(
        client=client,
        after_compaction_strategy=after,
        disable_web_search=True,
    )
    assert after_only.compaction_strategy is None
    after_provider = next(
        provider for provider in after_only.context_providers or []
        if isinstance(provider, CompactionProvider)
    )
    assert after_provider.before_strategy is None
    assert after_provider.after_strategy is after
    disabled = create_harness_agent(
        client=client,
        before_compaction_strategy=before,
        after_compaction_strategy=after,
        disable_compaction=True,
        disable_web_search=True,
    )
    assert disabled.compaction_strategy is None
    assert CompactionProvider not in provider_types(disabled)


def assert_construction(client: NeverCalledChatClient) -> None:
    file_access = create_harness_agent(
        client=client,
        file_access_store=InMemoryAgentFileStore(),
        disable_web_search=True,
    )
    assert FileAccessProvider in provider_types(file_access)

    skills = create_harness_agent(
        client=client,
        skills_paths=["./offline-skills"],
        disable_web_search=True,
    )
    assert SkillsProvider in provider_types(skills)

    async def stop_loop(**kwargs: Any) -> bool:
        return False

    looped = create_harness_agent(
        client=client,
        loop_should_continue=stop_loop,
        loop_max_iterations=3,
        disable_web_search=True,
    )
    loop = next(
        item for item in looped.middleware or []
        if isinstance(item, AgentLoopMiddleware)
    )
    assert loop.max_iterations == 3

    hosted_options = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_web_search=True,
        default_options={"store": False, "max_tokens": 8_192},
    )
    assert hosted_options.default_options["store"] is False
    assert hosted_options.default_options["max_tokens"] == 8_192

    for context_tokens, output_tokens in (
        (0, 100),
        (100, 0),
        (100, -1),
        (100, 100),
    ):
        try:
            create_harness_agent(
                client=client,
                max_context_window_tokens=context_tokens,
                max_output_tokens=output_tokens,
                disable_web_search=True,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid token budgets were accepted")


def assert_reference_imports() -> None:
    reference_dir = Path(__file__).parent
    for name in (
        "local_harness.py",
        "hosted_harness.py",
        "plan_execute.py",
        "session_recovery.py",
    ):
        py_compile.compile(str(reference_dir / name), doraise=True)
    from hosted_harness import build_agent, build_server

    assert callable(build_agent)
    assert callable(build_server)
    assert ResponsesHostServer


def main() -> None:
    with isolated_working_directory():
        client = NeverCalledChatClient()
        assert_signature()
        print("HARNESS_SIGNATURE_OK")
        assert_defaults(client)
        print("HARNESS_DEFAULTS_OK")
        assert_compaction(client)
        print("HARNESS_COMPACTION_OK")
        assert_construction(client)
        print("HARNESS_CONSTRUCTION_OK")
        assert_reference_imports()
        print("HOSTING_IMPORT_OK")


if __name__ == "__main__":
    main()
```

Before implementation, confirm the exact abstract method signatures on
`BaseChatClient`; if the verified 1.13.0 source requires additional abstract
members, implement only those members and make every response path raise the
same `AssertionError`.

- [ ] **Step 3: Install the pinned runtime in an isolated environment**

Run:

```bash
python3 -m venv /tmp/agent-framework-harness-plan-venv
/tmp/agent-framework-harness-plan-venv/bin/pip install --quiet \
  "agent-framework~=1.13.0" \
  "agent-framework-core~=1.13.0" \
  "agent-framework-foundry~=1.10.4" \
  "agent-framework-foundry-hosting==1.0.0b260730" \
  "agent-framework-tools==1.0.0b260730" \
  "azure-identity~=1.25.3"
```

Expected: installation succeeds without using global Python packages.

- [ ] **Step 4: Run the smoke and verify it fails for the missing canonical references**

Run:

```bash
/tmp/agent-framework-harness-plan-venv/bin/python \
  skills/agent-framework-harness/references/python/test_harness_contract.py
```

Expected: earlier signature/default/compaction/construction assertions pass,
then execution fails with `FileNotFoundError` for `local_harness.py` or
`hosted_harness.py`. Fix only test-double/API mismatches revealed before that
expected failure.

- [ ] **Step 5: Commit the executable failing contract**

Run:

```bash
git add skills/agent-framework-harness/references/python/test_harness_contract.py
git commit -m "test(agent-framework-harness): define offline contract

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit containing only the offline contract smoke.

---

### Task 3: Add local and hosted canonical construction references

**Files:**
- Create: `skills/agent-framework-harness/references/python/local_harness.py`
- Create: `skills/agent-framework-harness/references/python/hosted_harness.py`
- Test: `skills/agent-framework-harness/references/python/test_harness_contract.py`

- [ ] **Step 1: Write the complete local recipe**

Create `skills/agent-framework-harness/references/python/local_harness.py`:

```python
"""Canonical local Agent Framework Harness construction.

Source of truth for the prose example in
`../../SKILL.md § Canonical local Python recipe`.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agent_framework import FileSystemAgentFileStore, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential


async def main() -> None:
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=AzureCliCredential(),
    )
    agent = create_harness_agent(
        client=client,
        name="local-harness",
        agent_instructions=(
            "Plan carefully, verify tool results, and report the final outcome."
        ),
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        file_memory_store=FileSystemAgentFileStore(
            (Path.cwd() / ".agent-memory").resolve()
        ),
        disable_web_search=True,
    )
    session = agent.create_session()
    response = await agent.run(
        "Create a short plan for validating this harness configuration.",
        session=session,
    )
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Write the hosted recipe with construction seams**

Create `skills/agent-framework-harness/references/python/hosted_harness.py`:

```python
"""Canonical Agent Framework Harness wiring for Foundry Hosted Agents.

Source of truth for the prose example in
`../../SKILL.md § Canonical Foundry Hosted recipe`.
"""

from __future__ import annotations

import os
from typing import Any

from agent_framework import Agent, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def build_agent(
    *,
    project_endpoint: str | None = None,
    model: str | None = None,
    credential: Any | None = None,
) -> Agent:
    client = FoundryChatClient(
        project_endpoint=project_endpoint or os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=model or os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential or DefaultAzureCredential(),
    )
    return create_harness_agent(
        client=client,
        name="hosted-harness",
        agent_instructions="Complete the caller's task and return a concise result.",
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_mode=True,
        disable_file_memory=True,
        disable_web_search=True,
        default_options={"store": False},
    )


def build_server(agent: Agent | None = None) -> ResponsesHostServer:
    return ResponsesHostServer(agent or build_agent())


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
```

Do not start the server at import time. The optional constructor arguments
exist only to make canonical code directly testable and reusable; production
defaults still come from platform environment variables and managed identity.

- [ ] **Step 3: Compile both references**

Run:

```bash
/tmp/agent-framework-harness-plan-venv/bin/python -m py_compile \
  skills/agent-framework-harness/references/python/local_harness.py \
  skills/agent-framework-harness/references/python/hosted_harness.py
```

Expected: exit 0 with no output.

- [ ] **Step 4: Re-run the offline smoke**

Run:

```bash
/tmp/agent-framework-harness-plan-venv/bin/python \
  skills/agent-framework-harness/references/python/test_harness_contract.py
```

Expected: failure moves to missing `plan_execute.py` or
`session_recovery.py`; all five stable markers are not printed yet.

- [ ] **Step 5: Commit the construction references**

Run:

```bash
git add \
  skills/agent-framework-harness/references/python/local_harness.py \
  skills/agent-framework-harness/references/python/hosted_harness.py
git commit -m "feat(agent-framework-harness): add construction references

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit containing only the local and hosted canonical recipes.

---

### Task 4: Add bounded plan/execute and session-recovery references

**Files:**
- Create: `skills/agent-framework-harness/references/python/plan_execute.py`
- Create: `skills/agent-framework-harness/references/python/session_recovery.py`
- Test: `skills/agent-framework-harness/references/python/test_harness_contract.py`

- [ ] **Step 1: Write the typed session-recovery helpers**

Create `skills/agent-framework-harness/references/python/session_recovery.py`:

```python
"""Canonical full-session persistence helpers for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Session persistence and recovery`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_framework import AgentSession


def serialize_session(session: AgentSession) -> dict[str, Any]:
    """Serialize the full opaque session, including provider-owned state."""
    return session.to_dict()


def restore_session(payload: Mapping[str, Any]) -> AgentSession:
    """Restore a session without reaching into provider-specific state."""
    return AgentSession.from_dict(dict(payload))
```

- [ ] **Step 2: Write the real host approval and persistence boundaries**

Create `skills/agent-framework-harness/references/python/plan_execute.py`:

```python
"""Canonical bounded plan-to-execute flow for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Safe plan-to-execute pattern`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from agent_framework import (
    Agent,
    create_harness_agent,
    set_agent_mode,
    todos_remaining,
    todos_remaining_message,
)

from session_recovery import serialize_session

ApprovePlan = Callable[[str], Awaitable[bool]]
PersistSession = Callable[[dict[str, Any]], Awaitable[None]]


def build_plan_execute_agent(client: Any) -> Agent:
    return create_harness_agent(
        client=client,
        name="bounded-plan-execute-harness",
        agent_instructions=(
            "Plan before execution, keep todos current, and verify tool results."
        ),
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        loop_should_continue=todos_remaining(looping_modes=["execute"]),
        loop_next_message=todos_remaining_message,
        loop_max_iterations=10,
        disable_web_search=True,
    )


async def run_approved_plan(
    *,
    agent: Agent,
    request: str,
    approve_plan: ApprovePlan,
    persist_session: PersistSession,
) -> str:
    session = agent.create_session()
    set_agent_mode(session, "plan")
    plan_response = await agent.run(
        f"Plan this request without executing it: {request}",
        session=session,
    )
    await persist_session(serialize_session(session))

    if not await approve_plan(plan_response.text):
        return "Plan rejected; execution did not start."

    set_agent_mode(session, "execute")
    await persist_session(serialize_session(session))
    result = await agent.run(
        "Execute the approved plan and complete the remaining todos.",
        session=session,
    )
    await persist_session(serialize_session(session))
    return result.text
```

The approval callback must be called before `set_agent_mode(..., "execute")`.
Persist the full session after planning, after the approved mode transition,
and after execution. Keep `loop_max_iterations=10`; never substitute `None`.

- [ ] **Step 3: Compile all five Python references**

Run:

```bash
/tmp/agent-framework-harness-plan-venv/bin/python -m py_compile \
  skills/agent-framework-harness/references/python/*.py
```

Expected: exit 0 with no output.

- [ ] **Step 4: Run the offline smoke to green**

Run:

```bash
/tmp/agent-framework-harness-plan-venv/bin/python \
  skills/agent-framework-harness/references/python/test_harness_contract.py
```

Expected:

```text
HARNESS_SIGNATURE_OK
HARNESS_DEFAULTS_OK
HARNESS_COMPACTION_OK
HARNESS_CONSTRUCTION_OK
HOSTING_IMPORT_OK
```

No Azure credential lookup, model call, HTTP server, or repository-local
`.agent-memory` write may occur.

- [ ] **Step 5: Commit the plan/execute and recovery references**

Run:

```bash
git add \
  skills/agent-framework-harness/references/python/plan_execute.py \
  skills/agent-framework-harness/references/python/session_recovery.py
git commit -m "feat(agent-framework-harness): add bounded execution references

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit containing only the plan/execute and recovery references.

---

### Task 5: Add the Tier-B pin and make pin validation execute the canonical smoke

**Files:**
- Create: `skills/agent-framework-harness/references/upstream-pin.md`
- Test: `skills/agent-framework-harness/references/python/test_harness_contract.py`

- [ ] **Step 1: Write the pin frontmatter with the verified package stack**

Create `skills/agent-framework-harness/references/upstream-pin.md` using schema
version 2 and this exact contract:

```yaml
---
schema_version: 2
freshness_tier: B
automation_tier: auto
upstream:
  type: pypi
  notes: |
    Tier-B package wrapper around microsoft/agent-framework. The source was
    audited at Python tag python-1.13.0, immutable commit
    e39a8a2e79c8c8987a0b9082d3ccb8665734b897. Package drift is detected
    through the PyPI versions below; the tag and SHA remain audit evidence.
packages:
  - name: agent-framework
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
  - name: agent-framework-core
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.4"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: Exact prerelease pin; do not replace with a compatible-release range.
  - name: agent-framework-tools
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-tools/#history
    notes: Exact prerelease pin for optional shell tooling.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
docs_to_revalidate:
  - https://learn.microsoft.com/agent-framework/agents/harness
  - https://learn.microsoft.com/agent-framework/agents/skills
  - https://learn.microsoft.com/agent-framework/agents/conversations/storage#persisting-sessions-across-restarts
  - https://learn.microsoft.com/azure/foundry/how-to/develop/framework-hosted-agents
  - https://pypi.org/project/agent-framework-foundry-hosting/
known_issues:
  - id: KI-001
    description: FileAccessProvider remains experimental and upstream is still improving its Harness contract; treat its controls as access UX, not sandboxing.
    upstream_url: https://github.com/microsoft/agent-framework/issues/6770
    status: open
    workaround_location: SKILL.md § "Default, opt-in, and experimental feature matrix"
  - id: KI-002
    description: BackgroundAgentsProvider can retain per-session tasks and child sessions; keep host-owned cancellation and cleanup explicit.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7385
    status: open
    workaround_location: SKILL.md § "Default, opt-in, and experimental feature matrix"
  - id: KI-003
    description: CompactionProvider currently runs after each AgentLoopMiddleware iteration; use explicit caps and verify compaction behavior on refresh.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7236
    status: open
    workaround_location: SKILL.md § "Safe plan-to-execute pattern"
  - id: KI-004
    description: Shell and code-execution Harness samples remain incomplete while agent-framework-tools is prerelease; workdir or deny lists are not sandboxing.
    upstream_url: https://github.com/microsoft/agent-framework/issues/6448
    status: open
    workaround_location: SKILL.md § "Failure modes and security callouts"
validation:
  runnable: true
  requires:
    - github_only
    - pypi
  script: |
    set -euo pipefail
    python3 -m venv /tmp/agent-framework-harness-pin
    /tmp/agent-framework-harness-pin/bin/pip install --quiet \
      "agent-framework~=1.13.0" \
      "agent-framework-core~=1.13.0" \
      "agent-framework-foundry~=1.10.4" \
      "agent-framework-foundry-hosting==1.0.0b260730" \
      "agent-framework-tools==1.0.0b260730" \
      "azure-identity~=1.25.3"
    /tmp/agent-framework-harness-pin/bin/python \
      skills/agent-framework-harness/references/python/test_harness_contract.py
  expected_output:
    - HARNESS_SIGNATURE_OK
    - HARNESS_DEFAULTS_OK
    - HARNESS_COMPACTION_OK
    - HARNESS_CONSTRUCTION_OK
    - HOSTING_IMPORT_OK
  failure_signatures:
    - AssertionError
    - ImportError
    - ModuleNotFoundError
    - FileNotFoundError
last_validated: 2026-08-05
validated_by: copilot-bot
known_issues_count: 4
---
```

Below the frontmatter, add a concise audit trail that separately records:

1. the 1.13.0 stable Harness factory baseline;
2. the exact beta hosting/tools pins;
3. the verified default values and provider/middleware order;
4. the requirement to re-check web-search capability detection and empty
   approval-rule behavior on every MINOR refresh;
5. the requirement to track Hosted Agents service lifecycle independently of
   Python hosting-adapter semver;
6. the latest offline smoke output.

- [ ] **Step 2: Validate the new pin schema**

Run:

```bash
python3 scripts/validate-skills.py
```

Expected at this intermediate point: failures only for the missing
`skills/agent-framework-harness/SKILL.md` or its missing fixture/dependency
registration. There must be no schema, cap, package, date, URL, or validation
script error for `upstream-pin.md`.

- [ ] **Step 3: Execute the pin's canonical validation script**

Run:

```bash
python3 scripts/run-pin-validation.py --base main
```

Expected: all five stable markers are found and the pin reports success. Do
not duplicate test logic inside the YAML script beyond invoking
`test_harness_contract.py`.

- [ ] **Step 4: Commit the freshness contract**

Run:

```bash
git add skills/agent-framework-harness/references/upstream-pin.md
git commit -m "chore(agent-framework-harness): pin the runtime contract

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit containing only the upstream pin.

---

### Task 6: Write the complete skill contract

**Files:**
- Create: `skills/agent-framework-harness/SKILL.md`
- Read: `docs/superpowers/specs/2026-08-05-agent-framework-harness-design.md`
- Read: all files under `skills/agent-framework-harness/references/python/`

- [ ] **Step 1: Add fixed frontmatter and verify description length**

Start `skills/agent-framework-harness/SKILL.md` with:

```yaml
---
name: agent-framework-harness
description: >
  Build Microsoft Agent Framework Python agents with create_harness_agent: plan/execute modes, persistent todos, context compaction, session/file memory, approval UX, recovery, and opt-in file access, skills, background agents, shell, and bounded looping. Covers actual defaults, internal provider/middleware ordering, local construction, and ResponsesHostServer wiring for Foundry Hosted Agents. USE FOR: Agent Harness, create_harness_agent, harness defaults, plan mode, execute mode, TodoProvider, FileMemoryProvider, compaction, tool approval, auto_approval_rules, AgentSession recovery, loop_should_continue, shell_executor, background_agents, ResponsesHostServer harness wiring. DO NOT USE FOR: deployment, RBAC, containers, or lifecycle (use foundry-hosted-agents); deterministic policy, audit, authorization, or sandbox governance (use foundry-agt); Foundry Skills REST distribution (use foundry-skill-catalog); general eval design (use foundry-evals).
metadata:
  version: "1.0.0"
---
```

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("skills/agent-framework-harness/SKILL.md")
data = yaml.safe_load(p.read_text().split("---", 2)[1])
print(len(data["description"]))
assert 200 <= len(data["description"]) <= 1024
PY
```

Expected: `958`, including YAML's folded-scalar trailing newline.

- [ ] **Step 2: Write the one-minute decision table and ownership boundary**

Add `## Quick decision table` as the first body section with these rows:

| Need | Owner |
|---|---|
| Compose a MAF `Agent` with Harness providers, middleware, modes, todos, compaction, recovery, approval UX, or opt-in executors | `agent-framework-harness` |
| Deploy, authorize, containerize, roll out, or operate a hosted agent | [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) |
| Enforce deterministic authorization, policy, audit, or governance | [`foundry-agt`](../foundry-agt/SKILL.md) |
| Publish or consume centrally managed skills through Foundry Skills REST | [`foundry-skill-catalog`](../foundry-skill-catalog/SKILL.md) |
| Design or score evaluations | [`foundry-evals`](../foundry-evals/SKILL.md) |

Immediately state:

- Harness is runtime/scaffolding, not hosting.
- Native Harness tool approval is an interactive UX gate and standing-approval
  convenience, not a non-bypassable policy engine.
- `ResponsesHostServer` adapts an already-built `Agent`; it does not create
  the Harness composition.
- This skill does not own deployment, RBAC, lifecycle, deterministic
  governance, Skills REST distribution, or general eval design.

- [ ] **Step 3: Document the internal factory pipeline exactly**

Add `## Architecture and internal factory pipeline` with this provider order:

1. `InMemoryHistoryProvider`
2. conditional before/after compaction composition
3. todo provider
4. `AgentModeProvider`
5. `FileMemoryProvider`
6. optional `FileAccessProvider`
7. optional `SkillsProvider`
8. optional `BackgroundAgentsProvider`
9. optional shell provider
10. caller-supplied context providers

Then document middleware order:

1. optional `AgentLoopMiddleware`
2. default `ToolApprovalMiddleware`
3. always-on `MessageInjectionMiddleware`
4. caller-supplied middleware

State that default history is in-memory, provider state is session-backed,
pending approval returns control to the caller, and looping is outermost so
each pass remains a complete agent run.

- [ ] **Step 4: Add the complete default/opt-in/experimental matrix**

Add `## Default, opt-in, and experimental feature matrix` with no ambiguous
“enabled” shorthand:

| Feature | Factory behavior at the pinned release | Maturity and use |
|---|---|---|
| Function invocation | Always wired by `Agent` | Released |
| Per-service-call history persistence | Always enabled with default `InMemoryHistoryProvider` | Released; not durable across process loss unless the host persists the full session |
| Todo provider | Default-on unless `disable_todo=True` | Stable |
| Mode provider | Default-on in `plan` mode unless `disable_mode=True` | Stable; headless hosts should disable it unless they expose approval and transitions |
| File memory | Default-on unless `disable_file_memory=True`; default store is `{cwd}/agent-file-memory` | Stable API; choose an explicit store and tenant boundary |
| Compaction | Factory support is present, but no default strategy/provider is active without both token budgets; custom phases may be supplied independently | Stable; never claim a bare factory call compacts |
| Web search | `disable_web_search=False` by default, but a tool is added only when the client implements `SupportsWebSearchTool`; otherwise the factory logs a warning | Released capability-dependent surface; verify on every refresh |
| Tool approval | Middleware is default-on unless `disable_tool_auto_approval=True`; it coordinates queued approvals and session-backed standing rules | Released UX gate, not governance; requires `AgentSession` |
| Heuristic auto-approval callbacks | None unless `auto_approval_rules` is supplied | Opt-in; inspect arguments whenever risk depends on arguments |
| Message injection | Always on and no-op when the session queue is empty | Released |
| OpenTelemetry provider name | Set by the factory | Released; destination and sensitive-data settings remain caller-owned |
| Shared file access | Opt-in via `file_access_store` | Experimental; access control and sandboxing remain host responsibilities |
| Skills | Opt-in via `skills_provider` or `skills_paths` | Released; external sources are untrusted input and this is not Foundry Skills REST distribution |
| Background agents | Opt-in via `background_agents` | Experimental |
| Shell | Opt-in via `shell_executor` | Experimental and prerelease tooling |
| Looping | Opt-in via `loop_should_continue`; default cap resolves to 10 | Experimental; always pass an explicit positive cap |
| Caller providers and middleware | Opt-in | Advanced extension surface; preserve built-in ordering |

Add a compaction subsection that covers the shared default strategy, the
before-call `agent.compaction_strategy`, the after-call
`CompactionProvider`, independent custom strategies, and
`disable_compaction=True` overriding all strategies.

- [ ] **Step 5: Add imperative links to every canonical reference**

Add these sections and links without duplicating the Python bodies:

```markdown
## Canonical local Python recipe

> **MUST:** Copy and adapt
> [`references/python/local_harness.py`](references/python/local_harness.py).
> Do not redefine it inline; this file is the canonical local construction and
> session-use recipe.

## Canonical Foundry Hosted recipe

> **MUST:** Copy and adapt
> [`references/python/hosted_harness.py`](references/python/hosted_harness.py).
> It owns runtime wiring only. Use
> [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) for deployment,
> RBAC, containers, rollout, and lifecycle.

## Safe plan-to-execute pattern

> **MUST:** Use
> [`references/python/plan_execute.py`](references/python/plan_execute.py).
> Its host callback is the approval boundary and its positive loop cap is
> mandatory.

## Session persistence and recovery

> **MUST:** Use
> [`references/python/session_recovery.py`](references/python/session_recovery.py).
> Persist and restore the full opaque `AgentSession`; do not cherry-pick
> provider state.

## Offline contract and pin validation

> **MUST:** Run
> [`references/python/test_harness_contract.py`](references/python/test_harness_contract.py)
> through the executable contract in
> [`references/upstream-pin.md`](references/upstream-pin.md).
```

For the local section, state that both token budgets activate compaction, the
visible `.agent-memory` path prevents accidental unknown writes, web search is
disabled, an `AgentSession` is passed, and any compatible chat client can
replace `FoundryChatClient`.

For the hosted section, state that `default_options={"store": False}` is the
current correct hosting-adapter pattern, mode/file memory/web search are
disabled for the baseline headless host, and durable tenant-partitioned state
is required before re-enabling file memory.

- [ ] **Step 6: Separate hosting adapter status from service status**

Add a table under the hosted section:

| Surface | Current tracked status |
|---|---|
| Harness factory | Stable `agent-framework-core` 1.13.x |
| Python `agent-framework-foundry-hosting` adapter | `1.0.0b260730` prerelease; exact pin |
| Foundry Hosted Agents container service | Separate platform lifecycle owned and tracked by `foundry-hosted-agents` |

State explicitly that adapter prerelease status does not make the service
prerelease, and service lifecycle does not make the Python adapter stable.

- [ ] **Step 7: Add the Harness/Hosted/AGT comparison**

Add `## Harness vs Hosted Agents vs AGT`:

| Concern | Harness | Hosted Agents | AGT |
|---|---|---|---|
| Build provider/middleware runtime | Owns | Consumes the built agent | Can wrap the built agent |
| HTTP/Responses hosting | No | Owns through `ResponsesHostServer` and platform runtime | No |
| Deployment/RBAC/rollout | No | Owns | No |
| Native tool approval | UX gate | Transports caller interaction when designed | Can enforce configured deterministic policy |
| Audit/policy/governance | No | Platform operations only | Owns configured governance surfaces |
| Sandbox/security boundary | No | Platform isolation is separate | Only the explicitly configured AGT policy surfaces |

Then show the valid combined shape:

```text
Harness Agent -> AGT middleware/policy -> ResponsesHostServer
              -> Foundry hosted runtime, identity, scale, and lifecycle
```

- [ ] **Step 8: Add failure modes and security callouts**

Add `## Failure modes and security callouts` with concrete symptom, cause, and
fix rows for:

- compaction expected but one/both token budgets missing;
- file memory unexpectedly written under the process working directory;
- plan mode switched to execute without caller approval;
- loop set to `None` or allowed outside execute mode;
- approval waiting inside an autonomous loop;
- default session lost on process restart;
- hosted history duplicated because `store=False` was omitted;
- web search assumed present although the client does not support it;
- shell/background/file access treated as stable;
- provider or middleware order accidentally overridden by caller composition.

Include these exact security boundaries:

- shell deny lists and working-directory confinement are not sandboxing;
- file access and file memory require tenant partitioning and path policy;
- background agents multiply credentials, tools, cost, and cancellation
  responsibilities;
- positive loop caps bound iterations and cost but do not prove safety;
- native approval can be bypassed by host design and must not be described as
  deterministic authorization;
- deterministic governance belongs to `foundry-agt`.

- [ ] **Step 9: Add pin/reference policy and acceptance checklist**

Add `## Upstream pin and reference policy` that requires:

- stable compatible-release pins and exact prerelease pins;
- immutable source SHA/tag;
- separate service-lifecycle checks;
- web-search and approval-default re-verification on MINOR refresh;
- experimental file/background/loop/shell issue checks;
- signature/default/construction validation, not import-only testing;
- all non-trivial code remaining single-source under `references/python/`.

End with `## Completion checklist` containing checkboxes for the approved
acceptance criteria: one-minute routing, exact defaults, conditional
compaction wording, conditional web search, positive loop cap, approval UX
boundary, non-sandbox shell wording, experimental labels, canonical files,
separate hosting statuses, offline smoke, T3 evidence, and no ownership leak.

- [ ] **Step 10: Run focused structural validation**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
p = Path("skills/agent-framework-harness/SKILL.md")
parts = p.read_text().split("---", 2)
data = yaml.safe_load(parts[1])
assert data["name"] == p.parent.name
assert data["metadata"]["version"] == "1.0.0"
assert 200 <= len(data["description"]) <= 1024
for heading in (
    "Quick decision table",
    "Architecture and internal factory pipeline",
    "Default, opt-in, and experimental feature matrix",
    "Canonical local Python recipe",
    "Canonical Foundry Hosted recipe",
    "Safe plan-to-execute pattern",
    "Session persistence and recovery",
    "Harness vs Hosted Agents vs AGT",
    "Failure modes and security callouts",
    "Upstream pin and reference policy",
    "Offline contract and pin validation",
):
    assert f"## {heading}" in parts[2], heading
print("skill contract structure: OK")
PY
python3 scripts/validate-skills.py
```

Expected: the focused script prints `skill contract structure: OK`.
Catalog validation may still report only the not-yet-added fixture dependency,
catalog registration, plugin version, or generated docs.

- [ ] **Step 11: Commit the new skill contract with the required gate tag**

Run:

```bash
git add skills/agent-framework-harness/SKILL.md
git commit -m "[skill-rewrite] feat(agent-framework-harness): add harness runtime skill

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: the new skill body lands in a commit explicitly tagged
`[skill-rewrite]`.

---

### Task 7: Register and author the live Foundry T3 fixture

**Files:**
- Create: `skills/agent-framework-harness/test-fixture/consumer_prompt.md`
- Modify: `.github/skill-deps.yml`
- Import: `skills/agent-framework-harness/references/python/hosted_harness.py`

- [ ] **Step 1: Register the fixture and its forward dependency**

Add this entry to `.github/skill-deps.yml` in alphabetical order:

```yaml
  agent-framework-harness:
    depends_on:
      - foundry-hosted-agents
```

Keep the file's existing top-level shape and indentation. This deliberately
runs the Harness fixture when the hosted boundary changes; no reverse
dependency or workflow edit is needed.

- [ ] **Step 2: Write the fixture preamble and audit acknowledgement**

Create `skills/agent-framework-harness/test-fixture/consumer_prompt.md` as a
self-contained execution smoke, not a “use skill X” instruction. Its first
actions must be:

```markdown
# Agent Framework Harness live Foundry smoke

This is an execution smoke. Follow these steps directly; do not inspect the
catalog or redesign the task.

First run this lightweight audit acknowledgement in Bash:

    echo "skills/agent-framework-harness/SKILL.md"

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You are the running Copilot CLI process. Do not run `copilot -p`,
`copilot --version`, install Copilot, or write any transcript file. The
workflow already captures the outer process.
```

The fixture must never instruct the agent to `view` the full `SKILL.md`; the
single `echo` satisfies the workflow audit without consuming the skill body
again.

- [ ] **Step 3: Add the environment and auth contract**

Require only existence checks for:

```bash
test -n "$FOUNDRY_PROJECT_ENDPOINT"
test -n "$FOUNDRY_MODEL_DEPLOYMENT"
```

Then export the canonical recipe variable:

```bash
export AZURE_AI_MODEL_DEPLOYMENT_NAME="$FOUNDRY_MODEL_DEPLOYMENT"
```

Print non-secret state for the audit log:

```bash
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "AZURE_AI_MODEL_DEPLOYMENT_NAME=${AZURE_AI_MODEL_DEPLOYMENT_NAME:+set}"
az account show --output table ||
  echo "(az cache not inherited; DefaultAzureCredential will use the workflow OIDC environment)"
```

Do not assert subscription equality, inspect token claims, re-grant RBAC, run
`az login`, install Azure CLI/system tooling, hunt the filesystem for tools,
deploy infrastructure, or start `ResponsesHostServer`. The isolated pinned
Python environment in the next step is the only fixture-side installation.

- [ ] **Step 4: Add one pinned environment and one canonical live execution**

Require the agent to run these commands exactly:

```bash
python3 -m venv /tmp/agent-framework-harness-venv
/tmp/agent-framework-harness-venv/bin/pip install --quiet \
  "agent-framework-core~=1.13.0" \
  "agent-framework-foundry~=1.10.4" \
  "agent-framework-foundry-hosting==1.0.0b260730" \
  "azure-identity~=1.25.3"

/tmp/agent-framework-harness-venv/bin/python - <<'PY'
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from agent_framework import Agent
from agent_framework_foundry_hosting import ResponsesHostServer

reference_dir = (
    Path("skills/agent-framework-harness/references/python").resolve()
)
sys.path.insert(0, str(reference_dir))

from hosted_harness import build_agent, build_server


async def main() -> None:
    print("HARNESS_REFERENCE_IMPORT_OK")
    agent = build_agent()
    assert isinstance(agent, Agent)
    assert agent.default_options["store"] is False
    print("HARNESS_AGENT_CONSTRUCTED")

    server = build_server(agent)
    assert isinstance(server, ResponsesHostServer)
    print("HOSTING_ADAPTER_CONSTRUCTED")

    session = agent.create_session()
    response = await agent.run(
        "Reply with exactly HARNESS_LIVE_OK.",
        session=session,
    )
    assert "HARNESS_LIVE_OK" in response.text
    print("HARNESS_LIVE_RESPONSE_OK")


asyncio.run(main())
PY
```

Do not copy/redefine `build_agent` or `build_server` inside the fixture. Do
not call `server.run()`; constructing the adapter proves the wiring without
starting a long-lived HTTP process. The single `agent.run(...)` call is the
live Azure/model proof.

- [ ] **Step 5: Add deterministic marker handling**

Make the fixture's final mandatory action:

```bash
printf 'SMOKE_RESULT=PASS\n' \
  > /tmp/agent-framework-harness-smoke-result
```

For any prior failure:

```bash
printf 'SMOKE_RESULT=FAIL %s\n' "concise failure reason" \
  > /tmp/agent-framework-harness-smoke-result
```

The agent must write the marker through a Bash tool call, never merely mention
it in prose. The PASS file must contain exactly one line and no extra bytes.

- [ ] **Step 6: Validate fixture discovery and change-gated selection**

Run:

```bash
python3 scripts/build-test-matrix.py
python3 - <<'PY'
from pathlib import Path
import yaml
data = yaml.safe_load(Path(".github/skill-deps.yml").read_text())
entry = data["skills"]["agent-framework-harness"]
assert entry["depends_on"] == ["foundry-hosted-agents"]
assert Path(
    "skills/agent-framework-harness/test-fixture/consumer_prompt.md"
).is_file()
print("fixture registration: OK")
PY
```

Expected: the matrix output includes `agent-framework-harness`; the focused
script prints `fixture registration: OK`.

- [ ] **Step 7: Commit the live fixture contract**

Run:

```bash
git add \
  .github/skill-deps.yml \
  skills/agent-framework-harness/test-fixture/consumer_prompt.md
git commit -m "test(agent-framework-harness): add live Foundry smoke

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit containing only fixture registration and the fixture.

---

### Task 8: Patch only the three necessary adjacent routing contracts

**Files:**
- Modify: `skills/foundry-hosted-agents/SKILL.md`
- Modify: `skills/foundry-agt/SKILL.md`
- Modify: `skills/foundry-skill-catalog/SKILL.md`
- Do not modify: `skills/foundry-evals/SKILL.md`

- [ ] **Step 1: Update hosted-agent routing and PATCH version**

In `skills/foundry-hosted-agents/SKILL.md`:

- bump `metadata.version` from `2.1.1` to `2.1.2`;
- replace the frontmatter description with this 880-character folded value:

```yaml
description: >
  Deploy and manage Foundry hosted agents: GA container deploy through unified azure.yaml and azd, MAF 1.13, microsoft.foundry extension, implicit agent access, ResponsesHostServer, ACR, identity, rollout, and troubleshooting. USE FOR: deploy foundry agent, hosted agent, container agent, azure.yaml, azd ai agent, FoundryChatClient, ResponsesHostServer, ACR push, agent identity, Foundry User, Responses/Invocations protocols, Activity protocol, blue-green deploy, canary, rollback, traffic routing, version_selector, agent_endpoint, update_details. DO NOT USE FOR: create_harness_agent runtime composition (use agent-framework-harness); prompt agents (use foundry-prompt-agents); ACA MCP (use foundry-mcp-aca); GHCP agents (use ghcp-hosted-agents); Citadel (use citadel-hub-deploy); continuous eval (use foundry-evals); routines (use foundry-routines); A2A (use foundry-toolbox).
```

- add one routing row near the existing “which path” table:
  “Build an already-hostable Agent with `create_harness_agent`” →
  `agent-framework-harness`;
- state once near the `ResponsesHostServer` runtime section that this skill
  hosts/deploys the returned Agent, while the Harness skill owns factory
  composition.

- [ ] **Step 2: Update AGT routing and PATCH version**

In `skills/foundry-agt/SKILL.md`:

- bump `metadata.version` from `1.3.1` to `1.3.2`;
- replace the frontmatter description with this 866-character folded value:

```yaml
description: >
  Wrap the Microsoft Agent Governance Toolkit (AGT) around Foundry hosted agents, MCP servers, and Citadel spokes. Adds deterministic policy enforcement, capability allow/deny, hash-chained audit, OWASP ASI 2026 coverage, MAF middleware, ACA sidecar patterns, starter policies, and field-tested known issues. USE FOR: agent governance, agent-governance-toolkit, deterministic policy, capability guard, audit trail, OWASP ASI 2026, MAF middleware, MCP scanner, PromptDefense, Citadel adapter, agt verify, agt doctor, agt red-team, ACS policy, guardrail decision, AGT vs GuardrailTool. DO NOT USE FOR: create_harness_agent runtime scaffolding or approval UX (use agent-framework-harness); Foundry deployment (use foundry-hosted-agents); Citadel hub setup (use citadel-spoke-onboarding); App Insights wiring (use foundry-observability); eval scoring (use foundry-evals).
```

- add one row to “What AGT isn't”: Harness modes/todos/compaction/native
  approval UX → `agent-framework-harness`;
- explicitly state native Harness approval is caller interaction, not AGT
  policy enforcement.

- [ ] **Step 3: Update Foundry Skills routing and PATCH version**

In `skills/foundry-skill-catalog/SKILL.md`:

- bump `metadata.version` from `1.2.3` to `1.2.4`;
- replace the frontmatter description with this 791-character folded value:

```yaml
description: >
  Store and distribute instruction-only SKILL.md files through the Foundry Skills REST API ({project}/skills), then consume them from MAF agents through FoundrySkillsSource and SkillsProvider. Covers JSON versus ZIP modes, the JSON write-only trap, mandatory Foundry-Features: Skills=V1Preview header, quoted-frontmatter HTTP 500, allow_preview=True, and runtime fetch. USE FOR: Foundry skills, central skill store, client.beta.skills, has_blob, create_from_package, FoundrySkillsSource, SkillsProvider with Foundry, skills:import, skills:download. DO NOT USE FOR: awesome-gbb skill authoring; create_harness_agent runtime composition or file-system skills wiring (use agent-framework-harness); Foundry tools (use foundry-toolbox); general hosted-agent deployment (use foundry-hosted-agents).
```

- add one routing row distinguishing Foundry Skills REST distribution from
  Harness-local `SkillsProvider`/`skills_paths` composition.

- [ ] **Step 4: Verify description lengths and version bumps**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
expected = {
    "foundry-hosted-agents": "2.1.2",
    "foundry-agt": "1.3.2",
    "foundry-skill-catalog": "1.2.4",
}
for skill, version in expected.items():
    p = Path("skills") / skill / "SKILL.md"
    data = yaml.safe_load(p.read_text().split("---", 2)[1])
    print(skill, len(data["description"]), data["metadata"]["version"])
    assert len(data["description"]) <= 1024
    assert data["metadata"]["version"] == version
PY
```

Expected lengths: `880`, `866`, and `791`, including YAML's folded-scalar
trailing newline.

- [ ] **Step 5: Inspect the adjacent-skill diff for scope**

Run:

```bash
git --no-pager diff -a -- \
  skills/foundry-hosted-agents/SKILL.md \
  skills/foundry-agt/SKILL.md \
  skills/foundry-skill-catalog/SKILL.md
```

Expected: only frontmatter description/version changes and the three narrow
routing clarifications. No code sample, pin, reference, deployment, policy,
or REST behavior changes.

- [ ] **Step 6: Commit with both required cross-skill gate tags**

Run:

```bash
git add \
  skills/foundry-hosted-agents/SKILL.md \
  skills/foundry-agt/SKILL.md \
  skills/foundry-skill-catalog/SKILL.md
git commit -m "[multi-skill][skill-rewrite] docs: route harness ownership

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit with exactly three adjacent skill files and both gate
tags.

---

### Task 9: Register the skill in the public catalog and plugin manifests

**Files:**
- Modify: `README.md`
- Modify: `scripts/build-site.py`
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`
- Modify: `AGENTS.md`

- [ ] **Step 1: Add the README catalog row**

In the Foundry Building Blocks table in `README.md`, add this row next to
`foundry-hosted-agents`:

```markdown
| [agent-framework-harness](skills/agent-framework-harness/) | Build MAF `create_harness_agent` runtimes with accurate defaults, compaction, plan/execute modes, recovery, bounded loops, and Hosted Agents adapter wiring |
```

Update visible top-level catalog prose from 35 to 36 skills. Also correct any
older visible total that still says 28 skills so the README has one current
count; do not rewrite unrelated catalog descriptions.

- [ ] **Step 2: Add the site category entry**

In `scripts/build-site.py`, add `"agent-framework-harness"` to the Foundry
Building Blocks `CATEGORIES` list immediately before or after
`"foundry-hosted-agents"`.

Run:

```bash
python3 - <<'PY'
import scripts.build_site as site
matches = [
    category for category, skills in site.CATEGORIES.items()
    if "agent-framework-harness" in skills
]
assert len(matches) == 1, matches
print(matches[0])
PY
```

Expected: the Foundry Building Blocks category name.

- [ ] **Step 3: MINOR-bump and update `plugin.json`**

Change:

- `"version": "4.29.5"` to `"version": "4.30.0"`;
- the public description count from 35 to 36;
- no plugin name, skills path, keyword, or install surface.

- [ ] **Step 4: Match both marketplace version/count surfaces**

In `.github/plugin/marketplace.json`, change both version fields from
`4.29.5` to `4.30.0` and both visible 35-skill descriptions to 36. Do not add
a second plugin entry.

- [ ] **Step 5: Update both AGENTS.md coverage tables consistently**

In `AGENTS.md`, update the stale “Current coverage” block and “Catalog at a
glance” values to:

| Metric | New value |
|---|---|
| Total skills | 36 |
| Skills with upstream pins | 32 |
| Auto-tier runnable pins | 26 |
| Auto-tier non-runnable CI pins | 3 |
| Total auto-tier pins | 29 |
| Issue-only pins | 3 |
| Internal IP/no pin | 4 |
| Copilot CLI fixtures | 21 |

Do not change workflow counts, unit-test counts, E2E inventory, design
philosophy, or fixture patterns.

- [ ] **Step 6: Verify manifest consistency and computed counts**

Run:

```bash
python3 scripts/build-plugins.py --check
python3 - <<'PY'
from pathlib import Path
import json
import yaml

plugin = json.loads(Path("plugin.json").read_text())
market = json.loads(Path(".github/plugin/marketplace.json").read_text())
assert plugin["version"] == "4.30.0"
assert market["metadata"]["version"] == "4.30.0"
assert market["plugins"][0]["version"] == "4.30.0"

skills = list(Path("skills").glob("*/SKILL.md"))
pins = list(Path("skills").glob("*/references/upstream-pin.md"))
fixtures = list(Path("skills").glob("*/test-fixture/consumer_prompt.md"))
auto = 0
for pin in pins:
    data = yaml.safe_load(pin.read_text().split("---", 2)[1])
    auto += data.get("automation_tier") == "auto"
assert (len(skills), len(pins), auto, len(fixtures)) == (36, 32, 29, 21)
print("catalog counts: 36 skills, 32 pins, 29 auto, 21 fixtures")
PY
```

Expected: plugin check succeeds and the exact count line prints.

- [ ] **Step 7: Commit catalog registration**

Run:

```bash
git add \
  README.md \
  scripts/build-site.py \
  plugin.json \
  .github/plugin/marketplace.json \
  AGENTS.md
git commit -m "feat: register agent framework harness

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one commit containing only hand-authored catalog registration and
count files.

---

### Task 10: Rebuild static docs

**Files:**
- Generate: `docs/skills/agent-framework-harness/index.html`
- Generate: `docs/index.html`
- Generate: `docs/skills/index.html`
- Generate: `docs/plugins/index.html`
- Generate: `docs/plugins/awesome-gbb/index.html`
- Generate: `docs/llms.txt`
- Preserve: `docs/superpowers/specs/2026-08-05-agent-framework-harness-design.md`
- Preserve: `docs/superpowers/plans/2026-08-05-agent-framework-harness.md`

- [ ] **Step 1: Build and validate the static site**

Run:

```bash
python3 scripts/build-site.py --out docs/ --validate
```

Expected: exit 0, links validate, and the new skill page is generated.

- [ ] **Step 2: Verify the generated skill page and indexes**

Run:

```bash
test -f docs/skills/agent-framework-harness/index.html
rg -n "agent-framework-harness|Agent Framework Harness" \
  docs/index.html \
  docs/skills/index.html \
  docs/plugins/awesome-gbb/index.html \
  docs/llms.txt \
  docs/skills/agent-framework-harness/index.html
```

Expected: every listed generated surface references the new skill.

- [ ] **Step 3: Check that hand-authored superpowers docs remain intact**

Run:

```bash
test -f docs/superpowers/specs/2026-08-05-agent-framework-harness-design.md
test -f docs/superpowers/plans/2026-08-05-agent-framework-harness.md
```

Expected: both files still exist after site generation.

- [ ] **Step 4: Inspect generated-file scope**

Run:

```bash
git --no-pager diff --name-only | sort
```

Expected generated changes are limited to the documented site outputs plus
any additional generated index the builder deterministically refreshes. Do
not manually edit generated HTML to reduce the diff.

- [ ] **Step 5: Commit generated docs separately**

Run:

```bash
git add docs/
git commit -m "docs: publish agent framework harness catalog page

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 99ccd83c-fcf6-4b04-b25f-b54b0c978a85"
```

Expected: one generated-docs commit; the approved spec and this plan are not
modified by the build.

---

### Task 11: Run the complete local validation stack

**Files:**
- Test: all implementation files from Tasks 2-10
- No new files

- [ ] **Step 1: Run the canonical offline smoke in the isolated venv**

Run:

```bash
/tmp/agent-framework-harness-plan-venv/bin/python \
  skills/agent-framework-harness/references/python/test_harness_contract.py
```

Expected:

```text
HARNESS_SIGNATURE_OK
HARNESS_DEFAULTS_OK
HARNESS_COMPACTION_OK
HARNESS_CONSTRUCTION_OK
HOSTING_IMPORT_OK
```

- [ ] **Step 2: Run catalog validation**

Run:

```bash
python3 scripts/validate-skills.py
```

Expected: exit 0 with no missing frontmatter, description-length, SemVer,
reference-anchor, pin-schema, dependency-graph, forbidden-string, or
deprecated-API errors.

- [ ] **Step 3: Run plugin structure validation**

Run:

```bash
python3 scripts/build-plugins.py --check
```

Expected: exit 0; single-plugin structure and version consistency pass.

- [ ] **Step 4: Run pin validation**

Run:

```bash
python3 scripts/run-pin-validation.py
```

Expected: the changed Harness pin runs its script and all five expected
substrings are present. Existing pins also pass according to the repository's
changed-file selection behavior.

- [ ] **Step 5: Run the repository unit suite**

Run:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
```

Expected: all existing tests pass; no new test runner or dependency is added.

- [ ] **Step 6: Re-run site validation without producing a diff**

Run:

```bash
python3 scripts/build-site.py --out docs/ --validate
git diff --exit-code -- docs/
```

Expected: build succeeds and generated docs are already current.

- [ ] **Step 7: Run mechanical diff checks**

Run:

```bash
git diff -a --check main...HEAD
git --no-pager diff -a --stat main...HEAD
git --no-pager diff -a main...HEAD -- \
  'skills/*/references/data-realism/*'
```

Expected: no whitespace errors; the data-realism diff is empty.

- [ ] **Step 8: Scan for forbidden or unfinished content**

Run:

```bash
if rg -n '\b(TBD|TODO|FIXME|implement later)\b|similar to Task' \
  skills/agent-framework-harness
then
  exit 1
fi
git --no-pager diff -a main...HEAD |
  rg -n 'kyc-poc|card-dispute-investigation|threadlight-v[123]|subscriptions/[0-9a-fA-F]{8}-' &&
  exit 1 || true
```

Expected: no placeholder, PoC, customer, or real subscription identifier is
found.

- [ ] **Step 9: Remove the named local validation environments**

Run:

```bash
rm -rf \
  /tmp/agent-framework-harness-plan-venv \
  /tmp/agent-framework-harness-pin
```

Expected: only those two task-specific temporary environments are removed.

- [ ] **Step 10: Verify the final worktree contains no uncommitted files**

Run:

```bash
git status --short
```

Expected: empty output.

---

### Task 12: Obtain and document required Azure T3 evidence

**Files:**
- Test: `skills/agent-framework-harness/test-fixture/consumer_prompt.md`
- No implementation changes unless the fixture exposes a real defect

- [ ] **Step 1: Push the implementation branch and open a PR**

Run:

```bash
git push -u origin HEAD
gh pr create \
  --title "Add Agent Framework Harness skill" \
  --body "## Summary
- add the canonical create_harness_agent runtime skill and references
- add offline signature/default/construction validation
- add a registered live Foundry T3 fixture

## Validation
- local T0/T1/T2 validation passed
- Azure T3 evidence will be added from the copilot-cli-matrix run before merge

## Scope
- no deployment, RBAC, governance, Skills REST, or eval ownership added"
```

Expected: a PR URL. The PR is not merge-ready until the live fixture passes.

- [ ] **Step 2: Confirm change-gated matrix selection**

Run:

```bash
PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr checks "$PR_NUMBER" --watch
```

Expected: the `copilot-cli-matrix` includes
`agent-framework-harness`; dependent fanout may include
`foundry-hosted-agents` according to the changed-skill graph. Required T0 and
pin gates also pass.

- [ ] **Step 3: Inspect the live fixture transcript and marker outcome**

Run:

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" \
  --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run view "$RUN_ID" --log |
  rg -n "agent-framework-harness|HARNESS_REFERENCE_IMPORT_OK|HARNESS_AGENT_CONSTRUCTED|HOSTING_ADAPTER_CONSTRUCTED|HARNESS_LIVE_RESPONSE_OK|PASS via marker file"
```

Expected evidence:

```text
HARNESS_REFERENCE_IMPORT_OK
HARNESS_AGENT_CONSTRUCTED
HOSTING_ADAPTER_CONSTRUCTED
HARNESS_LIVE_RESPONSE_OK
PASS via marker file
```

If the matrix is still running, wait for its completion notification rather
than dispatching duplicate runs. If it fails, classify the failure using the
existing workflow retry/fixture patterns; fix only a reproducible Harness
contract defect, not transient Azure/model behavior already covered by the
workflow.

- [ ] **Step 4: Add the live evidence to the PR body**

Run:

```bash
PR_NUMBER="$(gh pr view --json number --jq .number)"
RUN_URL="$(gh run view "$RUN_ID" --json url --jq .url)"
gh pr edit "$PR_NUMBER" --body "## Summary
- add the canonical create_harness_agent runtime skill and references
- add offline signature/default/construction validation
- add a registered live Foundry T3 fixture

## Validation
- local T0/T1/T2 validation passed
- Azure T3: $RUN_URL
- live evidence: HARNESS_REFERENCE_IMPORT_OK, HARNESS_AGENT_CONSTRUCTED, HOSTING_ADAPTER_CONSTRUCTED, HARNESS_LIVE_RESPONSE_OK, deterministic PASS marker

## Scope
- no deployment, RBAC, governance, Skills REST, or eval ownership added"
```

Expected: the PR description links the successful run and names the verified
live surfaces, satisfying AGENTS.md section 2.9.

- [ ] **Step 5: Confirm final PR scope and checks**

Run:

```bash
gh pr diff "$PR_NUMBER" --name-only
gh pr checks "$PR_NUMBER"
```

Expected: only the mapped implementation, adjacent routing, catalog, and
generated-doc files appear; all required checks and the Harness T3 leg are
green.

---

## Final self-review checklist

Run this review after all tasks and before requesting merge:

- [ ] Every approved design section maps to a skill section, reference, test,
      fixture, routing patch, or catalog task above.
- [ ] `create_harness_agent` defaults and provider/middleware order match the
      immutable 1.13.0 source and offline smoke.
- [ ] Compaction is described as inactive without both budgets or explicit
      custom phase strategies.
- [ ] Web search is described as not disabled by default but conditional on
      client capability.
- [ ] Approval middleware is described as default-on with no caller heuristic
      rules unless supplied, and as UX rather than governance.
- [ ] Todo, mode, and file memory are default-on; file access, skills,
      background agents, shell, and looping are opt-in.
- [ ] Every looping recipe uses a positive `loop_max_iterations=10`.
- [ ] Local, hosted, plan/execute, session recovery, and offline smoke code
      each have exactly one canonical Python source.
- [ ] Every reference header resolves to an exact `SKILL.md` heading.
- [ ] `ResponsesHostServer` receives an already-built Agent and is never
      described as the factory.
- [ ] `default_options={"store": False}` survives factory merging and appears
      in the hosted canonical source.
- [ ] Hosted service status and Python hosting-adapter package status remain
      separate.
- [ ] Shell workdir/deny-list controls are explicitly non-sandboxing.
- [ ] The skill does not absorb deployment/RBAC/lifecycle, AGT governance,
      Foundry Skills REST distribution, or general eval ownership.
- [ ] Plugin and marketplace versions both equal `4.30.0`.
- [ ] Computed totals equal 36 skills, 32 pins, 29 auto-tier pins, and 21
      fixtures.
- [ ] Offline T0/T1/T2 validation is green and the PR body links green Azure
      T3 evidence.
