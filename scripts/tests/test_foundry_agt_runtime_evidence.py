"""Contract tests for the foundry-agt runtime evidence producer.

Source of truth for the prose example in `../../SKILL.md § CI gating (`threadlight-safe-check` integration)`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from runtime_evidence import REQUIRED_FIELDS, SCHEMA, build_evidence, write_evidence  # noqa: E402

REF_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references"
SCHEMA_PATH = REF_DIR / "runtime-evidence.schema.json"
DATA_DIR = REF_DIR / "data"
VALID_FIXTURE_PATH = DATA_DIR / "runtime-evidence.valid.json"
INVALID_FIXTURE_PATH = DATA_DIR / "runtime-evidence.invalid.json"

try:  # pragma: no cover - optional dependency
    from jsonschema import Draft7Validator  # type: ignore
    from jsonschema.exceptions import ValidationError  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Draft7Validator = None
    ValidationError = None


def _event(*, session_id: str, decision: str, **extra: object) -> dict[str, object]:
    event: dict[str, object] = {
        "event_id": extra.pop("event_id", "evt-001"),
        "timestamp": extra.pop("timestamp", "2026-07-15T12:00:00Z"),
        "event_type": extra.pop("event_type", "tool_call"),
        "agent_id": extra.pop("agent_id", "agent-001"),
        "session_id": session_id,
        "policy_name": extra.pop("policy_name", "default"),
        "tool_name": extra.pop("tool_name", "demo_tool"),
        "decision": decision,
        "reason": extra.pop("reason", "ok"),
        "evaluation_ms": extra.pop("evaluation_ms", 3),
    }
    event.update(extra)
    return event


def _sample_inputs(*, empty_session: bool = False) -> tuple[list[dict[str, object]], str, str, bool]:
    events = [
        _event(session_id="session-001", decision="ALLOW", event_id="evt-001"),
        _event(
            session_id="" if empty_session else "session-002",
            decision="deny",
            event_id="evt-002",
            tool_name="delete_tool",
            reason="blocked",
        ),
    ]
    redaction_policy = "policies/redaction.md"
    retention_policy = "policies/retention.md"
    integrity_verified = True
    trace_correlated = not empty_session
    return events, redaction_policy, retention_policy, trace_correlated


def _assert_schema_contract(schema: dict[str, object]) -> None:
    def _resolve_local_ref(node: object) -> dict[str, object]:
        if not isinstance(node, dict):
            raise AssertionError(f"expected schema node to be a mapping, got {type(node).__name__}")
        ref = node.get("$ref")
        if ref is None:
            return node
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise AssertionError(f"unsupported schema ref: {ref!r}")
        target: object = schema
        for part in ref[2:].split("/"):
            if not isinstance(target, dict) or part not in target:
                raise AssertionError(f"unresolvable schema ref: {ref!r}")
            target = target[part]
        if not isinstance(target, dict):
            raise AssertionError(f"schema ref did not resolve to a mapping: {ref!r}")
        return target

    def _assert_string_schema(node: object, *, enum: list[object] | None = None, min_length: int | None = None) -> None:
        resolved = _resolve_local_ref(node)
        assert resolved["type"] == "string"
        if enum is not None:
            assert resolved["enum"] == enum
        if min_length is not None:
            assert resolved["minLength"] == min_length

    def _assert_boolean_schema(node: object, *, enum: list[object] | None = None) -> None:
        resolved = _resolve_local_ref(node)
        assert resolved["type"] == "boolean"
        if enum is not None:
            assert resolved["enum"] == enum

    def _assert_object_schema(
        node: object,
        *,
        required: tuple[str, ...] = (),
        property_checks: dict[str, Callable[[object], None]] | None = None,
    ) -> None:
        resolved = _resolve_local_ref(node)
        assert resolved["type"] == "object"
        if "required" in resolved:
            for field in required:
                assert field in resolved["required"]
        if resolved.get("additionalProperties") is not True:
            raise AssertionError("expected object schema to allow additional properties")
        properties = resolved.get("properties", {})
        if property_checks:
            for name, check in property_checks.items():
                check(properties[name])

    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    required = schema["required"]
    for field in [
        "schema",
        "captured_at",
        "policy_version",
        "events_observed",
        "required_fields_observed",
        "audit_sink",
        "telemetry_sink",
        "redaction_policy",
        "retention_policy",
        "integrity_verified",
    ]:
        assert field in required
    props = schema["properties"]
    assert props["schema"]["enum"] == [SCHEMA]
    eo = props["events_observed"]
    assert eo["type"] == "object"
    assert "allow" in eo["required"]
    assert "deny" in eo["required"]
    assert eo["properties"]["allow"]["minimum"] == 1
    assert eo["properties"]["deny"]["minimum"] == 1
    assert props["required_fields_observed"]["minItems"] == len(REQUIRED_FIELDS)
    assert props["required_fields_observed"]["maxItems"] == len(REQUIRED_FIELDS)
    _assert_object_schema(
        props["audit_sink"],
        required=("kind", "persistent"),
        property_checks={
            "kind": lambda node: _assert_string_schema(node, enum=["append-only"]),
            "persistent": lambda node: _assert_boolean_schema(node, enum=[True]),
        },
    )
    _assert_object_schema(
        props["telemetry_sink"],
        required=("kind", "trace_correlated"),
        property_checks={
            "kind": lambda node: _assert_string_schema(node, enum=["application-insights"]),
            "trace_correlated": lambda node: _assert_boolean_schema(node),
        },
    )
    _assert_string_schema(props["redaction_policy"], min_length=1)
    _assert_string_schema(props["retention_policy"], min_length=1)


class TestRuntimeEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self.redaction_policy = "policies/redaction.md"
        self.retention_policy = "policies/retention.md"

    def test_build_evidence_valid_allow_deny_output(self) -> None:
        events, redaction_policy, retention_policy, trace_correlated = _sample_inputs()

        evidence = build_evidence(
            events,
            policy_version="2026.07",
            redaction_policy=redaction_policy,
            retention_policy=retention_policy,
            integrity_verified=True,
            captured_at="2026-07-15T12:34:56Z",
        )

        self.assertEqual(evidence["schema"], SCHEMA)
        self.assertEqual(evidence["captured_at"], "2026-07-15T12:34:56Z")
        self.assertEqual(evidence["policy_version"], "2026.07")
        self.assertEqual(evidence["events_observed"], {"allow": 1, "deny": 1})
        self.assertNotIn("allow_count", evidence)
        self.assertNotIn("deny_count", evidence)
        self.assertEqual(evidence["required_fields_observed"], sorted(REQUIRED_FIELDS))
        self.assertEqual(evidence["audit_sink"], {"kind": "append-only", "persistent": True})
        self.assertEqual(
            evidence["telemetry_sink"],
            {"kind": "application-insights", "trace_correlated": trace_correlated},
        )
        self.assertEqual(evidence["redaction_policy"], redaction_policy)
        self.assertEqual(evidence["retention_policy"], retention_policy)
        self.assertTrue(evidence["integrity_verified"])

    def test_build_evidence_never_leaks_payload_values(self) -> None:
        leak = "LEAK-ME-914d9f1d"
        events = [
            _event(
                session_id="session-001",
                decision="allow",
                event_id="evt-001",
                prompt=leak,
                response=leak,
                arguments={"secret": leak},
                message=leak,
            ),
            _event(
                session_id="session-002",
                decision="deny",
                event_id="evt-002",
                reason="blocked",
                tool_arguments=leak,
                credentials=leak,
            ),
        ]

        evidence = build_evidence(
            events,
            policy_version="2026.07",
            redaction_policy=self.redaction_policy,
            retention_policy=self.retention_policy,
            integrity_verified=False,
            captured_at="2026-07-15T12:34:56Z",
        )
        payload = json.dumps(evidence, sort_keys=True)
        self.assertNotIn(leak, payload)

    def test_build_evidence_missing_required_field_raises(self) -> None:
        events = [
            {
                "event_id": "evt-001",
                "timestamp": "2026-07-15T12:00:00Z",
                "event_type": "tool_call",
                "agent_id": "agent-001",
                "session_id": "session-001",
                "policy_name": "default",
                "tool_name": "demo_tool",
                "decision": "allow",
                "evaluation_ms": 3,
            }
        ]

        with self.assertRaises(ValueError) as ctx:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy=self.redaction_policy,
                retention_policy=self.retention_policy,
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("event[0]", str(ctx.exception))
        self.assertIn("reason", str(ctx.exception))

    def test_build_evidence_requires_allow_and_deny(self) -> None:
        events = [
            _event(session_id="session-001", decision="ALLOW", event_id="evt-001"),
            _event(session_id="session-002", decision="allow", event_id="evt-002"),
        ]

        with self.assertRaises(ValueError) as ctx:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy=self.redaction_policy,
                retention_policy=self.retention_policy,
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        message = str(ctx.exception).lower()
        self.assertIn("allow", message)
        self.assertIn("deny", message)

    def test_build_evidence_false_trace_correlation_for_empty_session(self) -> None:
        events, redaction_policy, retention_policy, trace_correlated = _sample_inputs(empty_session=True)
        evidence = build_evidence(
            events,
            policy_version="2026.07",
            redaction_policy=redaction_policy,
            retention_policy=retention_policy,
            integrity_verified=True,
            captured_at="2026-07-15T12:34:56Z",
        )
        self.assertFalse(trace_correlated)
        self.assertFalse(evidence["telemetry_sink"]["trace_correlated"])

    def test_write_evidence_is_deterministic(self) -> None:
        events, redaction_policy, retention_policy, _ = _sample_inputs()
        evidence = build_evidence(
            events,
            policy_version="2026.07",
            redaction_policy=redaction_policy,
            retention_policy=retention_policy,
            integrity_verified=True,
            captured_at="2026-07-15T12:34:56Z",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "runtime-evidence.json"
            write_evidence(path, evidence)
            first = path.read_text(encoding="utf-8")
            self.assertTrue(first.endswith("\n"))
            self.assertEqual(first, json.dumps(evidence, indent=2, sort_keys=True) + "\n")

            write_evidence(path, evidence)
            second = path.read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_contract_fixtures(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        valid_fixture = json.loads(VALID_FIXTURE_PATH.read_text(encoding="utf-8"))
        invalid_fixture = json.loads(INVALID_FIXTURE_PATH.read_text(encoding="utf-8"))

        events, redaction_policy, retention_policy, _ = _sample_inputs()
        expected = build_evidence(
            events,
            policy_version="2026.07",
            redaction_policy=redaction_policy,
            retention_policy=retention_policy,
            integrity_verified=True,
            captured_at="2026-07-15T12:34:56Z",
        )
        self.assertEqual(valid_fixture, expected)

        if Draft7Validator is not None:
            Draft7Validator(schema).validate(valid_fixture)
            with self.assertRaises(ValidationError):
                Draft7Validator(schema).validate(invalid_fixture)
        else:
            self.assertEqual(invalid_fixture["schema"], "foundry-agt-runtime-evidence/v0")
            self.assertNotIn("telemetry_sink", invalid_fixture)

        # Always exercise the stdlib fallback so local runs cover the CI path.
        _assert_schema_contract(schema)
        self.assertEqual(valid_fixture["schema"], SCHEMA)
        self.assertIn("telemetry_sink", valid_fixture)


SKILL_MD_PATH = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "SKILL.md"
FIXTURE_PATH = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "test-fixture" / "consumer_prompt.md"


class TestSkillFixtureContract(unittest.TestCase):
    """Pin the SKILL.md / fixture output contract so heading renames are caught early."""

    def test_skill_has_runtime_audit_evidence_section(self) -> None:
        """SKILL.md must contain the ## Runtime audit evidence heading."""
        skill_text = SKILL_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("## Runtime audit evidence", skill_text,
                      "SKILL.md is missing '## Runtime audit evidence' section")

    def test_skill_links_schema_and_producer(self) -> None:
        """The Runtime audit evidence section must link both the schema and producer module."""
        skill_text = SKILL_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("runtime-evidence.schema.json", skill_text)
        self.assertIn("runtime_evidence.py", skill_text)

    def test_skill_names_output_artifact(self) -> None:
        """SKILL.md must name specs/agt-runtime-evidence.json as the output artifact."""
        skill_text = SKILL_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("specs/agt-runtime-evidence.json", skill_text,
                      "SKILL.md is missing output artifact 'specs/agt-runtime-evidence.json'")

    def test_skill_links_runtime_audit_export(self) -> None:
        """SKILL.md must link to runtime-audit-export.md."""
        skill_text = SKILL_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("runtime-audit-export.md", skill_text,
                      "SKILL.md is missing link to references/runtime-audit-export.md")

    def test_consumer_prompt_requires_specs_output(self) -> None:
        """test-fixture/consumer_prompt.md must require writing specs/agt-runtime-evidence.json."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("specs/agt-runtime-evidence.json", prompt_text,
                      "consumer_prompt.md does not mention specs/agt-runtime-evidence.json")

    def test_consumer_prompt_requires_allow_and_deny(self) -> None:
        """consumer_prompt.md must check events_observed allow and deny counts in the artifact."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("events_observed", prompt_text)
        self.assertIn('"allow"', prompt_text)
        self.assertIn('"deny"', prompt_text)

    def test_consumer_prompt_requires_integrity_verified(self) -> None:
        """consumer_prompt.md must check integrity_verified in the artifact."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("integrity_verified", prompt_text,
                      "consumer_prompt.md does not check integrity_verified")

    def test_consumer_prompt_checks_schema_field(self) -> None:
        """consumer_prompt.md must verify the schema sentinel value."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("foundry-agt-runtime-evidence/v1", prompt_text,
                      "consumer_prompt.md does not assert schema == 'foundry-agt-runtime-evidence/v1'")

    def test_consumer_prompt_checks_absence_of_sentinels(self) -> None:
        """consumer_prompt.md must check that sensitive sentinel strings are absent."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("DROP TABLE", prompt_text,
                      "consumer_prompt.md missing sentinel check for 'DROP TABLE'")
        self.assertIn("api_key=", prompt_text,
                      "consumer_prompt.md missing sentinel check for 'api_key='")

    def test_consumer_prompt_is_execution_only(self) -> None:
        """The fixture must forbid the authoring behavior that caused CI to skip execution."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        required_prohibitions = (
            "This is an EXECUTION-ONLY smoke",
            "Do NOT edit any file",
            "Do NOT invoke `apply_patch`",
            "Do NOT inspect repository files",
            "Do NOT run tests",
            "Do NOT rebuild docs",
            "Do NOT run any `git` command",
            "Do NOT finish with a prose-only response",
        )
        for prohibition in required_prohibitions:
            with self.subTest(prohibition=prohibition):
                self.assertIn(prohibition, prompt_text)

    def test_consumer_prompt_pins_executable_runtime_evidence_block(self) -> None:
        """The exact producer invocation in the fixture must execute against safe events."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'export AGT_SAFE_EVENTS_PATH="/tmp/foundry-agt-safe-events.json"',
            prompt_text,
        )
        self.assertIn(
            'export AGT_EVIDENCE_PATH="specs/agt-runtime-evidence.json"',
            prompt_text,
        )
        self.assertIn(
            'export AGT_INTEGRITY_PATH="/tmp/foundry-agt-integrity-ok"',
            prompt_text,
        )
        self.assertIn(
            "from runtime_evidence import build_evidence, write_evidence",
            prompt_text,
        )
        self.assertIn(
            'write_evidence(os.environ["AGT_EVIDENCE_PATH"], evidence)',
            prompt_text,
        )

        match = re.search(
            r"python3 - <<'PY'\n"
            r"# RUNTIME_EVIDENCE_PRODUCER_SMOKE\n"
            r"(?P<code>.*?)\nPY",
            prompt_text,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "fixture is missing the exact runtime-evidence Python block")
        code = match.group("code") if match else ""

        events = [
            _event(session_id="session-allow", decision="allow", event_id="evt-allow"),
            _event(
                session_id="session-deny",
                decision="deny",
                event_id="evt-deny",
                reason="blocked",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            safe_events = Path(tmp) / "safe-events.json"
            integrity_path = Path(tmp) / "integrity-ok"
            evidence_path = Path(tmp) / "agt-runtime-evidence.json"
            safe_events.write_text(json.dumps(events), encoding="utf-8")
            integrity_path.write_text("true\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "AGT_SAFE_EVENTS_PATH": str(safe_events),
                    "AGT_INTEGRITY_PATH": str(integrity_path),
                    "AGT_EVIDENCE_PATH": str(evidence_path),
                    "GITHUB_WORKSPACE": str(SKILL_MD_PATH.parents[2]),
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                cwd=SKILL_MD_PATH.parents[2],
                env=env,
                text=True,
                timeout=15,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["schema"], SCHEMA)
            self.assertEqual(evidence["events_observed"], {"allow": 1, "deny": 1})
            self.assertTrue(evidence["integrity_verified"])

    def test_consumer_prompt_uses_marker_as_only_success_source(self) -> None:
        """CI success must come only from the byte-exact marker file write."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        success_write = "printf 'SMOKE_RESULT=PASS\\n' > /tmp/foundry-agt-smoke-result"
        failure_write = (
            "printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' "
            "> /tmp/foundry-agt-smoke-result"
        )
        self.assertEqual(prompt_text.count(success_write), 1)
        self.assertEqual(prompt_text.count(failure_write), 1)
        self.assertEqual(prompt_text.count("SMOKE_RESULT=PASS"), 1)
        self.assertIn("The marker file is the only success source", prompt_text)
        self.assertIn("failure-marker Bash write in Step 4", prompt_text)
        self.assertNotIn("PASS via transcript", prompt_text)

    def test_fixture_asset_change_bumps_patch_version(self) -> None:
        """Changing the consumer fixture must advance the skill's patch version."""
        frontmatter = "\n".join(SKILL_MD_PATH.read_text(encoding="utf-8").splitlines()[:25])
        self.assertIn('version: "1.4.1"', frontmatter)

    def test_producer_module_references_new_skill_heading(self) -> None:
        """runtime_evidence.py docstring must reference the Runtime audit evidence heading."""
        producer_path = REF_DIR / "python" / "runtime_evidence.py"
        head = producer_path.read_text(encoding="utf-8").splitlines()[:10]
        joined = "\n".join(head)
        self.assertIn("Runtime audit evidence", joined,
                      "runtime_evidence.py docstring does not reference '§ Runtime audit evidence'")


