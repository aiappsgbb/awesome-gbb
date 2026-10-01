"""Static contract regressions, not proof of model decisions or message suppression."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RoleContractTests(unittest.TestCase):
    def text(self, name):
        return " ".join((ROOT / name).read_text(encoding="utf-8").split())

    def test_coordinator_routes_direct_work_and_delegates_executable_acceptance(self):
        text = self.text("references/children.md")
        self.assertIn("An active coordinator does not implement, build/test, deeply debug", text)
        self.assertIn("Route a direct implementation request to an existing suitable executor", text)
        self.assertIn("Integration, executable verification and publication require", text)
        self.assertIn("not each tiny step", text)
        self.assertIn("never perform them in the coordinator", text)
        self.assertNotIn("parent owns integration", text)

    def test_terminal_only_contract_has_no_dependency_or_status_back_door(self):
        text = self.text("references/children.md")
        self.assertIn("Return one terminal result per execution", text)
        self.assertIn("An unchanged blocker is not a new result", text)
        self.assertIn("No progress, ACK, separate dependency/ownership-release or frozen-head", text)
        self.assertIn("ordinary authorized recovery", text)
        self.assertIn("Do not wait for more progress from a blocked/stopped child or poll it", text)
        self.assertIn("A resolved block resumes the same assignment with its history", text)
        self.assertNotIn("notice to affected consumers is allowed", text)
        self.assertNotIn("An explicit status request can be answered", text)
        storage = self.text("references/storage.md")
        self.assertIn("not an intermediate-notice exception", storage)
        self.assertIn("same receipt, not authorization to send it again", storage)

    def test_solo_work_safety_and_native_gates_remain_intact(self):
        text = self.text("SKILL.md")
        self.assertIn("Ordinary solo work stays direct", text)
        self.assertIn("loading this skill never requires a child", text)
        self.assertIn("one-process end-to-end constraints", text)
        self.assertIn("Safety incidents, urgent cancellation and required permission/input gates", text)
        self.assertIn("host-generated notifications cannot be suppressed", text)
        children = self.text("references/children.md")
        self.assertIn("never hide a permission request just to obey quiet mode", children)
        self.assertIn("Host/tool/human confirmations remain mandatory", children)
        self.assertIn("Missing or unavailable reply is not consent", children)

    def test_compaction_restores_role_and_ownership_without_approval_reset(self):
        text = self.text("references/compaction.md")
        self.assertIn("preserve `execution_role`, all active handles/ownership", text)
        self.assertIn("Compaction itself neither grants consent nor reopens an unchanged question", text)
        self.assertIn("resumes a stopped child, resets failure history or authorizes role change", text)
        self.assertIn("Restore the role and ownership before the next action", text)

    def test_acceptance_is_targeted_not_blind_or_duplicate_execution(self):
        text = self.text("references/children.md")
        self.assertIn("Inspect enough final evidence to establish acceptance", text)
        self.assertIn("not automatically all artifacts, manifests or logs", text)
        self.assertIn("request targeted clarification, not blind trust", text)
        self.assertIn("never perform them in the coordinator", text)
        self.assertIn("retain the accepted high-water revision", text)
        self.assertIn("Missing/unreachable evidence is unverified", text)

    def test_kickoff_carries_task_context_not_repeated_protocol(self):
        text = (ROOT / "references/children.md").read_text()
        kickoff = text.split("```text\n", 1)[1].split("```", 1)[0]
        for field in ("Assignment", "plan revision", "Load progress-guard",
                      "own\nledger", "Outcome / acceptance", "Ownership",
                      "Baseline / dependencies / capacity", "Authority / escalation",
                      "Declared limits", "Avoid", "Return channel"):
            self.assertIn(field, kickoff)
        self.assertNotIn("Return one terminal result", kickoff)
        self.assertNotIn("approval records", kickoff)
        self.assertIn("The skill supplies quiet return, approval and recovery rules", text)

    def test_snapshot_boundaries_do_not_require_append_readback_ritual(self):
        skill = self.text("SKILL.md")
        self.assertIn("one event with a complete compact snapshot", skill)
        self.assertIn("no compulsory full readback after every append", skill)
        self.assertIn("after resume/compaction, before a retry, on changed inputs", skill)
        self.assertIn("final acceptance/handoff", skill)
        for file in ("references/children.md", "references/compaction.md"):
            text = self.text(file)
            self.assertIn("Successful append confirmation suffices", text)
        storage = self.text("references/storage.md")
        self.assertIn("`append --event -`", storage)
        self.assertIn("If the call's outcome is uncertain, read current state before retrying", storage)
        self.assertIn("Never invent token, turn or task budgets", skill)
        self.assertIn("UNKNOWN fences its effects and interfering work", skill)


if __name__ == "__main__":
    unittest.main()
