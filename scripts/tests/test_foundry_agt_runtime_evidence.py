"""Contract tests for the foundry-agt runtime evidence producer.

Source of truth for the prose example in `../../SKILL.md § CI gating (`threadlight-safe-check` integration)`.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
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


def _sample_inputs(*, empty_session: bool = False) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object], bool]:
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
    redaction_policy = {
        "mode": "strip-sensitive",
        "fields": ["prompt", "response", "arguments"],
    }
    retention_policy = {
        "mode": "retained",
        "days": 30,
    }
    integrity_verified = True
    trace_correlated = not empty_session
    return events, redaction_policy, retention_policy, trace_correlated


def _assert_schema_contract(schema: dict[str, object]) -> None:
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    required = schema["required"]
    for field in [
        "schema",
        "captured_at",
        "policy_version",
        "events_observed",
        "allow_count",
        "deny_count",
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
    assert props["allow_count"]["minimum"] == 1
    assert props["deny_count"]["minimum"] == 1
    assert props["required_fields_observed"]["minItems"] == len(REQUIRED_FIELDS)
    assert props["required_fields_observed"]["maxItems"] == len(REQUIRED_FIELDS)
    assert props["audit_sink"]["type"] == "object"
    assert props["telemetry_sink"]["type"] == "object"


class TestRuntimeEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self.redaction_policy = {"mode": "strip-sensitive", "fields": ["prompt", "response", "arguments"]}
        self.retention_policy = {"mode": "retained", "days": 30}

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
        self.assertEqual(evidence["events_observed"], 2)
        self.assertEqual(evidence["allow_count"], 1)
        self.assertEqual(evidence["deny_count"], 1)
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
            return

        _assert_schema_contract(schema)
        self.assertEqual(valid_fixture["schema"], SCHEMA)
        self.assertIn("telemetry_sink", valid_fixture)
        self.assertEqual(invalid_fixture["schema"], "foundry-agt-runtime-evidence/v0")
        self.assertNotIn("telemetry_sink", invalid_fixture)


if __name__ == "__main__":
    unittest.main(verbosity=2)