RUNBOOK_PATH = REF_DIR / "runtime-audit-export.md"


class TestRunbookStringPathContract(unittest.TestCase):
    """CI-discovered contract: build_evidence() must receive string paths, not dicts.

    These tests catch regressions where the runbook or a consumer passes a dict
    for redaction_policy or retention_policy instead of a repo-relative path string.
    """

    # ── runtime_evidence.py rejects dict-style args ────────────────────────

    def test_build_evidence_rejects_dict_redaction_policy(self) -> None:
        """redaction_policy={...} must raise ValueError immediately."""
        events = [
            _event(session_id="s-001", decision="allow"),
            _event(session_id="s-002", decision="deny"),
        ]
        with self.assertRaises(ValueError) as ctx:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy={  # type: ignore[arg-type]  # deliberate wrong type
                    "mode": "strip-sensitive",
                    "fields": ["prompt", "response", "arguments", "credentials"],
                },
                retention_policy="policies/retention.md",
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("redaction_policy", str(ctx.exception))
        self.assertIn("path", str(ctx.exception).lower())

    def test_build_evidence_rejects_dict_retention_policy(self) -> None:
        """retention_policy={...} must raise ValueError immediately."""
        events = [
            _event(session_id="s-001", decision="allow"),
            _event(session_id="s-002", decision="deny"),
        ]
        with self.assertRaises(ValueError) as ctx:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy="policies/redaction.md",
                retention_policy={  # type: ignore[arg-type]  # deliberate wrong type
                    "mode": "retained",
                    "days": 90,
                    "backpressure": "drop-oldest",
                },
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("retention_policy", str(ctx.exception))
        self.assertIn("path", str(ctx.exception).lower())

    def test_build_evidence_rejects_empty_string_redaction_policy(self) -> None:
        """An empty or whitespace-only redaction_policy string must raise ValueError."""
        events = [
            _event(session_id="s-001", decision="allow"),
            _event(session_id="s-002", decision="deny"),
        ]
        for bad in ("", "   "):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError) as ctx:
                    build_evidence(
                        events,
                        policy_version="2026.07",
                        redaction_policy=bad,
                        retention_policy="policies/retention.md",
                        integrity_verified=True,
                        captured_at="2026-07-15T12:34:56Z",
                    )
                self.assertIn("redaction_policy", str(ctx.exception))

    def test_build_evidence_rejects_empty_string_retention_policy(self) -> None:
        """An empty or whitespace-only retention_policy string must raise ValueError."""
        events = [
            _event(session_id="s-001", decision="allow"),
            _event(session_id="s-002", decision="deny"),
        ]
        for bad in ("", "   "):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError) as ctx:
                    build_evidence(
                        events,
                        policy_version="2026.07",
                        redaction_policy="policies/redaction.md",
                        retention_policy=bad,
                        integrity_verified=True,
                        captured_at="2026-07-15T12:34:56Z",
                    )
                self.assertIn("retention_policy", str(ctx.exception))

    def test_build_evidence_accepts_string_paths(self) -> None:
        """Confirm that well-formed string paths are accepted without error."""
        events = [
            _event(session_id="s-001", decision="allow"),
            _event(session_id="s-002", decision="deny"),
        ]
        evidence = build_evidence(
            events,
            policy_version="2026.07",
            redaction_policy="skills/foundry-agt/references/policies/redaction.md",
            retention_policy="skills/foundry-agt/references/policies/retention.md",
            integrity_verified=True,
            captured_at="2026-07-15T12:34:56Z",
        )
        self.assertIsInstance(evidence["redaction_policy"], str)
        self.assertIsInstance(evidence["retention_policy"], str)

    # ── runbook text must not contain the stale dict-style patterns ────────

    def test_runbook_step5_no_dict_redaction_policy(self) -> None:
        """runtime-audit-export.md must not contain `redaction_policy={`."""
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "redaction_policy={",
            runbook,
            "runtime-audit-export.md still passes a dict for redaction_policy — "
            "use a repo-relative path string instead.",
        )

    def test_runbook_step5_no_dict_retention_policy(self) -> None:
        """runtime-audit-export.md must not contain `retention_policy={`."""
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "retention_policy={",
            runbook,
            "runtime-audit-export.md still passes a dict for retention_policy — "
            "use a repo-relative path string instead.",
        )

    def test_runbook_step5_redaction_policy_is_string_assignment(self) -> None:
        """runtime-audit-export.md Step 5 must pass redaction_policy as a string literal."""
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'redaction_policy="',
            runbook,
            "runtime-audit-export.md Step 5 does not assign redaction_policy a string literal.",
        )

    def test_runbook_step5_retention_policy_is_string_assignment(self) -> None:
        """runtime-audit-export.md Step 5 must pass retention_policy as a string literal."""
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'retention_policy="',
            runbook,
            "runtime-audit-export.md Step 5 does not assign retention_policy a string literal.",
        )

    def test_runbook_policy_docs_exist(self) -> None:
        """The policy markdown files referenced by the runbook must exist in the repo."""
        policies_dir = REF_DIR / "policies"
        self.assertTrue(
            (policies_dir / "redaction.md").exists(),
            "skills/foundry-agt/references/policies/redaction.md does not exist",
        )
        self.assertTrue(
            (policies_dir / "retention.md").exists(),
            "skills/foundry-agt/references/policies/retention.md does not exist",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
