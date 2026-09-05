"""Offline checks for AgentOps reference navigation and runnable command safety.

Native regression cases opt in with AGENTOPS_NATIVE_SOURCE and its src directory
on PYTHONPATH. They execute the pinned runner with inert invocation/evaluator
boundaries, blocked network and no telemetry. These checks do not certify Azure.
"""

from __future__ import annotations

import contextlib
import copy
import json
import os
import pathlib
import re
import runpy
import shlex
import shutil
import socket
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-agentops"
REFERENCE_NAMES = {
    "artifact-contract.md",
    "workflow-modes.md",
    "threadlight-boundary.md",
    "day2-runbook.md",
    "upstream-pin.md",
}
DAY2_COMMANDS = {
    ("eval", "analyze"),
    ("eval", "run"),
    ("eval", "promote-traces"),
    ("doctor",),
    ("workflow", "analyze"),
    ("redteam", "run"),
    ("assert", "run"),
}


class FoundryAgentOpsContractTests(unittest.TestCase):
    def read_reference(self, name: str) -> str:
        path = SKILL / "references" / name
        self.assertTrue(path.is_file(), f"Missing reference: {path.relative_to(ROOT)}")
        return path.read_text(encoding="utf-8")

    def test_reference_table_links_all_five_contracts(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        references = re.search(r"^## References\s*\n(.*?)(?=^## |\Z)", skill, re.M | re.S)
        self.assertIsNotNone(references, "SKILL.md needs a navigable References table")
        links = re.findall(r"\]\(references/([^)#]+)(?:#[^)]*)?\)", references[1])
        self.assertEqual(set(links), REFERENCE_NAMES)
        for name in links:
            self.read_reference(name)

    def test_local_reference_links_resolve_inside_skill(self) -> None:
        for name in sorted(REFERENCE_NAMES - {"upstream-pin.md"}):
            with self.subTest(reference=name):
                text = self.read_reference(name)
                for link in re.findall(r"\]\(([^)]+)\)", text):
                    if "://" in link or link.startswith("#"):
                        continue
                    path = (SKILL / "references" / link.split("#", 1)[0]).resolve()
                    self.assertTrue(path.is_relative_to(SKILL.resolve()), link)
                    self.assertTrue(path.is_file(), f"{name}: broken link {link}")

    def test_artifact_tables_cover_native_acceptance_fields(self) -> None:
        text = self.read_reference("artifact-contract.md")
        sections = {
            "results.json": {
                "version", "started_at", "finished_at", "duration_seconds",
                "target", "dataset_path", "thresholds", "summary", "aggregate_metrics",
            },
            "evidence.json": {"version", "generated_at", "workspace", "status", "target", "checks"},
            "redteam/latest.json": {
                "target", "risk_categories", "attack_strategies", "num_objectives",
                "total_attempts", "successful_attacks", "attack_success_rate",
                "per_category", "generated_at", "target_fingerprint",
            },
        }
        for artifact, fields in sections.items():
            with self.subTest(artifact=artifact):
                section = re.search(
                    rf"^## [^\n]*{re.escape(artifact)}[^\n]*\n(.*?)(?=^## |\Z)",
                    text, re.M | re.S,
                )
                self.assertIsNotNone(section, f"Missing schema section for {artifact}")
                documented = set(re.findall(r"^\| `([^`]+)` \|", section[1], re.M))
                self.assertTrue(fields <= documented, f"Undocumented {artifact} fields: {fields - documented}")

    def test_native_source_links_use_supported_tag(self) -> None:
        for name in ("artifact-contract.md", "workflow-modes.md", "day2-runbook.md"):
            with self.subTest(reference=name):
                text = self.read_reference(name)
                links = re.findall(r"https://github.com/Azure/agentops/(?:blob|tree)/([^/)]+)", text)
                self.assertTrue(links, f"{name} needs tagged implementation citations")
                self.assertEqual(set(links), {"v0.14.0"})

    def test_day2_commands_have_scoped_private_execution_blocks(self) -> None:
        text = self.read_reference("day2-runbook.md")
        blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
        self.assertTrue(blocks)
        seen = set()
        for block in blocks:
            with self.subTest(block=block):
                parsed = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                tokens = shlex.split(block.replace("\\\n", " "))
                self.assertIn("cd", tokens, "Every call must reselect the one-agent cwd")
                self.assertIn("umask", tokens)
                self.assertIn("077", tokens)
                self.assertIn("2>&1", tokens, "Raw native errors must stay local too")
                self.assertNotIn("tee", tokens)
                self.assertNotRegex(block, r"\|\|\s*(?:true|:)\b")
                for unsafe in ("--no-gate", "--no-preflight", "--force", "--cached"):
                    self.assertNotIn(unsafe, tokens)
                invocations = re.findall(r'"<agentops-bin>"\s+([^\n]+(?:\\\n[^\n]+)*)', block)
                self.assertTrue(invocations, "Use the verified absolute executable placeholder")
                for command in DAY2_COMMANDS:
                    if re.search(r'"<agentops-bin>"\s+' + r"\s+".join(command) + r"\b", block):
                        seen.add(command)
                if re.search(r'"<agentops-bin>"\s+eval\s+run\b', block):
                    self.assertRegex(block, r'env -u GITHUB_STEP_SUMMARY\s+"<agentops-bin>"')
                    self.assertIn("--baseline .agentops/baseline/results.json", block)
        self.assertEqual(seen, DAY2_COMMANDS)

    def test_workflow_generation_examples_are_explicit_and_non_forcing(self) -> None:
        text = self.read_reference("workflow-modes.md")
        blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
        generation = [block for block in blocks if "workflow generate" in block]
        self.assertTrue(generation, "Document the native standalone generation command")
        for block in generation:
            with self.subTest(block=block):
                tokens = shlex.split(block.replace("\\\n", " "))
                for option in ("--platform", "--kinds", "--deploy-mode", "--doctor-gate"):
                    self.assertIn(option, tokens)
                self.assertIn("cd", tokens)
                self.assertNotIn("--force", tokens)
                self.assertNotRegex(block, r"\|\|\s*(?:true|:)\b")

    def test_telemetry_approval_precedes_native_execution(self) -> None:
        text = self.read_reference("day2-runbook.md")
        gate = re.search(
            r"^## PRE-EXECUTION telemetry approval\n(.*?)(?=^## |\Z)",
            text, re.M | re.S,
        )
        self.assertIsNotNone(gate, "A private log is not a network-export approval gate")
        self.assertLess(gate.start(), text.index('"<agentops-bin>" eval analyze'))
        flattened = " ".join(gate[1].split())
        for required in (
            "BEFORE", "STOP", "foundry-observability", "tenant-local",
            "destination", "payload capture", "retention", "authorization",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING",
            "AGENTOPS_OTLP_ENDPOINT", "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT",
            "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=false",
            "full input", "expected", "Doctor", "auto-discovery",
        ):
            with self.subTest(required=required):
                    self.assertIn(required, flattened)
        self.assertRegex(flattened, r"no .*supported.*opt-out")
        self.assertIn("not authorization", flattened)
        for command in (
            "eval run", "doctor", "eval analyze", "eval promote-traces",
            "workflow analyze", "workflow generate", "init --no-prompt",
            "redteam run", "assert run",
        ):
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", gate[1])

    def test_privacy_references_distinguish_network_exports_from_local_logs(self) -> None:
        for name in ("artifact-contract.md", "workflow-modes.md", "threadlight-boundary.md"):
            with self.subTest(reference=name):
                text = self.read_reference(name)
                self.assertIn("day2-runbook.md#pre-execution-telemetry-approval", text)
                self.assertIn("network exports", text)
                self.assertIn("foundry-observability", text)
        text = self.read_reference("workflow-modes.md")
        self.assertIn("baseline", text)
        self.assertIn("BEFORE", text)
        self.assertIn("STOP", text)

    def test_skill_requires_telemetry_approval_before_eval_and_doctor(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        gate = text.find("### PRE-EXECUTION telemetry approval")
        self.assertGreaterEqual(gate, 0)
        self.assertLess(gate, text.index("## 2."))
        for section in ("## 3.", "## 5."):
            body = text.split(section, 1)[1].split("\n## ", 1)[0]
            self.assertIn("telemetry approval", body)
        self.assertIn("not a network-export opt-out", " ".join(text.split()))

    def test_smoke_requires_approved_exports_before_creating_resources(self) -> None:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        gate = text.find("PRE-EXECUTION telemetry approval")
        self.assertGreaterEqual(gate, 0)
        self.assertLess(gate, text.index("## Step 3"))
        self.assertIn("telemetry destination/capture/retention unapproved", text)
        self.assertIn("synthetic row is not authorization", text)
        self.assertIn("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=false", text)
        for step in (6, 7):
            body = text.split(f"## Step {step}", 1)[1].split("\n## Step ", 1)[0]
            self.assertIn("telemetry approval", body)
            self.assertIn("2>&1", body, "Doctor output needs local capture as well")

    def test_native_identity_gate_precedes_context_and_has_no_implicit_fallback(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        gate = re.search(
            r"^### PRE-EXECUTION credential isolation\n(.*?)(?=^### |\Z)",
            text, re.M | re.S,
        )
        self.assertIsNotNone(gate, "Native CLI-first selection needs an explicit isolation gate")
        self.assertLess(gate.start(), text.index("### Resolve deployment context"))
        flattened = " ".join(gate[1].split())
        for required in (
            "AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_TOKEN_CREDENTIALS",
            "AzureCliCredential", "EnvironmentCredential", "WorkloadIdentityCredential",
            "azure-identity~=1.25.3", "get_shared_credential", "before",
            "every Bash", "owner", "STOP", "CI", "show-don't-assert",
            "allowed_subscriptions", "no token", "global", "prod", "dev",
        ):
            with self.subTest(required=required):
                self.assertIn(required, flattened)
        self.assertIn("utils/azure_credentials.py", gate[1])
        self.assertIn("not authorization", flattened)

    def test_fixture_uses_only_parent_approved_credential_selection(self) -> None:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        step0 = text.split("## Step 0", 1)[1].split("\n## Step 1", 1)[0]
        for variable in ("AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_TOKEN_CREDENTIALS"):
            self.assertIn(variable, step0)
        self.assertNotIn("relying on DefaultAzureCredential", step0)
        self.assertNotIn("az account show", step0)
        self.assertIn("CI runner context is authoritative", step0)
        self.assertIn("before launching", step0)
        self.assertIn("every Bash", step0)
        self.assertIn("azure-identity~=1.25.3", text)
        self.assertIn("no token", text)
        self.assertIn("AzureCliCredential", text)

    def test_manual_reproduction_distinguishes_outer_stall_and_ci_identity(self) -> None:
        text = " ".join(self.read_reference("day2-runbook.md").split())
        for required in (
            "cached-user", "ci-cli", "AZURE_CLIENT_ID", "public application ID",
            "skill-loading stall", "manual equivalent", "CI service-principal",
            "Step 0", "Step 6", "Step 7", "python", "no native command",
        ):
            self.assertIn(required, text)
        self.assertNotIn("For **all three** modes", text)

    def test_telemetry_scope_and_retention_are_explicit_across_contracts(self) -> None:
        for path in (SKILL / "SKILL.md", SKILL / "references/day2-runbook.md",
                     SKILL / "references/artifact-contract.md",
                     SKILL / "test-fixture/consumer_prompt.md"):
            with self.subTest(path=path.name):
                text = " ".join(path.read_text(encoding="utf-8").split())
                for required in (
                    "component-scoped", "four", "1 day", "90", "7-day",
                    "store=false", "response ID", "stored responses",
                    "not fresh per-agent ingestion", "STOP",
                ):
                    self.assertIn(required, text)
        text = self.read_reference("day2-runbook.md")
        for field in ("WorkspaceResourceId", "retentionInDays", "totalRetentionInDays",
                      "app_insights_resource_id", "log_analytics_workspace_id"):
            self.assertIn(field, text)
        self.assertIn("before execution", text)

    def test_doctor_exit_two_is_not_a_readiness_pass(self) -> None:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        self.assertNotIn("`0` or `2` are acceptable", text)
        self.assertIn("doctor readiness blocked", text)
        self.assertIn("Foundry observability", self.read_reference("artifact-contract.md"))
        self.assertIn("not_configured", self.read_reference("artifact-contract.md"))

    def test_smoke_documents_required_judge_context_without_credential_substitution(self) -> None:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text()
        for required in ("AZURE_OPENAI_DEPLOYMENT", "AZURE_AI_MODEL_DEPLOYMENT_NAME",
                         "AZURE_OPENAI_ENDPOINT", "API-key", "parent"):
            self.assertIn(required, text)
        text = self.read_reference("day2-runbook.md")
        self.assertIn("AZURE_OPENAI_DEPLOYMENT", text)

    def test_credential_guidance_accounts_for_native_azd_leg(self) -> None:
        paths = [
            SKILL / "SKILL.md",
            SKILL / "test-fixture/consumer_prompt.md",
            SKILL / "references/day2-runbook.md",
            SKILL / "references/workflow-modes.md",
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("AzureDeveloperCliCredential", text)
                self.assertIn("exclude_developer_cli_credential=False", text)
                self.assertIn("fresh empty", text)
                self.assertIn("all three", text)
                self.assertIn("no login or token cache", text)
                self.assertNotIn("single-source", text)
                self.assertNotIn("approved single source required", text)

    def test_day2_and_generated_workflows_require_credential_isolation(self) -> None:
        for name in ("day2-runbook.md", "workflow-modes.md"):
            with self.subTest(reference=name):
                text = self.read_reference(name)
                self.assertIn("../SKILL.md#pre-execution-credential-isolation", text)
                for block in re.findall(r"```bash\n(.*?)```", text, re.S):
                    for variable in ("AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_TOKEN_CREDENTIALS"):
                        self.assertIn(f'${{{variable}:?', block)
                        self.assertLess(block.index(variable), block.index('"<agentops-bin>"'))
        workflow = self.read_reference("workflow-modes.md")
        self.assertIn("before authentication", workflow)
        self.assertIn("AzureCliCredential", workflow)
        self.assertIn("show-don't-assert", workflow)

    def test_agentops_ci_isolates_cache_before_login_for_all_child_steps(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/skill-test.yml").read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        login = next(i for i, step in enumerate(steps) if step.get("uses") == "azure/login@v2")
        setup = [step for step in steps[:login] if step.get("name") == "Isolate AgentOps credential sources"]
        self.assertEqual(len(setup), 1, "AgentOps isolation must precede azure/login")
        self.assertEqual(setup[0]["if"], "matrix.skill == 'foundry-agentops'")
        block = setup[0]["run"]
        for required in ("AZURE_CONFIG_DIR=", "AZD_CONFIG_DIR=",
                         "AZURE_TOKEN_CREDENTIALS=AzureCliCredential", "$GITHUB_ENV"):
            self.assertIn(required, block)
        self.assertNotIn("az account", block)
        self.assertNotIn("az login", block)
        self.assertNotIn("cp ", block)
        self.assertIn("mkdir", block)

    def test_assert_block_enforces_environment_in_the_invocation(self) -> None:
        text = self.read_reference("day2-runbook.md")
        block = next(
            block for block in re.findall(r"```bash\n(.*?)```", text, re.S)
            if '"<agentops-bin>" assert run' in block
        )
        # Execute the documented shell boundary with inert local stand-ins.
        # Never invoke an installed AgentOps, ASSERT, Azure CLI or credentials.
        workspace = ROOT / ".artifacts" / f"agentops-contract-{uuid.uuid4().hex}"
        approved = workspace / ".venv/bin"
        inherited = workspace / "inherited/bin"
        approved.mkdir(parents=True)
        inherited.mkdir(parents=True)
        try:
            outsider = inherited / "assert-ai"
            outsider.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            outsider.chmod(0o700)
            agentops = approved / "agentops"
            agentops.write_text(
                f"#!{sys.executable}\n"
                "import os, shutil, sys\n"
                "print('BOUNDARY_INVOKED')\n"
                f"approved = {str(approved / 'assert-ai')!r}\n"
                "if shutil.which('assert-ai') != approved:\n"
                "    sys.exit(97)\n"
                "if 'GITHUB_STEP_SUMMARY' in os.environ:\n"
                "    sys.exit(98)\n"
                f"assert os.environ['AZURE_CONFIG_DIR'] == {str(workspace / 'approved-azure')!r}\n"
                f"assert os.environ['AZD_CONFIG_DIR'] == {str(workspace / 'approved-azd')!r}\n"
                "assert os.environ['AZURE_TOKEN_CREDENTIALS'] == 'EnvironmentCredential'\n"
                "sys.exit(2)\n",
                encoding="utf-8",
            )
            agentops.chmod(0o700)
            missing_context = {
                "missing-azure-config": "AZURE_CONFIG_DIR",
                "missing-azd-config": "AZD_CONFIG_DIR",
                "missing-selector": "AZURE_TOKEN_CREDENTIALS",
            }
            for case in ("approved", "missing", "external-symlink", *missing_context):
                with self.subTest(case=case):
                    executable = approved / "assert-ai"
                    if executable.exists() or executable.is_symlink():
                        executable.unlink()
                    if case == "approved" or case in missing_context:
                        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                        executable.chmod(0o700)
                    elif case == "external-symlink":
                        executable.symlink_to(outsider)
                    script = (block.replace("<selected-agent-root>", str(workspace))
                              .replace("<approved-env-bin>", str(approved))
                              .replace("<agentops-bin>", str(agentops))
                              .replace("<run-id>", case))
                    env = {
                        "PATH": f"{inherited}:/usr/bin:/bin",
                        "AZURE_CONFIG_DIR": str(workspace / "approved-azure"),
                        "AZD_CONFIG_DIR": str(workspace / "approved-azd"),
                        "AZURE_TOKEN_CREDENTIALS": "EnvironmentCredential",
                        "GITHUB_STEP_SUMMARY": str(workspace / "must-not-write"),
                    }
                    if case in missing_context:
                        del env[missing_context[case]]
                    result = subprocess.run(
                        ["/bin/bash", "-c", script], text=True, capture_output=True,
                        env=env,
                    )
                    log = workspace / ".agentops/operations" / case / "assert.log"
                    output = log.read_text(encoding="utf-8") if log.exists() else ""
                    if case == "approved":
                        self.assertEqual(result.returncode, 2, result.stderr + output)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertNotIn("BOUNDARY_INVOKED", output)
                    self.assertEqual(result.stdout, "")
                    self.assertFalse((workspace / "must-not-write").exists())
        finally:
            shutil.rmtree(workspace)


class FoundryAgentOpsEvalResultTests(unittest.TestCase):
    AGENT = "ci-smoke-agentops-pa-offline"
    AGENT_VERSION = "7"
    SEED = {
        "id": "smoke-1",
        "input": "Reply with exactly PASS and nothing else.",
        "expected": "PASS",
    }
    PRIVATE_ERROR = "SYNTHETIC_PRIVATE_INVOCATION_OR_EVALUATOR_ERROR"
    DEFAULTS = [
        ("CoherenceEvaluator", "coherence", ">=", 3.0, 5.0),
        ("FluencyEvaluator", "fluency", ">=", 3.0, 5.0),
        ("SimilarityEvaluator", "similarity", ">=", 3.0, 5.0),
        ("ResponseCompletenessEvaluator", "response_completeness", ">=", 3.0, 5.0),
        ("avg_latency_seconds", "avg_latency_seconds", "<=", 30.0, 0.1),
    ]

    def setUp(self) -> None:
        self.workspace = ROOT / ".artifacts" / f"agentops-eval-contract-{uuid.uuid4().hex}"
        self.workspace.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.workspace)
        self.dataset = self.workspace / ".agentops/data/smoke.jsonl"
        self.dataset.parent.mkdir(parents=True)
        self.dataset.write_text(json.dumps(self.SEED) + "\n", encoding="utf-8")
        self.output = self.workspace / ".agentops/results/latest/results.json"
        self.output.parent.mkdir(parents=True)
        self.exit_file = self.workspace / ".agentops/results/eval-exit-code"

    def valid_result(self) -> dict:
        return {
            "version": 1,
            "started_at": "2026-09-04T00:00:00+00:00",
            "finished_at": "2026-09-04T00:00:01+00:00",
            "duration_seconds": 1.0,
            "target": {
                "kind": "foundry_prompt", "raw": f"{self.AGENT}:{self.AGENT_VERSION}",
                "name": self.AGENT, "version": self.AGENT_VERSION,
                "protocol": None, "url": None, "deployment": None,
            },
            "dataset_path": str(self.dataset),
            "evaluators": [name for name, *_ in self.DEFAULTS],
            "rows": [{
                "row_index": 0, "input": self.SEED["input"], "expected": self.SEED["expected"],
                "response": "PASS", "context": None, "latency_seconds": 0.1,
                "tool_calls": None, "error": None,
                "metrics": [
                    {"name": metric, "value": value, "error": None, "reason": None}
                    for _, metric, _, _, value in self.DEFAULTS
                ],
            }],
            "aggregate_metrics": {metric: value for _, metric, _, _, value in self.DEFAULTS},
            "thresholds": [
                {"metric": metric, "criteria": criteria, "expected": f"{criteria}{bound:g}",
                 "actual": f"{value:g}", "passed": True}
                for _, metric, criteria, bound, value in self.DEFAULTS
            ],
            "summary": {
                "items_total": 1, "items_passed_all": 1, "items_pass_rate": 1.0,
                "thresholds_total": 5, "thresholds_passed": 5,
                "threshold_pass_rate": 1.0, "overall_passed": True,
            },
            "comparison": None,
            "config": {"version": 1, "agent": f"{self.AGENT}:{self.AGENT_VERSION}", "thresholds": {}},
        }

    def check_result(self, status: str = "0", *, agent: str | None = None,
                     version: str | None = None) -> subprocess.CompletedProcess:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        step6 = text.split("## Step 6", 1)[1].split("\n## Step 7", 1)[0]
        blocks = re.findall(r"```python\n(.*?)\n```", step6, re.S)
        self.assertEqual(len(blocks), 1, "Step 6 must contain one executable result check")
        self.assertTrue(blocks[0].startswith("# BEGIN AGENTOPS EVAL RESULT CHECK\n"))
        self.assertTrue(blocks[0].endswith("# END AGENTOPS EVAL RESULT CHECK"))
        self.exit_file.write_text(status + "\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-c", blocks[0],
             self.AGENT if agent is None else agent,
             self.AGENT_VERSION if version is None else version],
            cwd=self.workspace, capture_output=True, text=True,
            env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def assert_rejected(self, result: dict, status: str = "0", **binding) -> None:
        self.output.write_text(json.dumps(result), encoding="utf-8")
        checked = self.check_result(status, **binding)
        self.assertNotEqual(checked.returncode, 0, "Invalid execution artifact was accepted")
        self.assertEqual(checked.stdout, "")
        self.assertEqual(checked.stderr.strip(), "eval results contract failed")
        self.assertNotIn(self.PRIVATE_ERROR, checked.stdout + checked.stderr)

    def test_accepts_scored_native_shape_with_optional_nulls_or_omissions(self) -> None:
        for omit in (False, True):
            with self.subTest(omit_optional=omit):
                result = self.valid_result()
                if omit:
                    for key in ("protocol", "url", "deployment"):
                        del result["target"][key]
                    for key in ("error", "context", "tool_calls", "latency_seconds"):
                        del result["rows"][0][key]
                    for metric in result["rows"][0]["metrics"]:
                        del metric["error"]
                        del metric["reason"]
                    del result["comparison"]
                self.output.write_text(json.dumps(result), encoding="utf-8")
                checked = self.check_result()
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(checked.stderr, "")
                self.assertIn("quality gate=passed", checked.stdout)

    def test_accepts_only_executed_threshold_failure_without_relabeling_gate(self) -> None:
        result = self.valid_result()
        result["rows"][0]["metrics"][0]["value"] = 0.0
        result["aggregate_metrics"]["coherence"] = 0.0
        result["thresholds"][0].update(actual="0", passed=False)
        result["summary"].update(thresholds_passed=4, threshold_pass_rate=0.8, overall_passed=False)
        self.output.write_text(json.dumps(result), encoding="utf-8")
        checked = self.check_result("2")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("quality gate=failed; native exit=2", checked.stdout)
        self.assertEqual(self.exit_file.read_text().strip(), "2")
        self.assert_rejected(result, "0")
        self.assert_rejected(self.valid_result(), "2")

    def test_rejects_missing_or_malformed_artifacts_and_unexpected_exit(self) -> None:
        for content in (None, "", "{", "null", "[]", "{}"):
            with self.subTest(content=content):
                if content is not None:
                    self.output.write_text(content, encoding="utf-8")
                checked = self.check_result()
                self.assertNotEqual(checked.returncode, 0)
                self.assertEqual(checked.stderr.strip(), "eval results contract failed")
        for status in ("1", "3", "-1", "", "garbage"):
            with self.subTest(status=status):
                self.assert_rejected(self.valid_result(), status)

    def test_rejects_bad_missing_mismatched_empty_or_error_fields(self) -> None:
        cases = [
            (("version",), [None, 2, True, "1"]),
            (("target",), [None, {}, []]),
            (("target", "kind"), [None, "foundry", "model_direct", "foundry_hosted"]),
            (("target", "raw"), [None, "", "other:7", f"{self.AGENT}:8"]),
            (("target", "name"), [None, "", "other"]),
            (("target", "version"), [None, "", "8", 7]),
            (("target", "protocol"), ["responses"]),
            (("target", "url"), ["https://example.invalid/"]),
            (("target", "deployment"), ["model"]),
            (("dataset_path",), [None, "", "other.jsonl"]),
            (("rows",), [None, [], {}, [self.valid_result()["rows"][0]] * 2]),
            (("rows", 0), [None, {}]),
            (("rows", 0, "row_index"), [None, 1, False]),
            (("rows", 0, "input"), [None, "", "different input"]),
            (("rows", 0, "expected"), [None, "", "different expected"]),
            (("rows", 0, "response"), [None, "", " \n\t", 7]),
            (("rows", 0, "error"), ["", self.PRIVATE_ERROR]),
            (("rows", 0, "metrics"), [None, [], {}]),
            (("rows", 0, "metrics", 0, "name"), [None, "", "unexpected"]),
            (("rows", 0, "metrics", 0, "value"), [None, "", True, float("nan"), float("inf")]),
            (("rows", 0, "metrics", 0, "error"), ["", self.PRIVATE_ERROR]),
            (("evaluators",), [None, [], ["F1ScoreEvaluator"]]),
            (("aggregate_metrics",), [None, {}]),
            (("aggregate_metrics", "coherence"), [None, True, 1.0, float("nan")]),
            (("thresholds",), [None, [], {}]),
            (("thresholds", 0, "metric"), [None, "unexpected"]),
            (("thresholds", 0, "actual"), [None, "", "missing", "4", "nan"]),
            (("thresholds", 0, "expected"), [None, ">=0"]),
            (("thresholds", 0, "criteria"), [None, "<="]),
            (("thresholds", 0, "passed"), [None, 1, False]),
            (("summary",), [None, {}]),
            (("summary", "items_total"), [None, 0, 2, True]),
            (("summary", "items_passed_all"), [None, 0, True]),
            (("summary", "items_pass_rate"), [None, 0.0, True]),
            (("summary", "thresholds_total"), [None, 0, 1]),
            (("summary", "thresholds_passed"), [None, 0, 4]),
            (("summary", "threshold_pass_rate"), [None, 0.0, float("nan")]),
            (("summary", "overall_passed"), [None, False, 1, "false"]),
        ]
        optional = {("target", "protocol"), ("target", "url"), ("target", "deployment"),
                    ("rows", 0, "error"), ("rows", 0, "metrics", 0, "error")}
        missing = object()
        for path, values in cases:
            for value in values + ([] if path in optional else [missing]):
                with self.subTest(path=path, value="missing" if value is missing else value):
                    result = self.valid_result()
                    container = result
                    for key in path[:-1]:
                        container = container[key]
                    if value is missing:
                        del container[path[-1]]
                    else:
                        container[path[-1]] = value
                    self.assert_rejected(result)
        result = self.valid_result()
        result["rows"][0]["metrics"].append(copy.deepcopy(result["rows"][0]["metrics"][0]))
        self.assert_rejected(result)
        for key in ("evaluators", "thresholds"):
            result = self.valid_result()
            result[key].append(copy.deepcopy(result[key][0]))
            self.assert_rejected(result)

    def test_requires_independent_step3_binding_and_exact_seed(self) -> None:
        for binding in ({"agent": ""}, {"version": ""}, {"agent": "other"}, {"version": "8"}):
            with self.subTest(binding=binding):
                self.assert_rejected(self.valid_result(), **binding)
        for content in ("", "{}\n", json.dumps(self.SEED) + "\n" + json.dumps(self.SEED) + "\n"):
            with self.subTest(seed=content):
                self.dataset.write_text(content, encoding="utf-8")
                self.assert_rejected(self.valid_result())

    @unittest.skipUnless(os.environ.get("AGENTOPS_NATIVE_SOURCE"),
                         "Set AGENTOPS_NATIVE_SOURCE to the exact offline v0.14.0 checkout")
    def test_pinned_native_runner_reproduces_old_false_pass_and_checks_real_artifacts(self) -> None:
        source = pathlib.Path(os.environ["AGENTOPS_NATIVE_SOURCE"]).resolve()
        pin = yaml.safe_load(
            (SKILL / "references/upstream-pin.md").read_text(encoding="utf-8").split("---", 2)[1]
        )
        sha = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True,
        ).strip()
        self.assertEqual(sha, pin["upstream"]["pinned_sha"])
        subprocess.run(
            ["git", "-C", str(source), "diff", "--quiet", "HEAD", "--", "src/agentops"],
            check=True,
        )
        from agentops.core.agentops_config import AgentOpsConfig
        from agentops.pipeline import invocations, orchestrator, runtime
        self.assertTrue(pathlib.Path(orchestrator.__file__).resolve().is_relative_to(source))
        config = AgentOpsConfig(
            version=1, agent=f"{self.AGENT}:{self.AGENT_VERSION}",
            dataset=self.dataset, execution="local",
        )

        for scenario in ("passed", "threshold", "invocation-error", "evaluator-error",
                         "unscored", "empty-response"):
            with self.subTest(scenario=scenario), contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(
                    socket.socket, "connect", side_effect=AssertionError("Network forbidden"),
                ))
                stack.enter_context(patch(
                    "agentops.utils.azure_credentials.get_shared_credential",
                    side_effect=AssertionError("Credentials forbidden"),
                ))
                for name in ("eval_run_span", "eval_item_span", "agent_invoke_span"):
                    stack.enter_context(patch.object(
                        orchestrator.telemetry, name, side_effect=lambda **_: contextlib.nullcontext(None),
                    ))
                for name in ("set_eval_run_result", "set_eval_item_result",
                             "set_agent_invoke_result", "record_evaluator_span"):
                    stack.enter_context(patch.object(orchestrator.telemetry, name))
                stack.enter_context(patch.object(
                    orchestrator, "_publish_to_foundry_safely",
                    side_effect=AssertionError("Publishing forbidden"),
                ))

                def invoke(*args, **kwargs):
                    if scenario == "invocation-error":
                        raise RuntimeError(self.PRIVATE_ERROR)
                    return invocations.InvocationResult(
                        response="" if scenario == "empty-response" else "PASS",
                        latency_seconds=0.1,
                    )

                def load_evaluators(presets):
                    def score(**kwargs):
                        if scenario == "evaluator-error":
                            raise RuntimeError(self.PRIVATE_ERROR)
                        return {} if scenario == "unscored" else {"score": 0 if scenario == "threshold" else 5}
                    return [
                        runtime.load_evaluator(preset) if preset.class_name == "_latency"
                        else runtime.EvaluatorRuntime(preset=preset, callable=score)
                        for preset in presets
                    ]

                stack.enter_context(patch.object(invocations, "invoke", side_effect=invoke))
                stack.enter_context(patch.object(runtime, "load_evaluators", side_effect=load_evaluators))
                result = orchestrator._run_evaluation_local(
                    config, options=orchestrator.RunOptions(
                        config_path=self.workspace / "agentops.yaml", output_dir=self.output.parent,
                    ),
                )
                status = orchestrator.exit_code_from(result)
                payload = json.loads(self.output.read_text(encoding="utf-8"))
                # Historical Step 6: all six native outcomes passed these assertions.
                self.assertIn(status, (0, 2))
                self.assertEqual(payload["version"], 1)
                self.assertIsInstance(payload["summary"]["overall_passed"], bool)
                if scenario in ("invocation-error", "evaluator-error"):
                    self.assertEqual(status, 2)
                    self.assertEqual(payload["summary"]["items_passed_all"], 0)
                checked = self.check_result(str(status))
                if scenario in ("passed", "threshold"):
                    self.assertEqual(checked.returncode, 0, checked.stderr)
                else:
                    self.assertNotEqual(checked.returncode, 0, "Native execution failure was accepted")
                    self.assertEqual(checked.stderr.strip(), "eval results contract failed")
                self.assertNotIn(self.PRIVATE_ERROR, checked.stdout + checked.stderr)

class FoundryAgentOpsCredentialContractTests(unittest.TestCase):
    def check_context(self, route: str, **overrides) -> subprocess.CompletedProcess:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```python\n(# BEGIN AGENTOPS AUTH CONTEXT CHECK\n.*?)\n```", text, re.S)
        self.assertEqual(len(blocks), 1, "Fixture needs an executable route-aware presence check")
        env = {
            "PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1",
            "AZURE_CONFIG_DIR": "/approved/azure",
            "AZD_CONFIG_DIR": "/approved/empty-azd",
            "AZURE_TENANT_ID": "approved-tenant",
            "AZURE_SUBSCRIPTION_ID": "approved-subscription",
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.invalid/api/projects/synthetic",
            "AZURE_TOKEN_CREDENTIALS": {
                "cached-user": "AzureCliCredential", "ci-cli": "AzureCliCredential",
                "environment": "EnvironmentCredential", "workload": "WorkloadIdentityCredential",
            }.get(route, "AzureCliCredential"),
        }
        if route != "cached-user":
            env["AZURE_CLIENT_ID"] = "approved-principal-client"
        if route == "environment":
            env["AZURE_CLIENT_SECRET"] = "SYNTHETIC_SECRET"
        if route == "workload":
            env["AZURE_FEDERATED_TOKEN_FILE"] = "/approved/token-file"
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            [sys.executable, "-c", blocks[0], route], text=True, capture_output=True, env=env,
        )

    def test_cached_cli_user_needs_no_client_id(self) -> None:
        result = self.check_context("cached-user")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AZURE_CLIENT_ID=unset (cached user; not required)", result.stdout)

    def test_ci_cli_environment_and_workload_keep_real_client_contract(self) -> None:
        for route in ("ci-cli", "environment", "workload"):
            with self.subTest(route=route):
                result = self.check_context(route)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("AZURE_CLIENT_ID=set", result.stdout)
                self.assertNotIn("SYNTHETIC_SECRET", result.stdout + result.stderr)
                self.assertNotIn("approved-principal-client", result.stdout + result.stderr)

    def test_rejects_missing_meaningful_or_fabricated_client_context(self) -> None:
        for route in ("ci-cli", "environment", "workload"):
            for value in (None, "", "N/A", "not applicable", "<client-id>"):
                with self.subTest(route=route, value=value):
                    self.assertNotEqual(self.check_context(route, AZURE_CLIENT_ID=value).returncode, 0)
        self.assertNotEqual(self.check_context("cached-user", AZURE_CLIENT_ID="N/A").returncode, 0)
        for route in ("cached-user", "ci-cli", "environment", "workload"):
            for variable in ("AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_TOKEN_CREDENTIALS",
                             "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "FOUNDRY_PROJECT_ENDPOINT"):
                with self.subTest(route=route, variable=variable):
                    self.assertNotEqual(self.check_context(route, **{variable: None}).returncode, 0)
        self.assertNotEqual(self.check_context("cached-user", AZURE_TOKEN_CREDENTIALS="EnvironmentCredential").returncode, 0)
        self.assertNotEqual(self.check_context("environment", AZURE_CLIENT_SECRET=None).returncode, 0)
        self.assertNotEqual(self.check_context("workload", AZURE_FEDERATED_TOKEN_FILE=None).returncode, 0)
        self.assertNotEqual(self.check_context("invented").returncode, 0)


class FoundryAgentOpsDoctorContractTests(unittest.TestCase):
    """Sanitized native-shaped regressions; never load live logs or responses."""

    def setUp(self) -> None:
        self.workspace = ROOT / ".artifacts" / f"agentops-doctor-contract-{uuid.uuid4().hex}"
        self.workspace.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.workspace)
        self.agent_dir = self.workspace / ".agentops/agent"
        self.agent_dir.mkdir(parents=True)
        self.output = self.workspace / ".agentops/release/latest/evidence.json"
        self.output.parent.mkdir(parents=True)
        self.agent = "ci-smoke-agentops-pa-offline"
        self.version = "7"
        self.start = "2026-09-05T00:00:00+00:00"
        self.end = "2026-09-05T00:01:00+00:00"
        self.sources = ["results_history", "azure_monitor", "foundry_control", "azure_resources"]

    def evidence(self, critical: int = 0) -> tuple[dict, dict]:
        counts = {"critical": critical, "warning": 8, "info": 1}
        severity = "critical" if critical else "warning"
        doctor = {"status": "ok", "findings_total": sum(counts.values()),
                  "max_severity": severity, "counts": counts, "top_findings": []}
        evidence = {
            "version": 1, "generated_at": self.end, "workspace": str(self.workspace),
            "status": "blocked" if critical else "ready_with_warnings",
            "target": f"{self.agent}:{self.version}",
            "checks": [
                {"name": "Doctor readiness", "status": "blocked" if critical else "warning",
                 "summary": "Synthetic readiness", "evidence": doctor},
                {"name": "Foundry observability", "status": "ready",
                 "summary": "Synthetic contradictory native claim", "evidence": {}},
                {"name": "AI Landing Zone readiness", "status": "unknown", "summary": "Synthetic unknown"},
                {"name": "Governance artifacts", "status": "unknown", "summary": "Synthetic unknown"},
            ],
            "blockers": ["Synthetic critical finding"] if critical else [],
            "warnings": ["Synthetic warning"], "ready": [], "links": [],
            "doctor": doctor,
            "observability": {"status": "not_configured", "dataset_kind": "auto",
                              "multi_turn_ready": True, "multi_turn_rows": 0, "rubrics_count": 0,
                              "rubrics": [], "evaluation_urls": [], "datasets_url": None},
            "monitoring": {
                "status": "ok", "request_count": 42,
                "diagnostics": {"enabled": True, "status": "ok", "lookback_days": 1,
                                "safety_status": "ok", "token_status": "ok", "rate_limit_status": "ok"},
            },
            "foundry": {"status": "ok", "agents_count": 1, "enabled_evaluation_rules": 0},
            "official_eval": {"status": "missing"},
            "ailz": {"status": "not_detected"},
            "governance": {},
        }
        history = {
            "timestamp": self.end, "findings_total": sum(counts.values()),
            "findings_by_severity": counts, "findings_by_category": {},
            "max_severity": severity, "sources_enabled": self.sources,
            "lookback_days": 1, "duration_seconds": 60.0,
            "findings": [{"id": "synthetic.finding", "severity": level}
                         for level, count in counts.items() for _ in range(count)],
        }
        return evidence, history

    def check(self, evidence: dict, history: dict, status: str = "0") -> subprocess.CompletedProcess:
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```python\n(# BEGIN AGENTOPS DOCTOR EVIDENCE CHECK\n.*?)\n```", text, re.S)
        self.assertEqual(len(blocks), 1, "Step 7 needs an executable evidence/history check")
        self.output.write_text(json.dumps(evidence), encoding="utf-8")
        for name, content in (
            ("history.jsonl", json.dumps(history)),
            ("doctor-exit-code", status),
            ("doctor-started-at", self.start), ("doctor-finished-at", self.end),
        ):
            (self.agent_dir / name).write_text(content + "\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-c", blocks[0], self.agent, self.version],
            cwd=self.workspace, text=True, capture_output=True,
            env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_real_critical_shape_keeps_doctor_two_blocked_and_payload_private(self) -> None:
        evidence, history = self.evidence(critical=1)
        evidence["blockers"] = ["SYNTHETIC_PRIVATE_FINDING"]
        result = self.check(evidence, history, "2")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("readiness gate=blocked; native exit=2", result.stdout)
        self.assertIn("critical=1; warning=8; info=1", result.stdout)
        self.assertNotIn("SYNTHETIC_PRIVATE_FINDING", result.stdout + result.stderr)
        self.assertEqual((self.agent_dir / "doctor-exit-code").read_text().strip(), "2")

    def test_verified_doctor_two_maps_to_execution_pass_not_readiness_pass(self) -> None:
        evidence, history = self.evidence(critical=1)
        result = self.check(evidence, history, "2")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("readiness gate=blocked; native exit=2", result.stdout)
        self.assertEqual(json.loads(self.output.read_text()), evidence)
        self.assertEqual((self.agent_dir / "doctor-exit-code").read_text().strip(), "2")
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text(encoding="utf-8")
        mapping = " ".join(text.split("On checker exit 2,", 1)[1].split("On checker exit 1", 1)[0].split())
        marker = re.search(r"\bwrite (PASS|FAIL)\b", mapping)
        self.assertIsNotNone(marker, "The fixture must explicitly map Doctor 2 to a smoke marker")
        self.assertEqual(marker[1], "PASS", "Verified Doctor readiness blockers are not execution failures")
        for required in ("Step 6", "Step 7", "assertions", "readiness **BLOCKED**", "native exit `2`"):
            self.assertIn(required, mapping)
        self.assertIn("never suppress", mapping)

    def test_ready_observability_does_not_certify_zero_rows_or_rubrics(self) -> None:
        evidence, history = self.evidence()
        result = self.check(evidence, history)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("native observability=ready; coverage=unverified", result.stdout)
        self.assertIn("observability detail=not_configured; multi-turn rows=0; rubrics=0", result.stdout)
        self.assertIn("official eval=missing", result.stdout)
        self.assertIn("governance=unknown; landing zone=unknown", result.stdout)
        self.assertIn("not fresh per-agent ingestion", result.stdout)
        self.assertEqual(json.loads(self.output.read_text()), evidence, "Do not rewrite native evidence")

    def test_rejects_missing_sources_stale_unbound_or_inconsistent_doctor(self) -> None:
        for scenario in ("source-disabled", "stale", "wrong-agent", "version",
                         "counts", "severity-exit", "missing-checks", "missing-doctor"):
            with self.subTest(scenario=scenario):
                evidence, history = self.evidence()
                if scenario == "source-disabled":
                    history["sources_enabled"] = self.sources[:-1]
                elif scenario == "stale":
                    evidence["generated_at"] = "2026-09-04T00:00:00+00:00"
                elif scenario == "wrong-agent":
                    evidence["target"] = "other:7"
                elif scenario == "version":
                    evidence["version"] = True
                elif scenario == "counts":
                    history["findings_by_severity"]["info"] = 8
                elif scenario == "severity-exit":
                    evidence, history = self.evidence(critical=1)
                elif scenario == "missing-checks":
                    evidence["checks"] = []
                else:
                    del evidence["doctor"]
                result = self.check(evidence, history)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr.strip(), "doctor evidence contract failed")

    def test_failed_secondary_query_is_unverified_even_when_primary_is_ok(self) -> None:
        evidence, history = self.evidence()
        evidence["monitoring"]["diagnostics"]["token_status"] = "error"
        result = self.check(evidence, history)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("component aggregates=unverified", result.stdout)

    @unittest.skipUnless(os.environ.get("AGENTOPS_NATIVE_SOURCE"),
                         "Set AGENTOPS_NATIVE_SOURCE to the exact offline v0.14.0 checkout")
    def test_pinned_native_scope_storage_and_observability_limits(self) -> None:
        source = pathlib.Path(os.environ["AGENTOPS_NATIVE_SOURCE"]).resolve()
        pin = yaml.safe_load((SKILL / "references/upstream-pin.md").read_text().split("---", 2)[1])
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True,
        ).strip(), pin["upstream"]["pinned_sha"])
        subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--", "src/agentops"], check=True)
        from agentops.agent.config import AgentConfig
        from agentops.agent.sources import azure_monitor
        from agentops.core.agentops_config import AgentOpsConfig, TargetResolution
        from agentops.core.release_evidence import ReleaseEvidence
        from agentops.pipeline import invocations
        from agentops.services import evidence_pack
        from pydantic import ValidationError
        self.assertTrue(pathlib.Path(evidence_pack.__file__).resolve().is_relative_to(source))
        evidence, _ = self.evidence(critical=1)
        self.assertEqual(ReleaseEvidence.model_validate(evidence).version, 1)
        fixture = (SKILL / "test-fixture/consumer_prompt.md").read_text()
        step4 = fixture.split("## Step 4", 1)[1].split("\n## Step 5", 1)[0]
        configs = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)```", step4, re.S)]
        doctor_config = next(config for config in configs if "sources" in config)
        config = AgentConfig.model_validate(doctor_config)
        self.assertEqual(config.lookback_days, 1)
        self.assertTrue(all(getattr(config.sources, name).enabled for name in self.sources))
        self.assertIsNone(config.sources.azure_monitor.log_analytics_workspace_id)
        for invalid in (0, 0.5):
            with self.assertRaises(ValidationError):
                AgentConfig(lookback_days=invalid)
        for query in (azure_monitor._REQUESTS_KQL, azure_monitor._SAFETY_KQL,
                      azure_monitor._TOKEN_USAGE_KQL, azure_monitor._RATE_LIMIT_KQL):
            self.assertIn("ago(1d)", query.format(lookback_days=1))
            self.assertNotIn("agent_id", query)
            self.assertNotIn("operation_Id", query)

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")))
            stack.enter_context(patch("agentops.utils.azure_credentials.get_shared_credential",
                                      side_effect=AssertionError("Credentials forbidden")))
            (self.workspace / "agentops.yaml").write_text("version: 1\n", encoding="utf-8")
            observability = evidence_pack._observability_status(self.workspace, {"status": "missing"})
            checks, warnings, ready = [], [], []
            evidence_pack._add_observability_check(checks, warnings, ready, observability)
            self.assertEqual(observability["status"], "not_configured")
            self.assertEqual((observability["multi_turn_rows"], observability["rubrics_count"]), (0, 0))
            self.assertTrue(observability["multi_turn_ready"])
            self.assertEqual(checks[0].status, "ready", "Regression must preserve actual upstream overstatement")

            stack.enter_context(patch.object(invocations, "_get_token", return_value="SYNTHETIC_TOKEN"))
            http = stack.enter_context(patch.object(invocations, "_http_request_json", return_value={
                "id": "SYNTHETIC_RESPONSE_ID",
                "output": [{"type": "message", "role": "assistant",
                            "content": [{"type": "output_text", "text": "PASS"}]}],
            }))
            target = TargetResolution(kind="foundry_prompt", protocol=None,
                                      raw="synthetic:7", name="synthetic", version="7")
            result = invocations._invoke_foundry_prompt(
                target, AgentOpsConfig(version=1, agent="synthetic:7",
                                       dataset=self.workspace / "synthetic.jsonl",
                                       project_endpoint="https://example.invalid/api/projects/synthetic"),
                {"input": "Reply with exactly PASS and nothing else."}, timeout=1,
            )
            self.assertNotIn("store", http.call_args.kwargs["body"])
            self.assertEqual(result.response, "PASS")
            self.assertEqual(result.metadata, {})
            self.assertNotIn("SYNTHETIC_RESPONSE_ID", repr(result))


class FoundryAgentOpsCatalogTests(unittest.TestCase):
    VALIDATION_RECORD = "docs/maintenance/foundry-agentops-validation.md"

    @staticmethod
    def frontmatter(path: pathlib.Path) -> dict:
        return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])

    def test_plugin_and_marketplace_share_catalog_release(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".github/plugin/marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(plugin["skills"], "skills/")
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["source"], ".")
        self.assertEqual(entry["name"], plugin["name"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertEqual(marketplace["metadata"]["version"], plugin["version"])
        self.assertEqual(plugin["version"], "4.31.0")
        self.assertEqual(self.frontmatter(SKILL / "SKILL.md")["metadata"]["version"], "1.0.0")

    def test_manifest_counts_match_discovered_skills(self) -> None:
        count = len(list((ROOT / "skills").glob("*/SKILL.md")))
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".github/plugin/marketplace.json").read_text(encoding="utf-8")
        )
        for description in (
            plugin["description"], marketplace["metadata"]["description"],
            marketplace["plugins"][0]["description"],
        ):
            with self.subTest(description=description):
                match = re.search(r"\b(\d+) (?:reusable (?:GBB )?(?:building blocks|skills)|skills)\b", description)
                self.assertIsNotNone(match, "Manifest must advertise the discovered skill count")
                self.assertEqual(int(match[1]), count)

    def test_agentops_discovery_keywords_match_in_both_manifests(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        entry = json.loads(
            (ROOT / ".github/plugin/marketplace.json").read_text(encoding="utf-8")
        )["plugins"][0]
        keywords = {"agentops", "agent-operations", "release-evidence", "doctor", "regression-baseline"}
        self.assertTrue(keywords <= set(plugin["keywords"]))
        self.assertEqual(entry["keywords"], plugin["keywords"])

    def test_agentops_registered_once_with_evals_and_observability(self) -> None:
        site = runpy.run_path(str(ROOT / "scripts/build-site.py"))
        categories = site["CATEGORIES"]
        occurrences = sum(members.count(SKILL.name) for members in categories.values())
        self.assertEqual(occurrences, 1, "AgentOps needs exactly one catalog category")
        category = next(members for members in categories.values() if SKILL.name in members)
        self.assertIn("foundry-evals", category)
        self.assertIn("foundry-observability", category)
        site["assert_categorization"](site["load_skills"](ROOT))
        self.assertEqual(site["load_plugins"](ROOT)[0]["skills"].count(SKILL.name), 1)

    def test_matrix_includes_agentops_and_fans_out_from_each_specialist(self) -> None:
        matrix = runpy.run_path(str(ROOT / "scripts/build-test-matrix.py"))
        self.assertEqual(matrix["build"](ROOT)["skill"].count(SKILL.name), 1)
        deps = matrix["_load_dep_map"](ROOT)
        expected = {"foundry-prompt-agents", "foundry-evals", "foundry-observability", "foundry-agt"}
        self.assertEqual(set(deps[SKILL.name]), expected)
        for owner in expected:
            with self.subTest(owner=owner):
                self.assertIn(SKILL.name, matrix["_expand_transitively"]({owner}, deps))
        self.assertEqual(matrix["_expand_transitively"]({SKILL.name}, deps), {SKILL.name})

    def test_specialists_link_once_to_agentops(self) -> None:
        for name in ("foundry-evals", "foundry-observability", "foundry-agt"):
            with self.subTest(skill=name):
                path = ROOT / "skills" / name / "SKILL.md"
                text = path.read_text(encoding="utf-8")
                links = re.findall(r"\]\(([^)]+)\)", text)
                agentops_links = [link for link in links if "foundry-agentops" in link]
                self.assertEqual(agentops_links, ["../foundry-agentops/SKILL.md"])
                self.assertEqual((path.parent / agentops_links[0]).resolve(), (SKILL / "SKILL.md").resolve())

    def test_specialist_links_have_patch_versions_and_valid_frontmatter(self) -> None:
        minimum_versions = {
            "foundry-evals": (1, 3, 2),
            "foundry-observability": (1, 2, 4),
            "foundry-agt": (2, 0, 1),
        }
        for name, minimum in minimum_versions.items():
            with self.subTest(skill=name):
                fm = self.frontmatter(ROOT / "skills" / name / "SKILL.md")
                self.assertEqual(set(fm), {"name", "description", "metadata"})
                self.assertEqual(fm["name"], name)
                self.assertLessEqual(len(fm["description"]), 1024)
                self.assertGreaterEqual(tuple(map(int, fm["metadata"]["version"].split("."))), minimum)

    def test_readme_has_one_catalog_row_and_versioned_adoption_entry(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| \[\*\*foundry-agentops\*\*\]\(skills/foundry-agentops/\) \|.*$", text, re.M)
        self.assertEqual(len(rows), 1)
        usage = text.split("## How to Use", 1)[1].split("\n## ", 1)[0]
        links = re.findall(r"\]\(([^)]+)\)", usage)
        self.assertIn("skills/foundry-agentops/SKILL.md", links)
        pin = self.frontmatter(SKILL / "references/upstream-pin.md")
        package = next(p for p in pin["packages"] if p["name"] == "agentops-accelerator")
        self.assertIn(f'agentops-accelerator=={package["version"]}', usage)
        version = self.frontmatter(SKILL / "SKILL.md")["metadata"]["version"]
        self.assertIn(f"skill {version}", usage)
        self.assertIn("# Install the published release (not the draft addition):", usage)
        count = len(list((ROOT / "skills").glob("*/SKILL.md")))
        self.assertIn(f"skills-{count}-blue", text)
        for advertised in re.findall(r"\ball (\d+) skills\b", text):
            self.assertEqual(int(advertised), count)

    def test_agents_coverage_counts_follow_source_inventory(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        skills = list((ROOT / "skills").glob("*/SKILL.md"))
        pins = [self.frontmatter(p) for p in (ROOT / "skills").glob("*/references/upstream-pin.md")]
        fixtures = {p.parents[1].name for p in (ROOT / "skills").glob("*/test-fixture/consumer_prompt.md")}
        deps = yaml.safe_load((ROOT / ".github/skill-deps.yml").read_text(encoding="utf-8"))["skills"]
        self.assertTrue(fixtures <= deps.keys())
        counts = {
            "Total skills": len(skills),
            "Skills with upstream pins": len(pins),
            "Auto-tier (CI can refresh autonomously)": sum(p["automation_tier"] == "auto" for p in pins),
            "Issue-only (human / complex deploy)": sum(p["automation_tier"] == "issue_only" for p in pins),
            "Internal IP (no upstream)": len(skills) - len(pins),
        }
        glance = text.split("### 12.5", 1)[1].split("\n## ", 1)[0]
        for label, count in counts.items():
            with self.subTest(metric=label):
                self.assertRegex(glance, rf"(?m)^\| {re.escape(label)} \| {count} \|$")
        coverage = text.split("### 12.3", 1)[1].split("\n### ", 1)[0]
        self.assertIn(f"({len(skills)} skills, {len(pins)} with upstream pins)", coverage)
        self.assertRegex(coverage, rf"(?m)^\| Auto-tier .* \| {counts['Auto-tier (CI can refresh autonomously)']} pins \|")
        self.assertRegex(coverage, rf"(?m)^\| Copilot-CLI fixtures \| {len(fixtures)} skills \|")

    def test_proposed_release_notes_link_versioned_skill_changes(self) -> None:
        path = ROOT / "CHANGELOG.md"
        self.assertTrue(path.is_file(), "The proposed catalog addition needs unreleased notes")
        text = path.read_text(encoding="utf-8")
        version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
        self.assertRegex(text, rf"(?mi)^## .*{re.escape(version)}.*unreleased")
        for name in ("foundry-agentops", "foundry-evals", "foundry-observability", "foundry-agt"):
            with self.subTest(skill=name):
                fm = self.frontmatter(ROOT / "skills" / name / "SKILL.md")
                self.assertIn(f"(skills/{name}/SKILL.md)", text)
                self.assertIn(fm["metadata"]["version"], text)

    def assert_partial_validation_status(self, text: str) -> None:
        text = " ".join(re.sub(r"<[^>]+>", " ", text).replace("**", "").split())
        for expected in (
            "corrected-source manual execution PASS", "quality FAIL (4/5 thresholds)",
            "Doctor readiness BLOCKED", "release PENDING",
        ):
            self.assertIn(expected, text)
        self.assertNotRegex(
            text.casefold(),
            r"all (?:live |validation |release |ci )?gates (?:have )?passed"
            r"|production[- ](?:ready|readiness) (?:certified|passed)"
            r"|unchanged ci/sp (?:passed|validated)|every skill works end-to-end",
        )
        self.assertNotRegex(
            text.casefold(),
            r"corrected-source rerun pending|owner context selection (?:is )?pending"
            r"|corrected-source (?:manual )?execution \+ quality pass",
        )

    def assert_draft_candidate_status(self, text: str) -> None:
        text = " ".join(re.sub(r"<[^>]+>", " ", text).replace("**", "").split()).casefold()
        for expected in (
            "draft candidate eligible for PR validation",
            "not merged, released, or production-ready",
            "CI results and candidate SHA will be recorded in the PR",
        ):
            self.assertIn(expected.casefold(), text)
        for stale in (
            "local draft", "no downstream commit pin",
            "committed source does not yet contain", "pending publication",
            "requires separate push/PR authorization", "still prohibited", "still-unrun",
        ):
            self.assertNotIn(stale.casefold(), text)

    def test_catalog_sources_link_partial_manual_evidence(self) -> None:
        for name in ("README.md", "CHANGELOG.md", "AGENTS.md"):
            with self.subTest(source=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                if name == "AGENTS.md":
                    text = text.split("### 12.3", 1)[1].split("\n### 12.4", 1)[0]
                self.assertIn(f"]({self.VALIDATION_RECORD})", text)
                self.assert_partial_validation_status(text)
                self.assert_draft_candidate_status(text)
                self.assertNotIn("CI/SP NOT RUN", text)
                self.assertNotIn("full matrix NOT RUN", text)
                self.assertNotIn("live Foundry gate remains", text)
                self.assertIn("unreleased", text.casefold())

    def test_partial_status_guard_rejects_blanket_success_claims(self) -> None:
        status = (
            "corrected-source manual execution PASS; quality FAIL (4/5 thresholds); "
            "Doctor readiness BLOCKED; CI/SP NOT RUN; full matrix NOT RUN; release PENDING."
        )
        self.assert_partial_validation_status(status)
        for claim in (
            "All gates passed", "All live gates passed", "Unchanged CI/SP validated",
            "Every skill works end-to-end", "corrected-source rerun PENDING",
            "Owner context selection is pending", "Corrected-source manual execution + quality PASS",
        ):
            with self.subTest(claim=claim), self.assertRaises(AssertionError):
                self.assert_partial_validation_status(status + " " + claim)

    def test_validation_record_preserves_provenance_and_limitations(self) -> None:
        path = ROOT / self.VALIDATION_RECORD
        self.assertTrue(path.is_file(), "Publish only a sanitized outcome, not raw private evidence")
        text = path.read_text(encoding="utf-8")
        self.assert_partial_validation_status(text)
        for expected in (
            "2026-09-05", "agentops-accelerator==0.14.0", "AzureCliCredential",
            "one native cycle", "target", "eval judge", "Doctor judge", "Sol",
            "5/5", "exit 0", "exit 2", "evidence v1",
            "results_history", "azure_monitor", "foundry_control", "azure_resources",
            "1 critical", "8 warnings", "1 info", "API key",
            "not_configured", "0 rows", "0 rubrics", "24-hour",
            "fresh ingestion", "official evaluation", "governance", "landing-zone",
            "existing conversations", "404", "store=false", "response ID",
            "service retention", "7-day", "90-day", "illustrative",
            "first skill-load", "manual continuation", "wrong subscription",
            "owner context selection", "push/PR authorization is granted", "no account changes",
            "SHA-256", "prior fixture",
        ):
            with self.subTest(fact=expected):
                self.assertIn(expected, text)
        self.assertIn("not publicly installable", text)
        self.assertIn("no released downstream pin", text)
        self.assert_draft_candidate_status(text)
        self.assertIn("Before PR CI, as of 2026-09-05", text)
        self.assertIn("CI/SP NOT RUN", text)
        self.assertIn("full matrix NOT RUN", text)

    def test_corrected_cycle_reports_threshold_failure_not_green_row_proxy(self) -> None:
        text = (ROOT / self.VALIDATION_RECORD).read_text(encoding="utf-8")
        self.assertIn("## Corrected-source manual cycle", text)
        corrected = text.split("## Corrected-source manual cycle", 1)[1].split("\n## ", 1)[0]
        for fact in (
            "166.5 seconds", "AzureCliCredential", "auth exit 0", "Analyze exit 0",
            "Eval exit 2", "execution checker exit 0", "fluency 2", "threshold 3",
            "exact expected match", "items_passed_all=1", "overall_passed=false",
            "thresholds_passed=4", "thresholds_total=5",
            "Doctor exit 2", "evidence checker exit 2", "evidence v1",
            "2 critical", "8 warnings", "1 info",
            "opex.release.latest_eval_failed", "waf.security.local_auth_disabled",
            "no retry", "no threshold reduction", "no errors hidden", "no shared repair",
        ):
            with self.subTest(fact=fact):
                self.assertIn(fact, corrected)
        self.assertNotIn("5/5", corrected)
        self.assertIn("## Prior manual cycle (historical, distinct)", text)
        prior = text.split("## Prior manual cycle (historical, distinct)", 1)[1].split("\n## ", 1)[0]
        self.assertIn("5/5 thresholds passed", prior)
        self.assertIn("1 critical", prior)
        self.assertIn("first skill-load", prior)

    def test_validation_record_binds_corrected_fixture_and_preserves_prior_fingerprints(self) -> None:
        import hashlib

        text = (ROOT / self.VALIDATION_RECORD).read_text(encoding="utf-8")
        fixture_digest = hashlib.sha256(
            (SKILL / "test-fixture/consumer_prompt.md").read_bytes()
        ).hexdigest()
        self.assertEqual(
            fixture_digest,
            "22de211e642a915c451c444e1f8005624108e3a5b4d7769c422520fe098aea5e",
            "Changed fixture requires new corrected-source live evidence",
        )
        expected = {
            "Executed corrected-source fixture": fixture_digest,
            "Corrected approval": "60436f44aa6e105f17c435268010dd4a0dfb2c84c7002894378d233cf229f058",
            "Corrected native results": "f40a0419dbee405e01f9fa445049b300bf6286c5f07e61a0ccdad850b7823563",
            "Corrected Doctor evidence": "c52e7c5453c6958281fc642a6e1208034d4a575a48223000d0e5d512358cee16",
            "Corrected Doctor history": "fbd2f2c237690539ed2505d9891c219918dfe6908e4788c282232f20e8ba4510",
            "Corrected outcome": "363dcadb7fdcb1542950bd4b57a269a70927e4ebd74829311a08f03449851560",
            "Verified prior outcome summary": "f9c63bae9bb1689951f0c51951129c5b9a0390226c28d33e3e55e5ef5d6c81f7",
            "Executed prior fixture, not corrected source": "49d8cc10d42aa159b4cf8220a11d25d114f85c3376256d39607138d502463f4d",
        }
        for artifact, digest in expected.items():
            with self.subTest(artifact=artifact):
                self.assertIn(f"| {artifact} | `{digest}` |", text)
        for package, version in (
            ("azure-identity", "1.25.3"), ("azure-ai-projects", "2.4.0"), ("httpx", "0.28.1"),
        ):
            self.assertIn(f"`{package}` {version}", text)

    def test_cleanup_and_scheduled_retention_do_not_claim_service_purge(self) -> None:
        text = (ROOT / self.VALIDATION_RECORD).read_text(encoding="utf-8")
        text = " ".join(text.replace("**", "").split())
        for fact in (
            "GET 404", "new copied credentials", "Persistent model deployments were untouched",
            "response ID", "purge unproven", "approved service retention",
            "Both cycles", "2026-09-12", "07:29:57 UTC", "intentionally earlier",
            "not proof that deletion has occurred",
        ):
            with self.subTest(fact=fact):
                self.assertIn(fact, text)

    def test_validation_record_excludes_private_identifiers_and_payloads(self) -> None:
        path = ROOT / self.VALIDATION_RECORD
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        forbidden = (
            r"(?i)\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
            r"(?i)/(?:Users|home|subscriptions)/|[A-Z]:\\Users\\|session-state/",
            r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b",
            r"(?i)https?://[^\s/]*(?:azure\.com|azurecr\.io|azurewebsites\.net)",
            r"(?i)\b(?:resp_|conv_)[a-z0-9_-]+",
            r"```(?:json|jsonl|log)\b",
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotRegex(text, pattern)

    def test_unreleased_metadata_is_scoped_to_agentops_and_proposed_plugin(self) -> None:
        site = runpy.run_path(str(ROOT / "scripts/build-site.py"))
        skills = site["load_skills"](ROOT)
        drafts = [s for s in skills if s.get("draft")]
        self.assertEqual([s["name"] for s in drafts], [SKILL.name])
        self.assertEqual(drafts[0]["draft"]["record"], self.VALIDATION_RECORD.removeprefix("docs/"))
        plugin = site["load_plugins"](ROOT)[0]
        self.assertEqual(plugin["draft"], drafts[0]["draft"])
        self.assert_partial_validation_status(plugin["draft"]["summary"])
        self.assert_draft_candidate_status(plugin["draft"]["summary"])

    def test_draft_pages_show_pending_gates_not_public_agentops_install(self) -> None:
        site = runpy.run_path(str(ROOT / "scripts/build-site.py"))
        templates = runpy.run_path(str(ROOT / "scripts/site_templates.py"))
        skills = site["load_skills"](ROOT)
        plugins = site["load_plugins"](ROOT)
        agentops = next(s for s in skills if s["name"] == SKILL.name)
        categories = site["CATEGORIES"]
        pages = {
            "home": templates["render_home"](categories, skills, plugins),
            "skills": templates["render_skills_index"](skills, categories),
            "agentops": templates["render_skill_detail"](agentops, categories, [plugins[0]["name"]]),
            "plugins": templates["render_plugins_index"](plugins),
            "plugin": templates["render_plugin_detail"](plugins[0], skills, categories),
            "llms": templates["render_llms_txt"](categories, skills, plugins),
        }
        for name, text in pages.items():
            with self.subTest(page=name):
                self.assert_partial_validation_status(text)
                self.assert_draft_candidate_status(text)
                self.assertNotIn("CI/SP NOT RUN", text)
                self.assertNotIn("full matrix NOT RUN", text)
                self.assertIn("/maintenance/foundry-agentops-validation.md", text)
                self.assertIn("unreleased", text.casefold())
                self.assertIn("not publicly installable", text)
                self.assertNotIn("gh skill install aiappsgbb/awesome-gbb foundry-agentops", text)
                self.assertNotIn("/blob/main/skills/foundry-agentops/SKILL.md", text)
        self.assertNotIn("last validated", pages["agentops"])
        for name in ("plugins", "plugin"):
            self.assertNotIn("copilot plugin install awesome-gbb@awesome-gbb", pages[name])
        existing = next(s for s in skills if s["name"] == "foundry-evals")
        existing_page = templates["render_skill_detail"](existing, categories, [plugins[0]["name"]])
        self.assertIn("gh skill install aiappsgbb/awesome-gbb foundry-evals", existing_page)
        self.assertNotIn("/maintenance/foundry-agentops-validation.md", existing_page)

    def test_manifests_label_proposed_catalog_not_a_public_install(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".github/plugin/marketplace.json").read_text(encoding="utf-8"))
        for description in (
            plugin["description"], marketplace["metadata"]["description"],
            marketplace["plugins"][0]["description"],
        ):
            with self.subTest(description=description):
                self.assertIn("unreleased", description.casefold())
                self.assertIn("proposed", description.casefold())

    def test_catalog_rendering_does_not_claim_unrecorded_live_validation(self) -> None:
        site = runpy.run_path(str(ROOT / "scripts/build-site.py"))
        templates = runpy.run_path(str(ROOT / "scripts/site_templates.py"))
        skills = site["load_skills"](ROOT)
        pages = {
            "home": templates["render_home"](
                site["CATEGORIES"], skills, site["load_plugins"](ROOT),
            ),
            "skills": templates["render_skills_index"](skills, site["CATEGORIES"]),
        }
        for name, html in pages.items():
            with self.subTest(page=name):
                self.assertNotIn("production-tested", html.casefold())
                self.assertNotIn("live-tested", html.casefold())


if __name__ == "__main__":
    unittest.main()
