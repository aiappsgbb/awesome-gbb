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
        self.assertIn("No progress, ACK, separate dependency/ ownership-release or frozen-head", text)
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
        self.assertIn("Preserve `execution_role`: a coordinator resumes coordination", text)
        self.assertIn("Reconcile an explicit role change against live child ownership first", text)
        self.assertIn("Do not poll it or resend an unchanged blocker on recovery", text)
        self.assertIn("compaction itself neither grants consent nor reopens an unchanged question", text)
        self.assertIn("Restore the role and ownership before the next action", text)


if __name__ == "__main__":
    unittest.main()
