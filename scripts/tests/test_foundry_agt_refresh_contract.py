"""Contract tests for the foundry-agt 2.0 manual-hygiene refresh."""

from __future__ import annotations

import asyncio
import importlib.util
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-agt"


def frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    _, fm, body = raw.split("---", 2)
    return yaml.safe_load(fm), body


# Load the skill's contract_probe.py under a UNIQUE module name to avoid
# sys.modules collision with any other skill's same-named probe file when
# multiple test files run in the same `unittest discover` session. All of
# contract_probe.py's module-level imports are stdlib-only (agent_os /
# agent_framework imports are deferred inside its functions), so this
# exec_module succeeds without the pinned packages installed and without
# any network access — giving real, executable proof of its helper
# functions' behaviour rather than relying on static source-text matching
# alone. See test_unit_foundry_rbac_audit.py for the canonical pattern.
_CONTRACT_PROBE_PY = SKILL / "references" / "python" / "contract_probe.py"
_contract_probe_spec = importlib.util.spec_from_file_location(
    "foundry_agt_contract_probe", _CONTRACT_PROBE_PY
)
foundry_agt_contract_probe = importlib.util.module_from_spec(_contract_probe_spec)
sys.modules["foundry_agt_contract_probe"] = foundry_agt_contract_probe
_contract_probe_spec.loader.exec_module(foundry_agt_contract_probe)


def _stub_agent(*middlewares: object) -> SimpleNamespace:
    return SimpleNamespace(middleware=list(middlewares))


class _StubAuditLog:
    """Minimal stand-in exposing only ``export_cloudevents()`` — the sole
    real ``AuditLog`` surface ``assert_v4_audit_attribution`` actually
    calls — plus an ``append`` helper tests use to simulate what the real
    ``GovernancePolicyMiddleware._process_v4`` writes to it on ``.process``.
    """

    def __init__(self) -> None:
        self._events: list[dict] = []

    def export_cloudevents(self) -> list[dict]:
        return list(self._events)

    def append(self, event: dict) -> None:
        self._events.append(event)


class _StubV4GovernancePolicyMiddleware:
    """Minimal stand-in whose ``process()`` mirrors the real legacy v4
    ``_process_v4`` audit-logging behaviour this proof depends on: for a
    benign message it appends a CloudEvent-shaped dict — with ``source``
    set to whatever this test tells it to attribute the decision to — to
    its bound ``audit_log``, and calls ``call_next`` some controllable
    number of times, so tests can exercise both the correct-attribution
    path and every real failure mode the helper must catch.
    """

    def __init__(
        self,
        audit_log: object,
        *,
        emitted_source: str,
        emit_count: int = 1,
        call_next_calls: int = 1,
    ) -> None:
        self.audit_log = audit_log
        self._emitted_source = emitted_source
        self._emit_count = emit_count
        self._call_next_calls = call_next_calls

    async def process(self, context: object, call_next) -> None:
        for _ in range(self._emit_count):
            self.audit_log.append(
                {"type": "ai.agentmesh.policy.evaluation", "source": self._emitted_source}
            )
        for _ in range(self._call_next_calls):
            await call_next()


def _stub_v4_ns() -> SimpleNamespace:
    return SimpleNamespace(
        GovernancePolicyMiddleware=_StubV4GovernancePolicyMiddleware,
        AgentContext=lambda agent, messages: SimpleNamespace(agent=agent, messages=messages),
        Message=lambda role, parts: SimpleNamespace(role=role, parts=parts),
    )


