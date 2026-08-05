#!/usr/bin/env python3
"""Focused regression tests for the foundry-hosted-agents refresh contract."""

from __future__ import annotations

import ast
import os
import pathlib
import re
import shlex
import subprocess
import tempfile
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-hosted-agents"
SKILL = SKILL_DIR / "SKILL.md"
FIXTURE = SKILL_DIR / "test-fixture" / "consumer_prompt.md"
PIN = SKILL_DIR / "references" / "upstream-pin.md"
TIMEOUT = SKILL_DIR / "references" / "python" / "foundry_agent_timeout.py"


class FoundryHostedAgentsRefreshContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.fixture = FIXTURE.read_text(encoding="utf-8")
        cls.pin = PIN.read_text(encoding="utf-8")
        cls.timeout = TIMEOUT.read_text(encoding="utf-8")
        cls.pin_frontmatter = yaml.safe_load(cls.pin.split("---", 2)[1])
        cls.validation_script = cls.pin_frontmatter["validation"]["script"]
        validation_python = re.search(
            r"python - <<'PY'\n(?P<body>.*?)\nPY(?:\n|$)",
            cls.validation_script,
            flags=re.DOTALL,
        )
        if validation_python is None:
            raise AssertionError("validation Python heredoc not found")
        cls.validation_python = validation_python.group("body")
        dependency_function = re.search(
            r"require_canonical_dependency\(\) \{\n.*?^\}",
            cls.fixture,
            flags=re.DOTALL | re.MULTILINE,
        )
        if dependency_function is None:
            raise AssertionError("fixture dependency guard not found")
        cls.dependency_function = dependency_function.group(0)

    def test_timeout_reference_requires_current_versions(self) -> None:
        self.assertIn("- agent-framework-core ~= 1.13.0", self.timeout)
        self.assertIn("- agent-framework-foundry ~= 1.10.4", self.timeout)
        self.assertNotIn("- agent-framework-core ~= 1.11.0", self.timeout)
        self.assertNotIn("- agent-framework-foundry ~= 1.10.1", self.timeout)

    def test_pin_records_final_live_validation_date(self) -> None:
        self.assertEqual(str(self.pin_frontmatter["last_validated"]), "2026-08-05")
        self.assertNotIn("this 2026-08-04 validation", self.pin)

    def test_historical_upgrade_recipes_are_guarded_from_copying(self) -> None:
        guard = (
            "> **Historical boundary only — do not copy these pins; use "
            "[`references/python/pyproject.toml`](references/python/pyproject.toml).**"
        )
        for target in ("1.7.0", "1.8.0"):
            with self.subTest(target=target):
                recipe = re.search(
                    rf"### Upgrade recipe \(→ {re.escape(target)}\)\n\n"
                    rf"(?P<guard>.*?)\n\n```bash",
                    self.skill,
                    flags=re.DOTALL,
                )
                self.assertIsNotNone(recipe, f"missing {target} upgrade recipe")
                self.assertEqual(recipe.group("guard"), guard)
        self.assertNotIn(
            "Exact pin per AGENTS.md § 9.5 alpha\npre-release discipline.",
            self.skill,
        )
        self.assertIn(
            "current operators must use the exact beta "
            "`agent-framework-foundry-hosting==1.0.0b260730`",
            self.skill,
        )

    def test_pin_validation_checks_all_selected_installed_versions(self) -> None:
        required = (
            'assert version("agent-framework-foundry-hosting") == "1.0.0b260730"',
            'assert version("azure-identity").startswith("1.25.")',
            'assert version("python-dotenv").startswith("1.2.")',
        )
        for assertion in required:
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, self.validation_python)

    def test_pin_validation_guards_removed_surfaces_and_ga_models(self) -> None:
        required = (
            "from azure.ai.projects.models import (",
            "ContainerConfiguration,",
            "HostedAgentDefinition,",
            "ProtocolVersionRecord,",
            "from azure.ai.projects.operations import BetaAgentsOperations",
            "assert not hasattr(BetaAgentsOperations, \"patch_agent_details\")",
            "from agent_framework.azure import AzureOpenAIChatClient",
            "FAIL: AzureOpenAIChatClient unexpectedly still importable",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.validation_python)

    def test_fixture_guards_all_canonical_runtime_dependencies(self) -> None:
        required = (
            "agent-framework-core~=1.13.0",
            "agent-framework-foundry~=1.10.4",
            "agent-framework-foundry-hosting==1.0.0b260730",
            "azure-ai-projects~=2.3.0",
            "azure-identity~=1.25.3",
            "mcp~=1.29.0",
            "python-dotenv~=1.2.2",
        )
        calls = re.findall(r'^require_canonical_dependency "([^"]+)"$', self.fixture, re.MULTILINE)
        self.assertEqual(calls, list(required))

    def _run_dependency_guard(
        self, pyproject: str, dependency: str
    ) -> tuple[subprocess.CompletedProcess[str], str | None]:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = pathlib.Path(tmp)
            (work_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
            marker = work_dir / "result"
            script = "\n".join(
                (
                    "set -euo pipefail",
                    self.dependency_function,
                    f"work_dir={shlex.quote(str(work_dir))}",
                    f"require_canonical_dependency {shlex.quote(dependency)}",
                )
            )
            env = os.environ.copy()
            env["SMOKE_RESULT_MARKER"] = str(marker)
            result = subprocess.run(
                ["bash", "-c", script],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            marker_text = marker.read_text(encoding="utf-8") if marker.exists() else None
        return result, marker_text

    def test_fixture_dependency_guard_accepts_exact_canonical_pin(self) -> None:
        dependency = "agent-framework-core~=1.13.0"
        result, marker = self._run_dependency_guard(
            f'[project]\ndependencies = ["{dependency}"]\n', dependency
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(marker)

    def test_fixture_dependency_guard_writes_exact_failure_marker(self) -> None:
        dependency = "agent-framework-core~=1.13.0"
        result, marker = self._run_dependency_guard(
            '[project]\ndependencies = ["agent-framework-core~=1.12.0"]\n',
            dependency,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            marker,
            f"SMOKE_RESULT=FAIL canonical pyproject dependency drift: {dependency}\n",
        )

    def test_fixture_records_parity_and_preserves_single_deploy_contract(self) -> None:
        self.assertIn('record "CANONICAL_PYPROJECT_OK"', self.fixture)
        self.assertIn('r"CANONICAL_PYPROJECT_OK"', self.fixture)
        active_deploys = re.findall(
            r"^\s*azd deploy\b.*$", self.fixture, flags=re.MULTILINE
        )
        active_ups = re.findall(r"^\s*azd up\b.*$", self.fixture, flags=re.MULTILINE)
        self.assertEqual(active_deploys, ['  azd deploy "$agent_name" --no-prompt'])
        self.assertEqual(active_ups, [])

    def test_pin_validation_imports_canonical_container_and_otel_bundle(self) -> None:
        bash_syntax = subprocess.run(
            ["bash", "-n"],
            input=self.validation_script,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(bash_syntax.returncode, 0, bash_syntax.stderr)
        compile(self.validation_python, "<hosted-pin-validation>", "exec")
        validation_tree = ast.parse(self.validation_python)
        main_calls = [
            node
            for node in ast.walk(validation_tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "main")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "main")
            )
        ]
        self.assertEqual(main_calls, [], "pin smoke must import, not run, container main")
        self.assertIn("class OfflineCredential:", self.validation_python)
        self.assertIn(
            'raise RuntimeError("network is outside the import smoke")',
            self.validation_python,
        )
        self.assertNotIn("DefaultAzureCredential(", self.validation_python)
        self.assertNotIn("AzureCliCredential(", self.validation_python)

        required = (
            "PIN_VALIDATION_REPO_ROOT",
            "references/python/container.py",
            "importlib.util.spec_from_file_location",
            "container_spec.loader.exec_module(container_module)",
            "from microsoft.opentelemetry import use_microsoft_opentelemetry",
            "from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor",
            'print("ok canonical container import")',
            'print("ok otel bundle")',
            "assert callable(client.agents.update_details)",
            'print("ok hosted coherent stack")',
            'print("ok update_details")',
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.pin)
        self.assertEqual(
            self.pin_frontmatter["validation"]["expected_output"],
            [
                "ok canonical container import",
                "ok hosted coherent stack",
                "ok update_details",
                "ok otel bundle",
            ],
        )


if __name__ == "__main__":
    unittest.main()
