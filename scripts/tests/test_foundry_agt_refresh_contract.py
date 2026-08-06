"""Contract tests for the foundry-agt 2.0 manual-hygiene refresh."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-agt"


def frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    _, fm, body = raw.split("---", 2)
    return yaml.safe_load(fm), body


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
        # (order/invoice IDs) and from a ZIP+4 code once its separator is
        # stripped -- both collapse into the same nine contiguous digits
        # the regex accepts. This is a false-positive/false-deny class the
        # policy file must disclose immediately, not a hypothetical.
        false_positive_pattern = re.compile(
            r"unseparated.{0,400}"
            r"(standalone|any).{0,80}9-digit.{0,250}"
            r"zip\+4",
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
