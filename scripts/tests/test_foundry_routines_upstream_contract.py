"""Regression contracts for the additive official routines workflow."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-routines" / "SKILL.md"
REFERENCE = SKILL.parent / "references" / "azd-routines.md"
PIN = SKILL.parent / "references" / "upstream-pin.md"


class FoundryRoutinesUpstreamContractTests(unittest.TestCase):
    def reference(self) -> str:
        self.assertTrue(REFERENCE.is_file(), "the azd workflow reference is missing")
        return REFERENCE.read_text(encoding="utf-8")

    def test_manifest_uses_wire_schedule_fields(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        manifests = [
            yaml.safe_load(block)
            for block in re.findall(r"```yaml\n(.*?)```", skill, re.DOTALL)
        ]
        routines = [doc for doc in manifests if isinstance(doc, dict) and "triggers" in doc]
        self.assertTrue(routines, "keep a standalone routine manifest")
        for routine in routines:
            for trigger in routine["triggers"].values():
                if trigger["type"] == "schedule":
                    self.assertIn("cron_expression", trigger)
                    self.assertNotIn("cron", trigger)

    def test_existing_entry_point_retains_sdk_and_routes_to_azd(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("(references/azd-routines.md)", skill)
        for operation in ("create_or_update", "dispatch", "list_runs", "delete"):
            self.assertIn(f"client.beta.routines.{operation}", skill)

    def test_skill_no_longer_denies_documented_event_and_cli_capabilities(self) -> None:
        skill = " ".join(SKILL.read_text(encoding="utf-8").split())
        for obsolete in (
            "Only `schedule` and `timer` triggers",
            "`azd ai routine` cannot list run history",
            "inline-flag form is timer-only",
        ):
            self.assertNotIn(obsolete, skill)
        self.assertIn("github_issue", skill)
        self.assertIn("custom", skill)

    def test_aliases_are_distinct_from_wire_types(self) -> None:
        reference = self.reference()
        for row in (
            "| `recurring` | `schedule` |",
            "| `github-issue` | `github_issue` |",
            "| `agent-response` | `invoke_agent_responses_api` |",
            "| `agent-invoke` | `invoke_agent_invocations_api` |",
        ):
            self.assertIn(row, reference)

    def test_stored_input_and_manual_override_are_not_conflated(self) -> None:
        reference = " ".join(self.reference().split())
        for required in (
            "`action.input`",
            "create` has no `--input` flag",
            "does not change the stored `action.input`",
            "`--file` and `--trigger` are mutually exclusive",
        ):
            self.assertIn(required, reference)

    def test_event_support_does_not_imply_arbitrary_webhooks(self) -> None:
        reference = " ".join(self.reference().split())
        for required in (
            "`connection_id`",
            "consent",
            "`teams`",
            "not a generic HTTP webhook",
            "Manual dispatch does not prove event delivery",
        ):
            self.assertIn(required, reference)

    def test_cli_history_and_project_target_are_explicit(self) -> None:
        reference = self.reference()
        self.assertIn("azd ai routine run list", reference)
        commands = re.findall(
            r"^azd ai routine (?!.*--help).*",
            reference.replace("\\\n", ""),
            re.MULTILINE,
        )
        self.assertTrue(commands)
        for command in commands:
            with self.subTest(command=command):
                self.assertIn('-p "$FOUNDRY_PROJECT_ENDPOINT"', command)

    def test_named_trigger_update_uses_manifest_not_default_only_flags(self) -> None:
        reference = self.reference()
        self.assertIn("azd ai routine update daily-summary --file", reference)
        self.assertIn("`default` trigger", reference)
        self.assertNotIn("azd ai routine update daily-summary --cron", reference)

    def test_trigger_update_rejection_is_not_reported_as_successful_upsert(self) -> None:
        reference = self.reference()
        self.assertIn("Routine trigger cannot be changed after creation", reference)
        self.assertIn("description-only", reference)
        self.assertNotIn(
            "operation replaces the\nstored definition. Omitted fields reset to defaults.",
            SKILL.read_text(encoding="utf-8"),
        )

    def test_run_completion_does_not_promise_response_body_readback(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("correlation handle", skill)
        self.assertIn("404", skill.split("## 6 · Run history", 1)[1].split("\n## ", 1)[0])
        self.assertNotIn("open in the portal to see the full agent response", skill)

    def test_declarative_manifest_preserves_naming_and_dependencies(self) -> None:
        reference = self.reference()
        documents = [
            yaml.safe_load(block)
            for block in re.findall(r"```yaml\n(.*?)```", reference, re.DOTALL)
        ]
        services = [
            doc["services"]
            for doc in documents
            if isinstance(doc, dict) and "services" in doc
        ]
        self.assertEqual(len(services), 1)
        routine = services[0]["daily-summary"]
        self.assertEqual(routine["host"], "azure.ai.routine")
        self.assertEqual(routine["uses"], ["summary-agent"])
        self.assertNotIn("name", routine)
        self.assertIn("does not delete", reference)

    def test_upsert_and_type_change_boundaries_are_documented(self) -> None:
        reference = " ".join(self.reference().split())
        for required in (
            "`create` refuses to overwrite",
            "`--force`",
            "trigger and action types are immutable",
            "retains the old routine until",
        ):
            self.assertIn(required, reference)

    def test_pin_preserves_validation_date_but_corrects_old_cli_claims(self) -> None:
        raw = PIN.read_text(encoding="utf-8")
        metadata = yaml.safe_load(raw.split("---", 2)[1])
        self.assertEqual(str(metadata["last_validated"]), "2026-08-17")
        issues = {issue["id"]: issue for issue in metadata["known_issues"]}
        self.assertIn("recurring", issues["KI-001"]["description"])
        self.assertIn("run list", issues["KI-002"]["description"])
        self.assertNotIn("does not list run history", raw)
        self.assertNotIn("timer-only", raw)

    def test_source_alignment_does_not_claim_new_live_acceptance(self) -> None:
        reference = self.reference()
        self.assertIn("a55fe6da7e24cbcf4331aafb903e4a070a35e972", reference)
        self.assertIn("SDK lifecycle only", reference)
        self.assertIn("live acceptance", reference)
        self.assertIn("azure-tenant-isolation", reference)


if __name__ == "__main__":
    unittest.main()
