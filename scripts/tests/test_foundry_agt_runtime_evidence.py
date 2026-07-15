"""Contract tests for the foundry-agt runtime evidence producer.

Source of truth for the prose example in `../../SKILL.md § CI gating (`threadlight-safe-check` integration)`.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from runtime_evidence import (  # noqa: E402
    REQUIRED_FIELDS,
    SCHEMA,
    _SAFE_CE_ENVELOPE_FIELDS,
    build_evidence,
    extract_cloudevent_payload,
    write_evidence,
)

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
    redaction_policy = "docs/pii-redaction.md"
    retention_policy = "infra/monitoring.bicep"
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
    # Policy fields must be non-empty strings (repo-relative paths), not inline objects.
    _assert_string_schema(props["redaction_policy"], min_length=1)
    _assert_string_schema(props["retention_policy"], min_length=1)


class TestRuntimeEvidence(unittest.TestCase):
    def setUp(self) -> None:
        self.redaction_policy = "docs/pii-redaction.md"
        self.retention_policy = "infra/monitoring.bicep"

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
        self.assertEqual(evidence["redaction_policy"], "docs/pii-redaction.md")
        self.assertEqual(evidence["retention_policy"], "infra/monitoring.bicep")
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

    def test_build_evidence_rejects_non_string_policy_path(self) -> None:
        events = [
            _event(session_id="session-001", decision="ALLOW", event_id="evt-001"),
            _event(session_id="session-002", decision="deny", event_id="evt-002"),
        ]
        with self.assertRaises(ValueError) as ctx:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy={"mode": "strip-sensitive"},  # type: ignore[arg-type]
                retention_policy=self.retention_policy,
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("redaction_policy", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy=self.redaction_policy,
                retention_policy={"mode": "retained"},  # type: ignore[arg-type]
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("retention_policy", str(ctx2.exception))

    def test_build_evidence_rejects_empty_policy_path(self) -> None:
        events = [
            _event(session_id="session-001", decision="ALLOW", event_id="evt-001"),
            _event(session_id="session-002", decision="deny", event_id="evt-002"),
        ]
        with self.assertRaises(ValueError) as ctx:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy="",
                retention_policy=self.retention_policy,
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("redaction_policy", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            build_evidence(
                events,
                policy_version="2026.07",
                redaction_policy=self.redaction_policy,
                retention_policy="   ",
                integrity_verified=True,
                captured_at="2026-07-15T12:34:56Z",
            )
        self.assertIn("retention_policy", str(ctx2.exception))

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

        # Policy fields in fixtures must be repo-relative path strings.
        self.assertIsInstance(valid_fixture["redaction_policy"], str)
        self.assertTrue(valid_fixture["redaction_policy"])
        self.assertIsInstance(valid_fixture["retention_policy"], str)
        self.assertTrue(valid_fixture["retention_policy"])

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


class TestExtractCloudeventPayload(unittest.TestCase):
    """Contract tests for the extract_cloudevent_payload helper."""

    def _flat(self, **extra: object) -> dict[str, object]:
        base: dict[str, object] = {
            "event_id": "evt-001",
            "timestamp": "2026-07-15T12:00:00Z",
            "event_type": "tool_call",
            "agent_id": "agent-001",
            "session_id": "session-001",
            "policy_name": "default",
            "tool_name": "demo_tool",
            "decision": "allow",
            "reason": "ok",
            "evaluation_ms": 3,
        }
        base.update(extra)
        return base

    def test_flat_mapping_returns_required_fields_only(self) -> None:
        flat = self._flat(sensitive_arg="secret", credentials="Authorization: Bearer test-secret-token")
        result = extract_cloudevent_payload(flat)
        self.assertEqual(set(result.keys()) - _SAFE_CE_ENVELOPE_FIELDS, set(REQUIRED_FIELDS))
        self.assertNotIn("sensitive_arg", result)
        self.assertNotIn("credentials", result)

    def test_flat_mapping_with_subset_of_required_fields(self) -> None:
        flat = {"event_id": "evt-001", "decision": "allow"}
        result = extract_cloudevent_payload(flat)
        self.assertEqual(result, {"event_id": "evt-001", "decision": "allow"})

    def test_enveloped_cloudevent_extracts_from_data(self) -> None:
        payload_data = self._flat()
        cloud_event = {
            "specversion": "1.0",
            "type": "com.agt.audit",
            "source": "urn:agt:session-001",
            "id": "ce-001",
            "time": "2026-07-15T12:00:00Z",
            "datacontenttype": "application/json",
            "data": payload_data,
        }
        result = extract_cloudevent_payload(cloud_event)
        for field in REQUIRED_FIELDS:
            self.assertIn(field, result)
        # Non-payload envelope fields must not bleed through (only safe ones allowed).
        self.assertNotIn("specversion", result)
        self.assertNotIn("datacontenttype", result)

    def test_enveloped_cloudevent_preserves_safe_envelope_fields(self) -> None:
        payload_data = {"decision": "deny", "reason": "blocked"}
        cloud_event = {
            "specversion": "1.0",
            "type": "com.agt.audit",
            "source": "urn:agt:session-001",
            "id": "ce-001",
            "time": "2026-07-15T12:00:00Z",
            "data": payload_data,
        }
        result = extract_cloudevent_payload(cloud_event)
        for key in _SAFE_CE_ENVELOPE_FIELDS:
            if key in cloud_event:
                self.assertIn(key, result)
        self.assertNotIn("specversion", result)

    def test_non_mapping_input_raises_value_error(self) -> None:
        for bad in [None, "string", 42, [1, 2, 3]]:
            with self.assertRaises(ValueError) as ctx:
                extract_cloudevent_payload(bad)
            self.assertIn("mapping", str(ctx.exception).lower())

    def test_non_mapping_data_raises_value_error(self) -> None:
        for bad_data in ["string-payload", 42, [1, 2, 3], None]:
            cloud_event = {
                "specversion": "1.0",
                "type": "com.agt.audit",
                "id": "ce-001",
                "data": bad_data,
            }
            with self.assertRaises(ValueError) as ctx:
                extract_cloudevent_payload(cloud_event)
            self.assertIn("data", str(ctx.exception).lower())

    def test_fixture_contains_no_sentinels(self) -> None:
        """Committed fixtures must not contain any test sentinel values."""
        valid_text = VALID_FIXTURE_PATH.read_text(encoding="utf-8")
        invalid_text = INVALID_FIXTURE_PATH.read_text(encoding="utf-8")
        SENTINELS = [
            "Authorization: Bearer test-secret-token",
            "DROP TABLE",
            "api_key=",
            "LEAK-ME",
        ]
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, valid_text,
                             f"valid fixture contains sentinel {sentinel!r}")
            self.assertNotIn(sentinel, invalid_text,
                             f"invalid fixture contains sentinel {sentinel!r}")


SKILL_MD_PATH = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "SKILL.md"
FIXTURE_PATH = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "test-fixture" / "consumer_prompt.md"
RUNBOOK_PATH = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references" / "runtime-audit-export.md"


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

    def test_skill_policy_fields_described_as_paths(self) -> None:
        """SKILL.md must describe redaction_policy and retention_policy as path strings."""
        skill_text = SKILL_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("redaction_policy", skill_text)
        self.assertIn("retention_policy", skill_text)

    def test_consumer_prompt_requires_specs_output(self) -> None:
        """test-fixture/consumer_prompt.md must require writing specs/agt-runtime-evidence.json."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("specs/agt-runtime-evidence.json", prompt_text,
                      "consumer_prompt.md does not mention specs/agt-runtime-evidence.json")

    def test_consumer_prompt_requires_allow_and_deny(self) -> None:
        """consumer_prompt.md must check allow_count and deny_count in the artifact."""
        prompt_text = FIXTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("allow_count", prompt_text)
        self.assertIn("deny_count", prompt_text)

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
        self.assertIn("Authorization: Bearer test-secret-token", prompt_text,
                      "consumer_prompt.md missing sentinel check for 'Authorization: Bearer test-secret-token'")

    def test_runbook_uses_extract_cloudevent_payload(self) -> None:
        """The runbook must reference extract_cloudevent_payload."""
        runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("extract_cloudevent_payload", runbook_text,
                      "runtime-audit-export.md must use extract_cloudevent_payload helper")

    def test_runbook_sentinel_is_realistic(self) -> None:
        """The runbook verification section must use the explicit test sentinel."""
        runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("Authorization: Bearer test-secret-token", runbook_text,
                      "runbook must use 'Authorization: Bearer test-secret-token' as test sentinel")

    def test_runbook_policy_as_path(self) -> None:
        """The runbook Step 5 must pass policy path strings, not inline objects."""
        runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/pii-redaction.md", runbook_text,
                      "runbook must show redaction_policy as a repo-relative path string")
        self.assertIn("infra/monitoring.bicep", runbook_text,
                      "runbook must show retention_policy as a repo-relative path string")

    def test_runbook_retention_policy_document_declares_lifecycle(self) -> None:
        """The runbook must state the referenced retention policy document declares lifecycle etc."""
        runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("lifecycle", runbook_text)
        self.assertIn("throughput", runbook_text)
        self.assertIn("backpressure", runbook_text)

    def test_producer_module_references_new_skill_heading(self) -> None:
        """runtime_evidence.py docstring must reference the Runtime audit evidence heading."""
        producer_path = REF_DIR / "python" / "runtime_evidence.py"
        head = producer_path.read_text(encoding="utf-8").splitlines()[:10]
        joined = "\n".join(head)
        self.assertIn("Runtime audit evidence", joined,
                      "runtime_evidence.py docstring does not reference '§ Runtime audit evidence'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