class FoundryAgtRefreshContractTests(unittest.TestCase):
    def test_skill_is_major_and_path_a_only(self) -> None:
        meta, body = frontmatter(SKILL / "SKILL.md")
        self.assertEqual(meta["metadata"]["version"], "2.0.0")

        description = meta["description"].lower()
        for forbidden in ("aca sidecar", "citadel adapter", "26.67", "0.00%"):
            self.assertNotIn(forbidden, description)

        # The description must NOT make the unconditional claim that
        # CapabilityGuardMiddleware is always wired alongside
        # AuditTrailMiddleware and GovernancePolicyMiddleware; upstream
        # AGT 4.1 factory only adds CapabilityGuard when allowed_tools
        # or denied_tools is not None.  The exact phrase
        # "wires AuditTrailMiddleware, GovernancePolicyMiddleware, and
        # CapabilityGuardMiddleware" (case-insensitive) is forbidden.
        self.assertNotIn(
            "wires audittrailmiddleware, governancepolicymiddleware, and capabilityguardmiddleware",
            description,
            "description must not unconditionally claim CapabilityGuardMiddleware "
            "is always wired; it is added by the factory only when allowed_tools "
            "or denied_tools is configured",
        )

        # The description must clearly convey that CapabilityGuard
        # per-tool gating is conditional: it is applied only when
        # allowed_tools or denied_tools are configured.
        desc_conditional_guard_pattern = re.compile(
            r"capabilityguard.{0,400}"
            r"(only when|when.{0,60}configured|conditional).{0,200}"
            r"(allowed_tools|denied_tools)",
            re.DOTALL,
        )
        self.assertRegex(
            description,
            desc_conditional_guard_pattern,
            "description must clearly state that CapabilityGuard per-tool "
            "gating is conditional when allowed_tools or denied_tools are "
            "configured",
        )

        changelog_index = body.find("## GBB Changelog")
        self.assertNotEqual(changelog_index, -1, "GBB Changelog heading not found")
        active_body_original = body[:changelog_index]
        active_body = active_body_original.lower()
        for forbidden in (
            "## path b",
            "## path c",
            "mcr.microsoft.com/agentmesh/enforcer",
            "26.67% policy-violation rate",
            "0.00% violation",
            "hitl-gate",
            "outbound text",
            "assembles the following three middleware",
        ):
            self.assertNotIn(forbidden, active_body)

        # CapabilityGuardMiddleware is conditional: upstream's factory only
        # adds it to the stack when allowed_tools or denied_tools is not
        # None (AuditTrail + GovernancePolicy are the only unconditional
        # members). The active SKILL must say so precisely instead of
        # claiming an unconditional three-item stack. Wording-robust,
        # truth-specific: look for "only when" near CapabilityGuardMiddleware
        # plus the deciding parameter names.
        conditional_guard_pattern = re.compile(
            r"capabilityguardmiddleware.{0,400}only when.{0,200}"
            r"(allowed_tools|denied_tools)",
            re.DOTALL,
        )
        self.assertRegex(
            active_body,
            conditional_guard_pattern,
            "SKILL.md must describe CapabilityGuardMiddleware as "
            "conditional on allowed_tools/denied_tools, not unconditional",
        )

        # Tool-audit scope: AuditTrailMiddleware hash-chains
        # agent-invocation start/complete entries only, never individual
        # tool calls. Only CapabilityGuardMiddleware, when explicitly
        # configured with allowed_tools/denied_tools, adds tool-invoked /
        # tool-blocked audit entries. The active SKILL must not claim an
        # unconditional, per-tool-call audit record.
        self.assertNotIn(
            "tamper-evident record of every tool call",
            active_body,
            "SKILL.md must not claim a tamper-evident record of every "
            "tool call unconditionally — CapabilityGuardMiddleware's "
            "tool-invoked/tool-blocked audit entries are conditional on "
            "explicit allowed_tools/denied_tools configuration, not "
            "automatic",
        )
        self.assertNotRegex(
            active_body,
            re.compile(r"audittrailmiddleware.{0,150}every tool call", re.DOTALL),
            "SKILL.md must not claim AuditTrailMiddleware covers 'every "
            "tool call' — it hash-chains agent-invocation start/complete "
            "entries only, never individual tool calls",
        )

        when_to_use_start = active_body.find("## when to use this skill")
        when_not_to_use_start = active_body.find("## when not to use this skill")
        self.assertNotEqual(when_to_use_start, -1, "'When to use this skill' heading not found")
        self.assertNotEqual(
            when_not_to_use_start, -1, "'When NOT to use this skill' heading not found"
        )
        when_to_use_section = active_body[when_to_use_start:when_not_to_use_start]

        self.assertRegex(
            when_to_use_section,
            re.compile(
                r"audittrailmiddleware.{0,150}"
                r"hash-chained.{0,100}"
                r"(agent-invocation|agent invocation).{0,60}"
                r"start.{0,40}complete",
                re.DOTALL,
            ),
            "'When to use this skill' must state AuditTrailMiddleware "
            "always hash-chains an agent-invocation start/complete entry",
        )
        self.assertRegex(
            when_to_use_section,
            re.compile(
                r"capabilityguardmiddleware.{0,100}"
                r"when explicitly configured.{0,150}"
                r"(allowed_tools|denied_tools).{0,200}"
                r"(tool-invoked|tool invoked).{0,60}"
                r"(tool-blocked|tool blocked)",
                re.DOTALL,
            ),
            "'When to use this skill' must state tool-invoked/tool-blocked "
            "evidence is conditional on explicitly configuring "
            "CapabilityGuardMiddleware with allowed_tools/denied_tools",
        )

        middleware_section_start = active_body.find("### middleware factory stack")
        policy_yaml_start = active_body.find("### policy yaml")
        self.assertNotEqual(
            middleware_section_start, -1, "'Middleware factory stack' heading not found"
        )
        self.assertNotEqual(policy_yaml_start, -1, "'Policy YAML' heading not found")
        middleware_section = active_body[middleware_section_start:policy_yaml_start]

        self.assertRegex(
            middleware_section,
            re.compile(
                r"audittrailmiddleware.{0,150}"
                r"(agent-invocation|agent invocation).{0,80}"
                r"start.{0,60}complete",
                re.DOTALL,
            ),
            "Middleware factory stack list must describe "
            "AuditTrailMiddleware as logging agent-invocation "
            "start/complete entries only",
        )
        self.assertRegex(
            middleware_section,
            re.compile(
                r"capabilityguardmiddleware.{0,400}"
                r"when configured.{0,200}"
                r"(tool-invoked|tool invoked).{0,60}"
                r"(tool-blocked|tool blocked).{0,200}"
                r"in addition to",
                re.DOTALL,
            ),
            "Middleware factory stack list must state that "
            "CapabilityGuardMiddleware, when configured, also logs "
            "tool-invoked/tool-blocked audit entries in addition to "
            "gating",
        )
        self.assertRegex(
            middleware_section,
            re.compile(
                r"no.{0,15}capabilityguardmiddleware.{0,300}"
                r"(no|none).{0,40}(tool-invoked|tool invoked).{0,60}"
                r"(tool-blocked|tool blocked).{0,300}"
                r"(still execute|execute normally).{0,300}"
                r"not guard-audited",
                re.DOTALL,
            ),
            "Middleware factory stack must state the no-guard default "
            "yields no tool-invoked/tool-blocked audit entries — tools "
            "still execute via the runtime but are simply not "
            "guard-audited at the tool level",
        )

        # Verification table: build_factory_stack proves middleware-type
        # *membership* for a configured stack, never ordering; the
        # check_snippet_import row is the one that proves the factory's
        # preserved order plus allowed_tools=None/denied_tools=None
        # default (no-guard) semantics. Locate each row precisely so the
        # assertion is robust to prose wording but specific about which
        # evidence function backs which claim.
        factory_row_match = re.search(
            r"^\|.*build_factory_stack.*\|\s*$",
            active_body_original,
            re.MULTILINE,
        )
        self.assertIsNotNone(
            factory_row_match,
            "no verification row cites contract_probe.py::build_factory_stack",
        )
        self.assertNotIn("order", factory_row_match.group(0).lower())

        snippet_row_match = re.search(
            r"^\|.*check_snippet_import.*\|\s*$",
            active_body_original,
            re.MULTILINE,
        )
        self.assertIsNotNone(
            snippet_row_match,
            "no verification row cites contract_probe.py::check_snippet_import",
        )
        snippet_row_lower = snippet_row_match.group(0).lower()
        self.assertIn("order", snippet_row_lower)
        self.assertIn("default", snippet_row_lower)

        # Rogue-detection upstream-default must be qualified in the active SKILL.
        # The SKILL must NOT make the unqualified claim "always assembles two
        # middleware when a policy_directory is supplied" — that is only true for
        # the snippet's proved path (enable_rogue_detection=False); upstream AGT
        # 4.1 factory default is True, which adds RogueDetection as a third
        # unconditional member.  The active SKILL must also: (a) state the
        # upstream AGT 4.1 factory default for enable_rogue_detection is True
        # (omitting the flag adds RogueDetectionMiddleware); and (b) state that
        # the canonical snippet explicitly overrides this to False until the
        # caller establishes a capability profile.
        self.assertNotRegex(
            active_body,
            re.compile(
                r"always assembles two middleware.{0,30}when.{0,20}policy_directory",
                re.DOTALL,
            ),
            "Active SKILL must not make the unqualified claim 'always assembles "
            "two middleware when a policy_directory is supplied' — that is only "
            "true for the snippet's proved path (enable_rogue_detection=False); "
            "upstream AGT 4.1 factory default is True, which adds RogueDetection.",
        )
        self.assertRegex(
            active_body,
            re.compile(
                r"(agt 4\.1|upstream).{0,400}enable_rogue_detection.{0,200}true",
                re.DOTALL,
            ),
            "Active SKILL must state that the upstream AGT 4.1 factory default "
            "for enable_rogue_detection is True; omitting the flag adds "
            "RogueDetectionMiddleware.",
        )
        self.assertRegex(
            active_body,
            re.compile(
                r"(snippet|canonical).{0,600}"
                r"(explicit|intentional|override).{0,300}"
                r"(false|enable_rogue_detection=false)",
                re.DOTALL,
            ),
            "Active SKILL must state that the canonical snippet explicitly "
            "overrides enable_rogue_detection to False until the caller "
            "establishes a capability profile.",
        )

        # Ownership-table AGT row: must NOT claim argument-level gating.
        body_plain = re.sub(r"[*_]", "", active_body)
        self.assertNotIn(
            "allowed to invoke this tool with these arguments",
            body_plain,
            "Ownership-table AGT row must not claim argument-level gating; "
            "AGT gates by tool name, not by argument values.",
        )

        # Ownership-table AGT row: must describe named-tool pre-execution gating.
        has_named_tool = "named tool" in body_plain or "tool name" in body_plain or "named-tool" in body_plain
        self.assertTrue(
            has_named_tool,
            "Ownership-table AGT row must describe pre-execution gating by "
            "tool name (e.g. 'named tool', 'tool name', or 'named-tool').",
        )

    def test_compliance_wording_is_precise(self) -> None:
        _, body = frontmatter(SKILL / "SKILL.md")
        changelog_index = body.find("## GBB Changelog")
        self.assertNotEqual(changelog_index, -1, "GBB Changelog heading not found")
        active_body = body[:changelog_index]
        changelog_body = body[changelog_index:]

        self.assertIn("self-assessment", active_body)
        self.assertIn("not certification", active_body)
        self.assertIn("live_t3_probe.py", active_body)
        for forbidden in (
            "certifies compliance",
            "certification proof",
            "independent audit proof",
            "ci-gateable proof of compliance",
            "guarantees owasp compliance",
            "not yet proved at this pin",
            "pending a live probe run",
        ):
            self.assertNotIn(forbidden, active_body.lower())

        # Verification-status T3 row: the durable skill body must state a
        # PROCESS REQUIREMENT that is truthful both before and after any
        # given CI run — "exact-head" + "required before merge"/
        # "acceptance" wording — never a pre-claim that every local source
        # commit has already been proved live (that overclaims the instant
        # a new commit lands, which is exactly the bug this locks down).
        active_body_lower = active_body.lower()
        self.assertIn("exact-head", active_body_lower)
        self.assertRegex(
            active_body_lower,
            re.compile(r"required before merge|acceptance"),
            "T3 verification row must require exact-head merge "
            "acceptance, not predeclare it as already proved",
        )
        for forbidden in (
            "proved at the exact-head commit",
            "re-run and re-accepted at every source-touching commit",
        ):
            self.assertNotIn(forbidden, active_body_lower)

        # The GBB Changelog entry for this release must describe the same
        # requirement (live T3 landed + exact-head artifact acceptance is
        # a merge gate), not an already-banked proof that ages the moment
        # the next source commit lands.
        changelog_lower = changelog_body.lower()
        self.assertIn("live_t3_probe.py", changelog_lower)
        self.assertIn("exact-head", changelog_lower)
        self.assertRegex(
            changelog_lower,
            re.compile(r"required before merge|acceptance"),
            "Changelog v2.0.0 entry must require exact-head artifact "
            "acceptance before merge, not predeclare it as already proved",
        )
        for forbidden in (
            "proved at the exact-head commit",
            "re-run and re-accepted at every source-touching commit",
        ):
            self.assertNotIn(forbidden, changelog_lower)

    def test_pin_uses_released_source_and_selective_set(self) -> None:
        pin_meta, pin_body = frontmatter(SKILL / "references" / "upstream-pin.md")

        self.assertEqual(pin_meta["automation_tier"], "issue_only")
        self.assertEqual(pin_meta["upstream"]["ref"], "v4.1.0")
        self.assertEqual(
            pin_meta["upstream"]["pinned_sha"],
            "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258",
        )

        expected_packages = {
            "agent-governance-toolkit": "4.1.0",
            "agent-framework-core": "1.13.0",
            "agent-framework-foundry": "1.10.4",
            "agent-framework-openai": "1.12.0",
            "azure-identity": "1.25.3",
        }
        actual_packages = {
            package["name"]: str(package["version"])
            for package in pin_meta["packages"]
        }
        self.assertEqual(actual_packages, expected_packages)

        validation_script = pin_meta["validation"]["script"]
        for expected_substring in (
            "agent-governance-toolkit[full]~=${PINNED_AGT_VERSION:-4.1.0}",
            "agent-framework-core~=${PINNED_AF_CORE_VERSION:-1.13.0}",
            "agent-framework-foundry~=${PINNED_AF_FOUNDRY_VERSION:-1.10.4}",
            "agent-framework-openai~=${PINNED_AF_OPENAI_VERSION:-1.12.0}",
            "azure-identity~=${PINNED_IDENTITY_VERSION:-1.25.3}",
            "references/python/contract_probe.py",
        ):
            self.assertIn(expected_substring, validation_script)
        self.assertNotIn("HITL_POLICY=PASS", validation_script)

        expected_output = pin_meta["validation"]["expected_output"]
        self.assertIn("POLICY_MIDDLEWARE=PASS", expected_output)
        self.assertNotIn("HITL_POLICY=PASS", expected_output)

        known_issues = pin_meta["known_issues"]
        self.assertEqual(len(known_issues), 2)
        self.assertEqual(pin_meta["known_issues_count"], 2)
        for issue in known_issues:
            self.assertIsNone(issue.get("upstream_url"))
            self.assertNotEqual(issue["id"], "KI-001")

        # Every remaining known issue has upstream_url: null — there is no
        # linked upstream report to track. The prose body must not describe
        # these findings as "upstream-tracked"/"upstream-reported" (both
        # phrases claim an upstream-side record that does not exist); it
        # must say the finding was empirically observed against the pinned
        # release instead, matching the frontmatter notes above.
        pin_body_lower = pin_body.lower()
        self.assertNotIn("upstream-tracked", pin_body_lower)
        self.assertNotIn("upstream-reported", pin_body_lower)
        self.assertIn(
            "empirically observed",
            pin_body_lower,
            "pin body must describe untracked findings as empirically "
            "observed, not implied to be upstream-tracked/upstream-reported",
        )

        # Upstream release note: create_governance_middleware's factory
        # default for enable_rogue_detection flipped to True at 4.1.0 (it
        # was False in the prior AGT 3.x pin). Empirically re-verified live
        # against the pinned 4.1.0 release via inspect.signature(...) — the
        # pin body must state the new upstream default precisely and must
        # not carry the stale "defaults to False" claim forward as if it
        # were still the upstream factory's own default.
        self.assertIn("enable_rogue_detection: bool = True", pin_body)
        self.assertNotIn("enable_rogue_detection: bool = False", pin_body)

        # The old unconditional "(4 items if enable_rogue_detection=True,
        # 3 otherwise)" claim ignored that allowed_tools/denied_tools
        # configuration ALSO changes the stack size independent of the
        # rogue-detection flag. Empirically re-verified: with
        # policy_directory set and nothing else configured,
        # enable_rogue_detection=False -> 2 items (AuditTrail +
        # GovernancePolicy only); either tool list configured (including
        # an empty list) with enable_rogue_detection=False -> 3 (+
        # CapabilityGuard); enable_rogue_detection=True with no tool list
        # configured -> 3 (+ RogueDetection, no guard); and
        # enable_rogue_detection=True with a tool list configured -> 4
        # (+ CapabilityGuard + RogueDetection). The pin must describe all
        # four conditional shapes instead of a single fixed "3 or 4".
        self.assertNotRegex(
            pin_body,
            re.compile(r"4 items if.{0,120}3 otherwise", re.DOTALL),
            "pin must not restate the old unconditional 4-vs-3 item claim",
        )
        for expected_count_phrase in (
            "-> 2: AuditTrailMiddleware, GovernancePolicyMiddleware",
            "-> 3: + CapabilityGuardMiddleware",
            "-> 3: + RogueDetectionMiddleware (no guard)",
            "-> 4: + CapabilityGuardMiddleware + RogueDetectionMiddleware",
        ):
            self.assertIn(
                expected_count_phrase,
                pin_body,
                "pin must precisely document each conditional middleware "
                "stack-count case (policy_directory set; tool-list "
                "configuration crossed with the explicit rogue-detection "
                "flag)",
            )

    def test_probes_cover_shapes_hook_and_live_inference(self) -> None:
        local_probe_path = SKILL / "references" / "python" / "contract_probe.py"
        live_probe_path = SKILL / "references" / "python" / "live_t3_probe.py"
        snippet_path = SKILL / "references" / "maf-middleware-snippet.py"

        self.assertTrue(local_probe_path.is_file())
        self.assertTrue(live_probe_path.is_file())
        self.assertTrue(snippet_path.is_file())

        local_probe = local_probe_path.read_text(encoding="utf-8")
        live_probe = live_probe_path.read_text(encoding="utf-8")
        snippet = snippet_path.read_text(encoding="utf-8")

        for expected_substring in (
            "FoundryChatClient",
            "StubCredential",
            "StubChatClient",
            "STUB_FOUNDRY_CONSTRUCTION=PASS",
            "STUB_RESPONSE_SHAPE=PASS",
            "FunctionInvocationContext",
            "FunctionTool",
            "CapabilityGuardMiddleware",
            "CAPABILITY_HOOK_ALLOW_EXECUTIONS=1",
            "CAPABILITY_HOOK_DENY_EXECUTIONS=0",
            "CONTRACT_PROBE=PASS",
            "AgentContext",
            "POLICY_MIDDLEWARE=PASS",
            ".invoke(arguments={}, context=",
            "SNIPPET_DEFAULT_NO_GUARD=PASS",
            "FACTORY_ROGUE_DETECTION_DEFAULT_TRUE=PASS",
        ):
            self.assertIn(expected_substring, local_probe)

        self.assertNotIn("HITL_POLICY=PASS", local_probe)
        self.assertNotIn("tool_args.amount", local_probe)

        # Parameter *presence* alone doesn't catch a silent default flip.
        # check_signatures must pull the real inspect.signature(...)
        # Parameter object for enable_rogue_detection and assert its
        # .default is True (the AGT 4.1.0 upstream factory default,
        # empirically re-verified live — it was False in the prior AGT
        # 3.x pin) — not just that the parameter name exists in the
        # signature. SIGNATURE_CONTRACT=PASS must remain gated behind
        # this assertion (i.e. it appears in source after this check).
        signature_default_match = re.search(
            r'enable_rogue_detection.*?\.default is (True|not True)',
            local_probe,
            re.DOTALL,
        )
        self.assertIsNotNone(
            signature_default_match,
            "check_signatures must assert enable_rogue_detection's actual "
            "inspect.signature(...) Parameter.default, not just its "
            "presence in the parameter set",
        )
        self.assertLess(
            local_probe.index("FACTORY_ROGUE_DETECTION_DEFAULT_TRUE=PASS"),
            local_probe.index('print("SIGNATURE_CONTRACT=PASS")'),
            "the enable_rogue_detection default assertion/marker must run "
            "before SIGNATURE_CONTRACT=PASS is printed, so a drifted "
            "default fails the contract before the gate passes",
        )

        # True-default (both allowed_tools and denied_tools OMITTED, not
        # just allowed_tools=None) construction must be exercised for
        # real, not merely asserted from docs: locate the call block and
        # confirm neither kwarg is passed to it.
        no_guard_call_match = re.search(
            r"no_guard_agent\s*=\s*snippet\.build_governed_agent\((.*?)\)\n",
            local_probe,
            re.DOTALL,
        )
        self.assertIsNotNone(
            no_guard_call_match,
            "contract_probe.py must construct a no_guard_agent via "
            "build_governed_agent with both allowed_tools and "
            "denied_tools omitted",
        )
        no_guard_call_args = no_guard_call_match.group(1)
        self.assertNotIn("allowed_tools", no_guard_call_args)
        self.assertNotIn("denied_tools", no_guard_call_args)

        # The proof must assert the exact two-item middleware stack and
        # the explicit absence of CapabilityGuardMiddleware — not just
        # print the marker.
        self.assertIn(
            'expected_no_guard_order = ["AuditTrailMiddleware", "GovernancePolicyMiddleware"]',
            local_probe,
        )
        self.assertIn("CapabilityGuardMiddleware)", local_probe)

        # The module docstring must describe the factory stack as
        # conditional (CapabilityGuardMiddleware only when configured),
        # never as an unconditional "three-middleware" assembly — that
        # phrasing is the same overclaim class §2.1/§9.7 guard against
        # for the snippet's own docstring, applied here to the probe's.
        self.assertNotIn(
            "the three-middleware governance factory stack assembles correctly",
            local_probe,
        )
        conditional_guard_in_probe_docstring = re.compile(
            r"capabilityguardmiddleware.{0,300}only when.{0,200}"
            r"(allowed_tools|denied_tools)",
            re.IGNORECASE | re.DOTALL,
        )
        self.assertRegex(
            local_probe,
            conditional_guard_in_probe_docstring,
            "contract_probe.py's module docstring must describe "
            "CapabilityGuardMiddleware as conditional, not an "
            "unconditional three-middleware stack",
        )

        # Durable validation must require the new marker at every pin
        # refresh, not just as a local nicety.
        pin_meta, _ = frontmatter(SKILL / "references" / "upstream-pin.md")
        self.assertIn(
            "SNIPPET_DEFAULT_NO_GUARD=PASS",
            pin_meta["validation"]["expected_output"],
        )

        # Empty-allowlist deny-all proof: the snippet's own docstring says
        # allowed_tools=[] means deny-all to CapabilityGuardMiddleware — but
        # nothing in the probe actually constructs that shape and drives it
        # through a real guard.process/FunctionTool.invoke round trip. A
        # hardcoded print("SNIPPET_EMPTY_ALLOWLIST_DENY_ALL=PASS") would
        # trivially satisfy a plain substring check, so this requires the
        # real construction path (an explicit empty allowed_tools=[], no
        # denied_tools) and the real invocation surface (FunctionTool,
        # FunctionInvocationContext, guard.process, MiddlewareTermination,
        # and an execution counter asserted == 0) to appear in the same
        # block that precedes the marker print.
        self.assertIn("SNIPPET_EMPTY_ALLOWLIST_DENY_ALL=PASS", local_probe)
        self.assertIn(
            "SNIPPET_EMPTY_ALLOWLIST_DENY_ALL=PASS",
            pin_meta["validation"]["expected_output"],
        )

        empty_allowlist_block_match = re.search(
            r"empty_allowlist_agent\s*=\s*snippet\.build_governed_agent\(.*?"
            r'print\("SNIPPET_EMPTY_ALLOWLIST_DENY_ALL=PASS"\)',
            local_probe,
            re.DOTALL,
        )
        self.assertIsNotNone(
            empty_allowlist_block_match,
            "contract_probe.py must construct build_governed_agent (or the "
            "factory directly) with an explicit empty allowed_tools=[] and "
            "prove deny-all in the same block that prints the marker, not "
            "print the marker independent of that construction",
        )
        empty_allowlist_block = empty_allowlist_block_match.group(0)
        for required_symbol in (
            "allowed_tools=[]",
            "empty_allowlist_guard.allowed_tools != []",
            "FunctionTool(",
            "FunctionInvocationContext(",
            "await empty_allowlist_guard.process(",
            "unlisted_tool.invoke(",
            "MiddlewareTermination",
        ):
            self.assertIn(
                required_symbol,
                empty_allowlist_block,
                "empty-allowlist deny-all proof must exercise the real "
                f"{required_symbol} path, not fake list-membership alone",
            )
        self.assertIsNotNone(
            re.search(r"\bexecutions\b\s*!=\s*0", empty_allowlist_block),
            "empty-allowlist deny-all proof must assert a real execution "
            "counter is exactly 0 (the tool function was never called), "
            "not just that MiddlewareTermination was raised",
        )

        # The v5 forward-compat construction contract
        # (assert_policy_middleware_agent_identity /
        # SNIPPET_POLICY_ID_FORWARD_COMPAT=PASS) has been removed
        # entirely: it exercised GovernancePolicyMiddleware's constructor
        # agent_id / its private ._agent_id attribute, which is read ONLY
        # by the kernel=-driven _process_v5 branch this skill never takes.
        # The legacy _process_v4 branch every construction here actually
        # exercises derives its audited agent_did from context.agent.name
        # at process-time and never reads ._agent_id at all — so passing
        # agent_id=name into the snippet's replacement construction was
        # inert configuration, and a probe built to verify that inert
        # constructor keyword is itself dead weight. The real,
        # behavioural v4 audit-attribution proof below
        # (assert_v4_audit_attribution /
        # SNIPPET_V4_AUDIT_REQUESTED_NAME=PASS) is the only proof this
        # skill needs, keeps, and asserts here.
        self.assertNotIn("SNIPPET_POLICY_ID_FORWARD_COMPAT=PASS", local_probe)
        self.assertNotIn(
            "SNIPPET_POLICY_ID_FORWARD_COMPAT=PASS",
            pin_meta["validation"]["expected_output"],
        )
        self.assertNotIn(
            "assert_policy_middleware_agent_identity",
            local_probe,
            "contract_probe.py must not define or call "
            "assert_policy_middleware_agent_identity — it is a removed, "
            "human-rejected v5 forward-compat construction contract that "
            "GovernancePolicyMiddleware's real legacy v4 audit path never "
            "exercises",
        )
        self.assertNotIn("SNIPPET_AGENT_IDENTITY=PASS", local_probe)
        self.assertNotIn(
            "SNIPPET_AGENT_IDENTITY=PASS",
            pin_meta["validation"]["expected_output"],
        )
        self.assertIn("SNIPPET_V4_AUDIT_REQUESTED_NAME=PASS", local_probe)
        self.assertIn(
            "SNIPPET_V4_AUDIT_REQUESTED_NAME=PASS",
            pin_meta["validation"]["expected_output"],
        )

        # The real v4 audit-attribution helper must exist as its own,
        # separately named function (not folded into the identity helper
        # above), placed after check_snippet_import so it doesn't disturb
        # the identity helper's own extraction boundary above.
        v4_audit_helper_match = re.search(
            r"async def assert_v4_audit_attribution\(.*?\n\n\nasync def run_probe",
            local_probe,
            re.DOTALL,
        )
        self.assertIsNotNone(
            v4_audit_helper_match,
            "contract_probe.py must define an "
            "assert_v4_audit_attribution(...) helper immediately ahead of "
            "run_probe",
        )
        v4_audit_helper_source = v4_audit_helper_match.group(0)
        for required_symbol in (
            "GovernancePolicyMiddleware",
            "len(policy_middlewares) != 1",
            "audit_log",
            "policy_middleware.audit_log is not audit_log",
            "expected_name",
            "agent.name != expected_name",
            "export_cloudevents",
            "AgentContext",
            "Message(",
            "call_next",
            "calls != 1",
            "policy_evaluation",
            "ai.agentmesh.policy.evaluation",
            'event["source"] != expected_name',
            "_process_v4",
        ):
            self.assertIn(
                required_symbol,
                v4_audit_helper_source,
                "assert_v4_audit_attribution must drive the real "
                "GovernancePolicyMiddleware.process hook with a dedicated "
                "AuditLog, a real AgentContext/Message, a counting "
                "call_next, and inspect the newly emitted CloudEvent's "
                "type/source against an explicit expected_name literal — "
                f"missing {required_symbol!r}",
            )

        # assert_v4_audit_attribution must take an explicit expected_name
        # parameter and assert it against BOTH the returned Agent's own
        # .name attribute and the emitted CloudEvent's source
        # INDEPENDENTLY — never by comparing the CloudEvent source to
        # agent.name itself (a self-referential compare that can't catch
        # either field drifting away from what the caller actually
        # requested, e.g. if a construction bug renames the returned
        # Agent post-hoc while the audit trail still faithfully echoes
        # that same, already-wrong, agent.name).
        self.assertRegex(
            v4_audit_helper_source,
            r"async def assert_v4_audit_attribution\(\s*"
            r"ns: SimpleNamespace,\s*agent: object,\s*audit_log: object,\s*"
            r"expected_name: str,?\s*\)",
            "assert_v4_audit_attribution must declare an explicit "
            "expected_name: str parameter",
        )
        self.assertNotIn(
            'event["source"] != agent.name',
            v4_audit_helper_source,
            "assert_v4_audit_attribution must not compare the emitted "
            "CloudEvent source against agent.name — that self-referential "
            "compare cannot catch agent.name itself having drifted away "
            "from the caller's requested expected_name; compare against "
            "the explicit expected_name literal instead",
        )

        # The helper's own docstring must document the empirical,
        # fresh-venv confirmation that the real installed 4.1.0
        # GovernancePolicyMiddleware stores audit_log as a genuine PUBLIC
        # instance attribute — not a defensive getattr(..., None) /
        # hasattr(...) fallback for an attribute that might not exist.
        # This is what licenses the direct
        # "policy_middleware.audit_log is not audit_log" attribute read
        # above as a real proof rather than an optimistic guess.
        for required_empirical_symbol in (
            "public instance attribute",
            "self.audit_log = audit_log",
            "inspect.getsource",
            "fresh venv",
            "not a defensive fallback",
        ):
            self.assertIn(
                required_empirical_symbol,
                v4_audit_helper_source,
                "assert_v4_audit_attribution's docstring must document the "
                "empirical, fresh-venv confirmation (via inspect.getsource "
                "on the real installed 4.1.0 "
                "GovernancePolicyMiddleware.__init__) that .audit_log is a "
                "genuine public instance attribute, not a defensive "
                f"fallback — missing {required_empirical_symbol!r}",
            )
        for forbidden_defensive_symbol in (
            'getattr(policy_middleware, "audit_log"',
            'hasattr(policy_middleware, "audit_log")',
        ):
            self.assertNotIn(
                forbidden_defensive_symbol,
                v4_audit_helper_source,
                "assert_v4_audit_attribution must not defensively guard "
                f"the audit_log attribute access with {forbidden_defensive_symbol!r} "
                "— it is a confirmed-public, always-present attribute on "
                "the real installed 4.1.0 class, so a direct read is the "
                "correct, non-defensive form",
            )

        # The v4 audit helper must claim only the observable contract
        # (event source equals requested agent name) and must NOT assert
        # differential knowledge of which internal field upstream reads.
        # Since agent_id equals name in all four constructions, the probe
        # cannot discriminate between _agent_id and context.agent.name as
        # the source of the CloudEvent — overclaiming that breaks the
        # "narrow to observable" rule.
        for forbidden_differential_claim in (
            "never from GovernancePolicyMiddleware._agent_id",
            "comes from context.agent.name, never",
        ):
            self.assertNotIn(
                forbidden_differential_claim,
                local_probe,
                f"contract_probe.py must not claim {forbidden_differential_claim!r} — "
                "the observable is only that event source equals the requested "
                "agent name; agent_id==name in all four constructions, so the "
                "probe cannot discriminate which equal internal field upstream reads",
            )
        self.assertIn(
            "requested agent name",
            v4_audit_helper_source,
            "assert_v4_audit_attribution's docstring must state the observable "
            "contract in terms of 'requested agent name', not internal mechanism",
        )

        # The new helper must be invoked on all four snippet constructions
        # too, each with its OWN dedicated AuditLog wired all the way
        # through build_governed_agent(..., audit_log=<dedicated>) — not a
        # shared log, and not just source-text listing the helper without
        # actually threading a real per-construction AuditLog into the
        # snippet.
        v4_audit_call_indices = []
        for expected_name, audit_log_var in (
            ("compat-probe", "compat_audit_log"),
            ("default-no-guard-probe", "no_guard_audit_log"),
            ("default-semantics-probe", "default_audit_log"),
            ("empty-allowlist-probe", "empty_allowlist_audit_log"),
        ):
            construction_match = re.search(
                re.escape(f'name="{expected_name}"') + r".*?\n    \)",
                local_probe,
                re.DOTALL,
            )
            self.assertIsNotNone(
                construction_match,
                f"could not find the build_governed_agent(...) call for "
                f"{expected_name!r}",
            )
            self.assertIn(
                f"audit_log={audit_log_var}",
                construction_match.group(0),
                f"the {expected_name!r} construction must pass its own "
                f"dedicated audit_log={audit_log_var} through to "
                "build_governed_agent so the real v4 audit-attribution "
                "proof can isolate its own newly emitted CloudEvent(s)",
            )

            call_match = re.search(
                r"assert_v4_audit_attribution\(ns,\s*\w+,\s*"
                + re.escape(audit_log_var)
                + r",\s*"
                + re.escape(f'"{expected_name}"')
                + r"\)",
                local_probe,
            )
            self.assertIsNotNone(
                call_match,
                "assert_v4_audit_attribution must be called with the "
                f"dedicated {audit_log_var!r} AND the exact literal "
                f"expected_name {expected_name!r} — not derived from "
                "agent.name or any other indirection",
            )
            v4_audit_call_indices.append(call_match.start())

        self.assertEqual(
            v4_audit_call_indices,
            sorted(v4_audit_call_indices),
            "the four v4 audit-attribution assertions must run in the "
            "same order as the four build_governed_agent constructions",
        )
        self.assertLess(
            max(v4_audit_call_indices),
            local_probe.index('print("SNIPPET_V4_AUDIT_REQUESTED_NAME=PASS")'),
            "SNIPPET_V4_AUDIT_REQUESTED_NAME=PASS must only print after all "
            "four real v4 audit-attribution assertions have run",
        )
        # Genuine executable proof of the real v4 audit-attribution helper
        # too — dynamically loaded from the real file, driven against stub
        # GovernancePolicyMiddleware/AuditLog instances that mirror the
        # real _process_v4 audit-logging behaviour this proof depends on
        # (append one CloudEvent-shaped dict per allowed message, call
        # call_next once). The helper takes an explicit expected_name
        # literal and asserts it against BOTH the returned Agent's own
        # .name attribute and the emitted CloudEvent's source
        # INDEPENDENTLY of each other — never by comparing the CloudEvent
        # source to agent.name itself.
        assert_v4_audit = foundry_agt_contract_probe.assert_v4_audit_attribution
        v4_stub_ns = _stub_v4_ns()

        # Passing case: both the Agent's own .name attribute and the
        # CloudEvent this construction's own dedicated AuditLog receives
        # are really attributed to the requested expected_name.
        passing_audit_log = _StubAuditLog()
        passing_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(passing_audit_log, emitted_source="v4-audit-probe")
        )
        passing_agent.name = "v4-audit-probe"
        asyncio.run(
            assert_v4_audit(v4_stub_ns, passing_agent, passing_audit_log, "v4-audit-probe")
        )

        # The literal real-world defect this proof exists to catch: the
        # dedicated AuditLog was never threaded through to this
        # construction's own GovernancePolicyMiddleware (build_governed_
        # agent wasn't called with audit_log=<this dedicated AuditLog>).
        unwired_audit_log = _StubAuditLog()
        different_bound_log = _StubAuditLog()
        unwired_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(different_bound_log, emitted_source="unwired-probe")
        )
        unwired_agent.name = "unwired-probe"
        with self.assertRaises(AssertionError) as unwired_ctx:
            asyncio.run(
                assert_v4_audit(v4_stub_ns, unwired_agent, unwired_audit_log, "unwired-probe")
            )
        self.assertIn("dedicated AuditLog", str(unwired_ctx.exception))

        # Emitted-SOURCE drift, INDEPENDENT of agent-name drift: the
        # returned Agent's own .name attribute genuinely equals the
        # requested expected_name, but the CloudEvent 'source' this
        # construction's GovernancePolicyMiddleware emitted attributes the
        # decision to something else entirely (e.g. a constructor keyword
        # default). This must fail even though agent.name itself is
        # perfectly correct — proving the source check is real and not
        # short-circuited by a passing name check.
        source_drift_audit_log = _StubAuditLog()
        source_drift_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(source_drift_audit_log, emitted_source="maf-agent")
        )
        source_drift_agent.name = "mismatch-probe"
        with self.assertRaises(AssertionError) as source_drift_ctx:
            asyncio.run(
                assert_v4_audit(
                    v4_stub_ns, source_drift_agent, source_drift_audit_log, "mismatch-probe"
                )
            )
        source_drift_message = str(source_drift_ctx.exception)
        self.assertIn("maf-agent", source_drift_message)
        self.assertIn("mismatch-probe", source_drift_message)
        self.assertNotIn(
            "never from GovernancePolicyMiddleware._agent_id",
            source_drift_message,
            "assert_v4_audit_attribution failure message must not make a "
            "differential claim about the internal source field",
        )

        # Returned-AGENT-NAME drift, INDEPENDENT of source drift: the
        # emitted CloudEvent 'source' faithfully matches the (already
        # drifted) Agent.name — so a self-referential
        # `event["source"] != agent.name` compare would see them "agree"
        # and never notice anything wrong — but the Agent's own .name
        # attribute has drifted away from the literal expected_name the
        # caller actually requested from build_governed_agent. The helper
        # must catch this by comparing agent.name against the
        # caller-supplied expected_name directly, never against the
        # (possibly also-wrong) emitted source.
        name_drift_audit_log = _StubAuditLog()
        name_drift_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(name_drift_audit_log, emitted_source="drifted-probe")
        )
        name_drift_agent.name = "drifted-probe"
        with self.assertRaises(AssertionError) as name_drift_ctx:
            asyncio.run(
                assert_v4_audit(
                    v4_stub_ns, name_drift_agent, name_drift_audit_log, "requested-probe"
                )
            )
        name_drift_message = str(name_drift_ctx.exception)
        self.assertIn("drifted-probe", name_drift_message)
        self.assertIn("requested-probe", name_drift_message)

        # Exactly-one requirement, same as the identity helper: zero
        # GovernancePolicyMiddleware present.
        zero_mw_agent = _stub_agent()
        zero_mw_agent.name = "zero-mw-probe"
        with self.assertRaises(AssertionError):
            asyncio.run(
                assert_v4_audit(v4_stub_ns, zero_mw_agent, _StubAuditLog(), "zero-mw-probe")
            )

        # Exactly-one requirement: more than one GovernancePolicyMiddleware
        # present must also fail.
        shared_log = _StubAuditLog()
        two_middleware_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(shared_log, emitted_source="dup-probe"),
            _StubV4GovernancePolicyMiddleware(shared_log, emitted_source="dup-probe"),
        )
        two_middleware_agent.name = "dup-probe"
        with self.assertRaises(AssertionError):
            asyncio.run(
                assert_v4_audit(v4_stub_ns, two_middleware_agent, shared_log, "dup-probe")
            )

        # call_next must be called exactly once for a benign message.
        no_call_next_log = _StubAuditLog()
        no_call_next_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(
                no_call_next_log, emitted_source="no-call-next-probe", call_next_calls=0
            )
        )
        no_call_next_agent.name = "no-call-next-probe"
        with self.assertRaises(AssertionError) as no_call_next_ctx:
            asyncio.run(
                assert_v4_audit(
                    v4_stub_ns, no_call_next_agent, no_call_next_log, "no-call-next-probe"
                )
            )
        self.assertIn("call_next", str(no_call_next_ctx.exception))

        # Exactly one newly emitted CloudEvent is required — zero or two
        # must both fail, not just be silently accepted.
        zero_events_log = _StubAuditLog()
        zero_events_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(
                zero_events_log, emitted_source="zero-events-probe", emit_count=0
            )
        )
        zero_events_agent.name = "zero-events-probe"
        with self.assertRaises(AssertionError):
            asyncio.run(
                assert_v4_audit(
                    v4_stub_ns, zero_events_agent, zero_events_log, "zero-events-probe"
                )
            )

        two_events_log = _StubAuditLog()
        two_events_agent = _stub_agent(
            _StubV4GovernancePolicyMiddleware(
                two_events_log, emitted_source="two-events-probe", emit_count=2
            )
        )
        two_events_agent.name = "two-events-probe"
        with self.assertRaises(AssertionError):
            asyncio.run(
                assert_v4_audit(v4_stub_ns, two_events_agent, two_events_log, "two-events-probe")
            )

        for expected_substring in (
            "FoundryChatClient",
            "DefaultAzureCredential",
            "https://ai.azure.com/.default",
            "LIVE_RESPONSE_NONEMPTY=1",
            "LIVE_RESPONSE_ID_PRESENT=1",
            "ALLOWED_TOOL_EXECUTIONS=1",
            "DENIED_TOOL_EXECUTIONS=0",
            "CAPABILITY_DENY_OBSERVED=1",
            "T3_PROBE=PASS",
        ):
            self.assertIn(expected_substring, live_probe)

        self.assertNotIn('agent.run("DROP TABLE users")', live_probe)

        for expected_substring in (
            "allowed_tools=allowed_tools",
            "denied_tools=denied_tools",
        ):
            self.assertIn(expected_substring, snippet)
        for forbidden_substring in (
            "allowed_tools or []",
            "denied_tools or []",
        ):
            self.assertNotIn(forbidden_substring, snippet)

        # The snippet's in-place replacement construction (the one bound
        # to OUR evaluator instance, inside the stack list comprehension)
        # must not pass agent_id=name to GovernancePolicyMiddleware: the
        # real v4 audit path this snippet actually exercises derives the
        # audited agent_did from context.agent.name at process-time, and
        # never reads the constructor's agent_id/._agent_id keyword (that
        # keyword is only read by the kernel=-driven _process_v5 path,
        # which this snippet never takes). This is scoped to the
        # replacement construction only — it must not touch the
        # unrelated, in-scope create_governance_middleware(..., agent_id=
        # name) factory call earlier in the snippet.
        replacement_construction_match = re.search(
            r"GovernancePolicyMiddleware\(evaluator=evaluator,\s*audit_log=audit_log[^)]*\)",
            snippet,
        )
        self.assertIsNotNone(
            replacement_construction_match,
            "maf-middleware-snippet.py must construct a replacement "
            "GovernancePolicyMiddleware(evaluator=evaluator, "
            "audit_log=audit_log) inside the stack list comprehension",
        )
        self.assertNotIn(
            "agent_id=name",
            replacement_construction_match.group(0),
            "the snippet's replacement GovernancePolicyMiddleware(...) "
            "construction must not pass agent_id=name — the real v4 "
            "audit path derives agent_did from context.agent.name at "
            "process-time, not from this constructor's "
            "agent_id/._agent_id keyword, so passing it here is inert",
        )

        # The snippet's docstring must not claim an unconditional
        # three-middleware stack — CapabilityGuardMiddleware is only added
        # by the factory when allowed_tools or denied_tools is not None,
        # so the default (both None) is a two-middleware stack. Assertions
        # are wording-robust but truth-specific: they anchor on the
        # deciding parameter names and the "only when" conditionality, not
        # exact prose.
        self.assertNotIn(
            "Returns a ready-to-run Agent with the three-middleware stack assembled",
            snippet,
        )
        conditional_guard_in_snippet = re.compile(
            r"capabilityguard.{0,300}only when.{0,200}"
            r"(allowed_tools|denied_tools)",
            re.IGNORECASE | re.DOTALL,
        )
        self.assertRegex(
            snippet,
            conditional_guard_in_snippet,
            "snippet docstring must describe the capability guard as "
            "conditional, not an unconditional three-middleware stack",
        )
        self.assertRegex(
            snippet,
            re.compile(r"two.{0,40}middleware", re.IGNORECASE),
            "snippet docstring must describe the always-on two-middleware "
            "baseline (AuditTrail + GovernancePolicy)",
        )

    def test_unsupported_sidecar_is_removed(self) -> None:
        sidecar_path = SKILL / "references" / "aca-sidecar-snippet.bicep"
        self.assertFalse(sidecar_path.exists())

        hitl_gate_path = SKILL / "references" / "policies" / "hitl-gate.yaml"
        self.assertFalse(hitl_gate_path.exists())

    def test_fixture_is_live_and_marker_safe(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )

        for expected_substring in (
            "FOUNDRY_PROJECT_ENDPOINT",
            "FOUNDRY_MODEL_DEPLOYMENT",
            "references/python/contract_probe.py",
            "references/python/live_t3_probe.py",
            "/tmp/foundry-agt-smoke-evidence",
            "_MOKE_RESULT=PASS",
            "SKILL_CONTRACT=OK",
            "sed -n",
            r'"agent-governance-toolkit\[full\]~=4\.1\.0"',
        ):
            self.assertIn(expected_substring, fixture)

        self.assertNotIn("SMOKE_RESULT=PASS", fixture)
        lowered = fixture.lower()
        self.assertNotIn("no dataplane calls", lowered)
        self.assertNotIn("no model deployments", lowered)

    def test_workflow_uploads_marker_artifact(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "skill-test.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("/tmp/${{ matrix.skill }}-smoke-result", workflow)

    def test_dependency_graph_has_one_key(self) -> None:
        deps = (ROOT / ".github" / "skill-deps.yml").read_text(encoding="utf-8")
        matches = re.findall(r"^  foundry-agt:\s*$", deps, flags=re.MULTILINE)
        self.assertEqual(len(matches), 1)

    def test_readme_drops_removed_contract_and_overclaim(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_line = next(
            (line for line in readme.splitlines() if "[**foundry-agt**]" in line),
            None,
        )
        self.assertIsNotNone(readme_line, "foundry-agt README line not found")

        for forbidden in (
            "v3.6.0",
            "Path B",
            "Path C",
            "26.67%",
            "5 field-tested Known Issues",
            "HITL-gate",
        ):
            self.assertNotIn(forbidden, readme_line)

    def test_ssn_policy_exact_yaml_bytes(self) -> None:
        policy = (
            SKILL / "references" / "policies" / "pii-deny.yaml"
        ).read_text(encoding="utf-8")

        expected = r"value: '\b\d{3}[\s.-]?\d{2}[\s.-]?\d{4}\b'"
        self.assertEqual(policy.count(expected), 1)
        self.assertNotIn("field: response", policy)

        # The approved regex's `[\s.-]?` separators are each optional, so
        # the rule also matches the fully unseparated digit run. That form
        # is indistinguishable from any other standalone 9-digit number
        # (order/invoice IDs). An ordinary hyphenated ZIP+4 also matches
        # because the first separator is optional and the second accepts its
        # hyphen. This is a false-positive/false-deny class the
        # policy file must disclose immediately, not a hypothetical.
        false_positive_pattern = re.compile(
            r"unseparated.{0,400}"
            r"(standalone|any).{0,80}9-digit.{0,250}"
            r"zip\+4",
            re.DOTALL,
        )
        ordinary_zip_pattern = re.compile(
            r"(ordinary|normal|conventional).{0,80}hyphenated.{0,80}zip\+4"
            r".{0,180}(first separator|optional)",
            re.DOTALL,
        )
        policy_lower = policy.lower()
        self.assertRegex(
            policy_lower,
            false_positive_pattern,
            "pii-deny.yaml must disclose that the unseparated SSN form "
            "false-positives/false-denies on any standalone 9-digit "
            "number and on ZIP+4 codes",
        )
        self.assertRegex(policy_lower, ordinary_zip_pattern)
        self.assertRegex(
            policy_lower,
            re.compile(
                r"tune.{0,60}(or|/).{0,60}remove.{0,120}before production",
                re.DOTALL,
            ),
            "pii-deny.yaml must instruct tuning or removing block-us-ssn "
            "before production",
        )
        self.assertRegex(
            policy_lower,
            re.compile(r"(real )?classifier.{0,80}content safety", re.DOTALL),
            "pii-deny.yaml must instruct pairing with a real classifier / "
            "Content Safety",
        )

        # The same disclosure must reach a consumer who only ever reads
        # SKILL.md's active (pre-changelog) policy guidance and never
        # opens the YAML directly.
        _, skill_body = frontmatter(SKILL / "SKILL.md")
        changelog_index = skill_body.find("## GBB Changelog")
        self.assertNotEqual(changelog_index, -1, "GBB Changelog heading not found")
        active_skill_body = skill_body[:changelog_index].lower()

        self.assertRegex(
            active_skill_body,
            false_positive_pattern,
            "SKILL.md's active policy guidance must disclose that the "
            "unseparated SSN form false-positives/false-denies on any "
            "standalone 9-digit number and on ZIP+4 codes",
        )
        self.assertRegex(active_skill_body, ordinary_zip_pattern)
        self.assertRegex(
            active_skill_body,
            re.compile(
                r"tune.{0,60}(or|/).{0,60}drop.{0,120}before production",
                re.DOTALL,
            ),
            "SKILL.md must instruct consumers to tune or drop the SSN "
            "rule before production",
        )
        self.assertRegex(
            active_skill_body,
            re.compile(r"(real )?classifier.{0,80}content safety", re.DOTALL),
            "SKILL.md must instruct pairing with a real classifier / "
            "Content Safety",
        )
        self.assertRegex(
            active_skill_body,
            re.compile(
                r"pii-deny\.yaml.{0,200}default.{0,60}director"
                r"|default.{0,60}director.{0,200}pii-deny\.yaml",
                re.DOTALL,
            ),
            "SKILL.md must explain that loading the default policy "
            "directory includes pii-deny.yaml's SSN rule",
        )
        self.assertRegex(
            active_skill_body,
            re.compile(r"deny.{0,120}terminat.{0,80}message", re.DOTALL),
            "SKILL.md must explain that a policy deny terminates the "
            "message path",
        )


if __name__ == "__main__":
    unittest.main()
