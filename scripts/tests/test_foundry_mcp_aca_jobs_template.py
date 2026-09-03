#!/usr/bin/env python3
"""Template contract tests for foundry-mcp-aca-jobs."""

from __future__ import annotations

import ast
import io
import os
import pathlib
import importlib.util
import re
import sys
import shutil
import subprocess
import json
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from scripts.tests.test_foundry_mcp_aca_jobs_protocol import _install_stubs
from azure.mgmt.appcontainers.models import EnvironmentVar as AcaEnvironmentVar


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-mcp-aca-jobs"
SKILL_DIR = SKILL / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))
_install_stubs()

from app.models import Policy


class FoundryMcpAcaJobsTemplateTests(unittest.TestCase):
    @staticmethod
    def _azd_env_values() -> dict[str, str]:
        return {
            "SERVICE_MCP_IMAGE_NAME": "myregistry.azurecr.us/mcp/service:20260903.1",
            "MCP_APP_NAME": "mcp-app",
            "ACA_JOB_NAME": "mcp-job",
            "AZURE_RESOURCE_GROUP": "rg-jobs",
            "AZURE_SUBSCRIPTION_ID": "sub-id",
            "ACR_NAME": "task13acr",
            "ACR_LOGIN_SERVER": "myregistry.azurecr.us",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": "https://storage.example.com",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME": "storage",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com:443/",
            "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME": "cosmos",
            "MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT": "true",
        }

    @staticmethod
    def _env_items(
        values: dict[str, str],
        *,
        mappings: bool = False,
    ) -> list[AcaEnvironmentVar] | list[dict[str, str]]:
        if mappings:
            return [{"name": name, "value": value} for name, value in values.items()]
        return [
            AcaEnvironmentVar({"name": name, "value": value})
            for name, value in values.items()
        ]

    @staticmethod
    def _policy_json(image: str, *, second_image: str | None = None) -> str:
        return json.dumps(
            {
                "jobs": {
                    "short-job": {"image_digest": image},
                    "second-job": {
                        "image_digest": second_image if second_image is not None else image
                    },
                }
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _frontmatter_and_body(path: pathlib.Path) -> tuple[dict[str, object], str]:
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        assert len(parts) == 3, path
        data = yaml.safe_load(parts[1])
        assert isinstance(data, dict), path
        return data, parts[2]

    @classmethod
    def _verify_deployment_client(
        cls,
        *,
        expected_image: str,
        app_identity_id: str = "app-id",
        job_identity_id: str = "job-id",
        app_env_overrides: dict[str, str] | None = None,
        job_env_overrides: dict[str, str] | None = None,
        app_image: str | None = None,
        job_image: str | None = None,
        app_command: list[str] | None = None,
        job_command: list[str] | None = None,
        mapping_env: bool = False,
    ) -> SimpleNamespace:
        app_env = {
            "MCP_ACA_JOBS_AUTH_MODE": "aca-easy-auth",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": "https://storage.example.com",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME": "storage",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com:443/",
            "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME": "cosmos",
            "MCP_ACA_JOBS_CALLBACK_CONTAINER_URL": "https://storage.example.com/outputs-callbacks",
            "MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID": "job-principal-id",
            "MCP_ACA_JOBS_POLICY_JSON": cls._policy_json(expected_image),
        }
        if app_env_overrides:
            app_env.update(app_env_overrides)

        job_env = {
            "MCP_ACA_JOBS_JOB_TYPE": "short-job",
            "MCP_ACA_JOBS_CALLBACK_AUTH_MODE": "managed_identity",
            "MCP_ACA_JOBS_CALLBACK_URL": "https://mcp-app.example.com/callbacks/jobs",
            "MCP_ACA_JOBS_INPUT_HOSTS": "input.example.com",
            "MCP_ACA_JOBS_OUTPUT_CONTAINER_URL": "https://storage.example.com/outputs",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": "https://storage.example.com",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME": "storage",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com:443/",
            "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME": "cosmos",
            "MCP_ACA_JOBS_COSMOS_DATABASE": "jobs",
            "MCP_ACA_JOBS_COSMOS_CONTAINER": "tasks",
            "MCP_ACA_JOBS_RESULT_HOSTS": "results.example.com,storage.example.com",
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": expected_image,
        }
        if job_env_overrides:
            job_env.update(job_env_overrides)

        app = SimpleNamespace(
            identity=SimpleNamespace(type="UserAssigned", userAssignedIdentities={app_identity_id: {}}),
            properties=SimpleNamespace(
                configuration=SimpleNamespace(
                    ingress=SimpleNamespace(external=True, targetPort=8080, transport="http", allowInsecure=False),
                    registries=[],
                    secrets=[],
                    activeRevisionsMode="Single",
                ),
                template=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            name="mcp",
                            image=app_image or expected_image,
                            command=app_command or ["python", "-m", "app.mcp_server"],
                            env=cls._env_items(app_env, mappings=mapping_env),
                            secrets=[SimpleNamespace(name="APP_SECRET")],
                        )
                    ]
                ),
            ),
        )
        job = SimpleNamespace(
            identity=SimpleNamespace(type="UserAssigned", userAssignedIdentities={job_identity_id: {}}),
            properties=SimpleNamespace(
                configuration=SimpleNamespace(
                    triggerType="Manual",
                    registries=[],
                    secrets=[],
                ),
                template=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            name="job",
                            image=job_image or expected_image,
                            command=job_command or ["python", "-m", "app.job_worker"],
                            env=cls._env_items(job_env, mappings=mapping_env),
                            secrets=[SimpleNamespace(name="JOB_SECRET")],
                        )
                    ]
                ),
            ),
        )
        auth_config = SimpleNamespace(
            properties=SimpleNamespace(
                platform=SimpleNamespace(enabled=True),
                globalValidation=SimpleNamespace(unauthenticatedClientAction="Return401"),
                identityProviders=SimpleNamespace(
                    azureActiveDirectory=SimpleNamespace(
                        enabled=True,
                        registration=SimpleNamespace(clientId="auth-client-id"),
                        validation=SimpleNamespace(
                            allowedAudiences=["api://auth-client-id", "auth-client-id"],
                        ),
                    )
                ),
            )
        )
        return SimpleNamespace(
            container_apps=SimpleNamespace(get=lambda resource_group, name: app),
            jobs=SimpleNamespace(get=lambda resource_group, name: job),
            container_apps_auth_configs=SimpleNamespace(get=lambda resource_group, app_name, auth_name: auth_config),
        )

    @staticmethod
    def _extract_bicep_block(text: str, marker: str) -> str:
        start = text.index(marker)
        open_brace = text.index("{", start)
        depth = 0
        for index in range(open_brace, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        raise AssertionError(f"unterminated Bicep block for {marker!r}")

    @staticmethod
    def _param_names(text: str) -> list[str]:
        return re.findall(r"(?m)^\s*param\s+(\w+)\s+\w+", text)

    @staticmethod
    def _allowlist_assertions_accept(
        client_ids: list[str], principal_ids: list[str]
    ) -> bool:
        exactly_one_mode = bool(client_ids) != bool(principal_ids)
        client_values_are_nonempty = all(value.strip() for value in client_ids)
        principal_values_are_nonempty = all(value.strip() for value in principal_ids)
        return (
            exactly_one_mode
            and client_values_are_nonempty
            and principal_values_are_nonempty
        )

    def _build_bicepparam(self, name: str, contents: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object] | None]:
        param_file = self._infra_dir() / name
        output_file = param_file.with_suffix(".json")
        param_file.write_text(contents, encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    "az",
                    "bicep",
                    "build-params",
                    "--file",
                    str(param_file),
                    "--outfile",
                    str(output_file),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            compiled = json.loads(output_file.read_text(encoding="utf-8")) if output_file.exists() else None
            return result, compiled
        finally:
            param_file.unlink(missing_ok=True)
            output_file.unlink(missing_ok=True)

    @staticmethod
    def _template_dir() -> pathlib.Path:
        return SKILL / "templates"

    @staticmethod
    def _infra_dir() -> pathlib.Path:
        return SKILL / "templates" / "infra"

    @staticmethod
    def _reference_app_dir() -> pathlib.Path:
        return SKILL / "references" / "python" / "app"

    @staticmethod
    def _script_dir() -> pathlib.Path:
        return SKILL / "templates" / "infra" / "scripts"

    @classmethod
    def _load_script(cls, filename: str, module_name: str):
        path = cls._script_dir() / filename
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec is not None and spec.loader is not None, path
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _docker_blocker_excerpt(output: str) -> str | None:
        lower = output.lower()
        daemon_markers = (
            "failed to connect to the docker api",
            "cannot connect to the docker daemon",
            "is the docker daemon running",
            "error during connect",
            "docker daemon is not running",
            "docker.sock",
        )
        if any(marker in lower for marker in daemon_markers):
            excerpt = [
                line
                for line in output.splitlines()
                if any(token in line.lower() for token in daemon_markers)
            ]
            body = "\n".join(excerpt[:20]) if excerpt else output.strip()
            return "docker-daemon\n" + body
        package_markers = (
            "no matching distribution found",
            "could not find a version that satisfies the requirement",
            "could not find any versions that satisfy the requirement",
        )
        if any(marker in lower for marker in package_markers):
            return None
        if os.getenv("ALLOW_NETWORK_DOCKER_SKIP") != "1":
            return None
        transport_markers = (
            "temporary failure in name resolution",
            "name resolution",
            "connection timed out",
            "read timeout",
            "ssl:",
            "certificate verify failed",
            "tlsv1",
            "tls handshake eof",
            "server certificate verification failed",
        )
        if not any(marker in lower for marker in transport_markers):
            return None
        excerpt = [
            line
            for line in output.splitlines()
            if any(token in line.lower() for token in transport_markers)
        ]
        body = "\n".join(excerpt[:20]) if excerpt else output.strip()
        return "docker-network\n" + body

    def test_pyproject_dependencies_match_canonical_stack(self) -> None:
        template = self._template_dir() / "pyproject.toml"
        pyproject = tomllib.loads(template.read_text(encoding="utf-8"))
        self.assertEqual(pyproject["build-system"]["requires"], ["hatchling"])
        self.assertEqual(pyproject["build-system"]["build-backend"], "hatchling.build")
        self.assertEqual(pyproject["project"]["name"], "foundry-mcp-aca-jobs-example")
        self.assertEqual(pyproject["project"]["version"], "1.0.0")
        self.assertEqual(pyproject["project"]["requires-python"], ">=3.12")
        self.assertEqual(pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"], ["app"])
        self.assertEqual(
            pyproject["project"]["dependencies"],
            [
                "fastmcp~=4.0.1",
                "fastmcp-tasks~=4.0.1",
                "mcp~=2.1.1",
                "azure-cosmos[aio]~=4.16.4",
                "azure-identity~=1.25.3",
                "azure-keyvault-secrets~=4.11.2",
                "azure-mgmt-appcontainers~=5.0.0",
                "azure-monitor-opentelemetry~=1.8.9",
                "azure-storage-blob[aio]~=12.30.1",
                "httpx~=0.28.1",
                "pydantic~=2.13.5",
                "uvicorn~=0.52.4",
            ],
        )
        self.assertEqual(
            pyproject["dependency-groups"]["fixture"],
            [
                "azure-ai-projects~=2.3.0",
            ],
        )
        self.assertTrue((self._template_dir() / "uv.lock").is_file())

    def test_skill_frontmatter_and_section_map_match_contract(self) -> None:
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        skill_fm, body = self._frontmatter_and_body(SKILL / "SKILL.md")
        headings = [(len(match.group(1)), match.group(2)) for match in re.finditer(r"(?m)^(#{2,3}) (.+)$", body)]

        self.assertEqual(skill_fm["name"], "foundry-mcp-aca-jobs")
        self.assertEqual(skill_fm["metadata"]["version"], "1.3.4")
        self.assertGreaterEqual(len(skill_fm["description"]), 200)
        self.assertLessEqual(len(skill_fm["description"]), 1024)
        self.assertRegex(skill_text, r"(?m)^# Foundry MCP ACA Jobs$")
        self.assertEqual(
            headings,
            [
                (2, "When to use this skill"),
                (2, "Architecture and shared-image contract"),
                (2, "Protocol contract"),
                (3, "Standards-first MCP Tasks path"),
                (3, "Compatibility tools"),
                (2, "Control record and lifecycle"),
                (2, "Idempotency and uncertain-start reconciliation"),
                (2, "Callback contract"),
                (2, "Security and least-privilege RBAC"),
                (2, "Deploy with azd"),
                (2, "Operate and observe"),
                (2, "Stable errors"),
                (2, "Test the implementation"),
                (2, "Non-goals"),
                (2, "Related skills"),
            ],
        )

        canonical_links = (
            "references/python/app/__init__.py",
            "references/python/app/aca_jobs.py",
            "references/python/app/aca_tasks_extension.py",
            "references/python/app/callbacks.py",
            "references/python/app/control_store.py",
            "references/python/app/job_worker.py",
            "references/python/app/mcp_server.py",
            "references/python/app/models.py",
            "references/python/app/orchestrator.py",
            "references/python/app/telemetry.py",
            "templates/Dockerfile",
            "templates/pyproject.toml",
            "templates/azure.yaml",
            "templates/infra/main.bicep",
            "templates/infra/app.bicep",
            "templates/infra/cosmos.bicep",
            "templates/infra/identity-rbac.bicep",
            "templates/infra/scripts/converge_image.py",
            "templates/infra/scripts/verify_deployment.py",
            "../azd-patterns/references/bicep/aca-job.bicep",
        )
        for rel_path in canonical_links:
            self.assertIn(f"[{rel_path}]({rel_path})", body)

        for required in (
            "MCP Tasks",
            "SEP-2663",
            "ACA Jobs",
            "durable result claims",
            "callbacks",
            "external job orchestration",
            "shared-image worker handoff",
            "Service Bus/queue/event-dispatch workflows",
            "TasksExtension",
            "docket_lifespan",
            "RESULT_REFERENCE_MISSING",
            "isError: true",
            "TASK_NOT_FOUND",
            "TASK_FORBIDDEN",
            "ARM_STATUS_UNAVAILABLE",
            "ARM_START_REJECTED",
            "ARM_STOP_REJECTED",
            "START_RECONCILIATION_EXHAUSTED",
            "ACA_EXECUTION_FAILED",
            "ACA_EXECUTION_STOPPED",
            "ACA_EXECUTION_STATE_UNRESOLVED",
            "CALLBACK_DELIVERY_REJECTED",
            "CALLBACK_DELIVERY_EXHAUSTED",
            "CALLBACK_PAYLOAD_CONFLICT",
            "CONTROL_STORE_UNAVAILABLE",
            "DEPLOYMENT_CONTRACT_MISMATCH",
            "WORKER_EXECUTION_FAILED",
            "foundry-prompt-agents",
        ):
            self.assertIn(required, skill_fm["description"] + "\n" + body)
        self.assertIn("[foundry-mcp-aca](../foundry-mcp-aca/SKILL.md)", body)
        self.assertNotIn("[foundry-mcp-aca-jobs](../foundry-mcp-aca-jobs/SKILL.md)", body)
        self.assertIn("[foundry-prompt-agents](../foundry-prompt-agents/SKILL.md)", body)
        compatibility = body.split("### Compatibility tools", 1)[1].split(
            "## Control record and lifecycle",
            1,
        )[0]
        for response_contract in (
            "`start_aca_job` returns exactly `taskId`, `jobType`, `status`, `acaExecutionId`, and `pollAfterMs`",
            "`get_aca_job_status` returns exactly `taskId`, `jobType`, `status`, `acaExecutionId`, `resultUrl`, `errorCode`, `createdAt`, and `updatedAt`",
            "`cancel_aca_job` returns exactly `taskId`, `status`, and `cancellationRequested`",
            "Never return the internal `TaskRecord`",
        ):
            self.assertIn(response_contract, compatibility)
        prompt_fm, _ = self._frontmatter_and_body(
            ROOT / "skills" / "foundry-prompt-agents" / "SKILL.md"
        )
        self.assertEqual(prompt_fm["metadata"]["version"], "1.1.9")

    def test_reference_headers_resolve_to_skill_sections(self) -> None:
        section_map = {
            self._reference_app_dir() / "__init__.py": ("../../../SKILL.md", 2, "Control record and lifecycle"),
            self._reference_app_dir() / "models.py": ("../../../SKILL.md", 2, "Control record and lifecycle"),
            self._reference_app_dir() / "callbacks.py": ("../../../SKILL.md", 2, "Callback contract"),
            self._reference_app_dir() / "control_store.py": ("../../../SKILL.md", 2, "Idempotency and uncertain-start reconciliation"),
            self._reference_app_dir() / "orchestrator.py": ("../../../SKILL.md", 2, "Idempotency and uncertain-start reconciliation"),
            self._reference_app_dir() / "aca_jobs.py": ("../../../SKILL.md", 2, "Architecture and shared-image contract"),
            self._reference_app_dir() / "aca_tasks_extension.py": ("../../../SKILL.md", 3, "Standards-first MCP Tasks path"),
            self._reference_app_dir() / "mcp_server.py": ("../../../SKILL.md", 2, "Protocol contract"),
            self._reference_app_dir() / "job_worker.py": ("../../../SKILL.md", 2, "Operate and observe"),
            self._reference_app_dir() / "telemetry.py": ("../../../SKILL.md", 2, "Operate and observe"),
            self._infra_dir() / "app.bicep": ("../../SKILL.md", 2, "Architecture and shared-image contract"),
            self._infra_dir() / "cosmos.bicep": ("../../SKILL.md", 2, "Control record and lifecycle"),
            self._infra_dir() / "identity-rbac.bicep": ("../../SKILL.md", 2, "Security and least-privilege RBAC"),
            self._infra_dir() / "identity-rbac" / "assignments.bicep": ("../../../SKILL.md", 2, "Security and least-privilege RBAC"),
            self._infra_dir() / "identity-rbac" / "job-operator.bicep": ("../../../SKILL.md", 2, "Security and least-privilege RBAC"),
            self._infra_dir() / "identity-rbac" / "uami.bicep": ("../../../SKILL.md", 2, "Security and least-privilege RBAC"),
            self._infra_dir() / "main.bicep": ("../../SKILL.md", 2, "Deploy with azd"),
            self._script_dir() / "converge_image.py": ("../../../SKILL.md", 2, "Deploy with azd"),
            self._script_dir() / "verify_deployment.py": ("../../../SKILL.md", 2, "Test the implementation"),
        }
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        skill_headings = {
            match.group(2): len(match.group(1))
            for match in re.finditer(r"(?m)^(#{2,3}) (.+)$", skill_text)
        }

        for path, (expected_relative_path, expected_level, expected_heading) in section_map.items():
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(expected_relative_path, text)
                self.assertIn(expected_heading, text)
                self.assertEqual(skill_headings[expected_heading], expected_level)

    def test_catalog_and_dependency_graph_include_new_skill(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        build_site = (ROOT / "scripts" / "build-site.py").read_text(encoding="utf-8")
        skill_deps = (ROOT / ".github" / "skill-deps.yml").read_text(encoding="utf-8")
        producer = (ROOT / "skills" / "foundry-mcp-aca" / "SKILL.md").read_text(encoding="utf-8")
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".github" / "plugin" / "marketplace.json").read_text(encoding="utf-8"))

        self.assertIn("foundry-mcp-aca-jobs", readme)
        self.assertIn("Install all 36 skills", readme)
        self.assertIn("skills-36-blue", readme)
        self.assertIn("foundry-mcp-aca-jobs", build_site)
        self.assertIn("foundry-mcp-aca-jobs:", skill_deps)
        self.assertIn("- foundry-mcp-aca", skill_deps)
        self.assertIn("foundry-mcp-aca-jobs", producer)
        self.assertIn("1.2.5", producer)
        self.assertIn("foundry-mcp-aca-jobs", plugin["description"])
        self.assertEqual(plugin["version"], "4.30.0")
        self.assertEqual(marketplace["metadata"]["version"], "4.30.0")
        self.assertEqual(marketplace["plugins"][0]["version"], "4.30.0")
        self.assertIn("foundry-mcp-aca-jobs", marketplace["metadata"]["description"])

    def test_catalog_readme_has_one_approved_adjacent_row(self) -> None:
        readme_lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        producer_row = next(
            index
            for index, line in enumerate(readme_lines)
            if line.startswith("| [**foundry-mcp-aca**]")
        )
        expected_row = (
            "| [**foundry-mcp-aca-jobs**](skills/foundry-mcp-aca-jobs/) | "
            "Expose durable MCP tools backed by pre-provisioned ACA Jobs — "
            "SEP-2663 Tasks, immediate fallback tools, Cosmos idempotency, "
            "managed-identity callbacks, and one immutable image with separate "
            "server/worker entrypoints. |"
        )

        self.assertEqual(
            sum(
                line.startswith("| [**foundry-mcp-aca-jobs**]")
                for line in readme_lines
            ),
            1,
        )
        self.assertEqual(readme_lines[producer_row + 1], expected_row)

    def test_build_site_category_places_jobs_skill_after_mcp_aca(self) -> None:
        module = ast.parse(
            (ROOT / "scripts" / "build-site.py").read_text(encoding="utf-8")
        )
        categories = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "CATEGORIES"
        )
        foundry_skills = categories["🏗️ Foundry Building Blocks"]
        producer_index = foundry_skills.index("foundry-mcp-aca")

        self.assertEqual(foundry_skills.count("foundry-mcp-aca-jobs"), 1)
        self.assertEqual(
            foundry_skills[producer_index + 1],
            "foundry-mcp-aca-jobs",
        )

    def test_catalog_manifests_and_agents_report_measured_totals(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".github" / "plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        skill_paths = list((ROOT / "skills").glob("*/SKILL.md"))
        pin_paths = list(
            (ROOT / "skills").glob("*/references/upstream-pin.md")
        )
        fixture_paths = list(
            (ROOT / "skills").glob("*/test-fixture/consumer_prompt.md")
        )
        pin_frontmatter = [
            self._frontmatter_and_body(path)[0] for path in pin_paths
        ]
        pins_by_skill = {
            path.parents[1].name: frontmatter
            for path, frontmatter in zip(pin_paths, pin_frontmatter, strict=True)
        }
        issue_only = sum(
            frontmatter["automation_tier"] == "issue_only"
            for frontmatter in pin_frontmatter
        )
        auto_tier = sum(
            frontmatter["automation_tier"] == "auto"
            for frontmatter in pin_frontmatter
        )

        self.assertEqual(
            (
                len(skill_paths),
                len(pin_paths),
                auto_tier,
                issue_only,
                len(skill_paths) - len(pin_paths),
                len(fixture_paths),
            ),
            (36, 32, 28, 4, 4, 22),
        )
        self.assertEqual(
            (
                pins_by_skill["foundry-agt"]["automation_tier"],
                pins_by_skill["foundry-agt"]["validation"]["runnable"],
            ),
            ("issue_only", True),
            "foundry-agt remains human-only even though its validation is runnable",
        )
        self.assertEqual(plugin["version"], "4.30.0")
        self.assertIn("36 reusable building blocks", plugin["description"])
        self.assertEqual(marketplace["metadata"]["version"], "4.30.0")
        self.assertIn("all 36 skills", marketplace["metadata"]["description"])
        self.assertEqual(marketplace["plugins"][0]["version"], "4.30.0")
        self.assertIn("36 reusable GBB skills", marketplace["plugins"][0]["description"])

        for expected in (
            "**Current coverage (36 skills, 32 with upstream pins):**",
            "| Auto-tier (CI can refresh autonomously) | 28 pins |",
            "| Issue-only (human / complex deploy) | 4 pins |",
            "| Internal IP (no pin) | 4 skills |",
            "| Copilot-CLI fixtures | 22 skills |",
            "| Total skills | 36 |",
            "| Skills with upstream pins | 32 |",
            "| Auto-tier (CI can refresh autonomously) | 28 |",
            "| Issue-only (human / complex deploy) | 4 |",
            "| Internal IP (no upstream) | 4 |",
        ):
            with self.subTest(expected=expected):
                self.assertTrue(
                    expected in agents,
                    f"AGENTS.md is missing measured catalog value: {expected}",
                )

        count_probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import unittest; "
                    "suite = unittest.defaultTestLoader.discover("
                    "'scripts/tests', pattern='test*.py'); "
                    "print(f'UNITTEST_CASE_COUNT={suite.countTestCases()}')"
                ),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        documented_unit_tests = re.search(
            r"^\| Unit tests \| (\d+) \|$",
            agents,
            flags=re.MULTILINE,
        )
        discovered_unit_tests = re.search(
            r"^UNITTEST_CASE_COUNT=(\d+)$",
            count_probe.stdout,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(documented_unit_tests)
        self.assertIsNotNone(discovered_unit_tests)
        self.assertEqual(
            int(documented_unit_tests.group(1)),
            int(discovered_unit_tests.group(1)),
        )

    def test_home_landing_renders_measured_skill_count(self) -> None:
        from scripts.site_templates import render_home

        skills = [{"name": f"skill-{index}"} for index in range(36)]
        landing = render_home({}, skills, [])

        self.assertTrue(
            "all 36 skills, or pick individual ones." in landing,
            "landing-page prose must derive its skill total from the skills list",
        )
        self.assertTrue(
            '<span class="browse-count" aria-label="Skills count">36</span>'
            in landing,
            "landing-page browse card must show the measured skills-list count",
        )
        self.assertFalse(
            "all 27 skills" in landing,
            "landing-page prose contains the stale hardcoded skill count",
        )

    def test_dependency_graph_matches_the_approved_four_skill_contract(self) -> None:
        deps = yaml.safe_load(
            (ROOT / ".github" / "skill-deps.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            deps["skills"]["foundry-mcp-aca-jobs"]["depends_on"],
            [
                "azd-patterns",
                "foundry-hosted-agents",
                "foundry-mcp-aca",
                "foundry-prompt-agents",
            ],
        )

    def test_fixture_workflow_maps_required_jobs_secrets_identically(self) -> None:
        workflow_path = ROOT / ".github" / "workflows" / "skill-test.yml"
        workflow_text = workflow_path.read_text(encoding="utf-8")
        workflow = yaml.safe_load(workflow_text)
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        fixture_steps = [
            step
            for step in steps
            if step.get("name", "").startswith("Run consumer prompt")
            or step.get("name", "").startswith("Retry")
        ]
        self.assertGreaterEqual(len(fixture_steps), 2)
        expected = {
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "${{ secrets.MCP_ACA_JOBS_COSMOS_ENDPOINT }}",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": "${{ secrets.MCP_ACA_JOBS_STORAGE_ACCOUNT_URL }}",
            "MCP_AUTH_APP_CLIENT_ID": "${{ secrets.MCP_AUTH_APP_CLIENT_ID }}",
        }
        extracted = [
            {name: step["env"].get(name) for name in expected}
            for step in fixture_steps
        ]
        self.assertEqual(extracted, [expected] * len(fixture_steps))
        self.assertEqual(
            workflow_text.count(
                "Required only for the foundry-mcp-aca-jobs fixture; other matrix"
            ),
            len(fixture_steps),
        )
        self.assertEqual(
            workflow_text.count(
                "Shared optional caller app client ID; foundry-mcp-aca-jobs"
            ),
            len(fixture_steps),
        )

    def test_relocated_template_layout_compiles_with_canonical_job_module(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'PROJECT_DIR="$SCRATCH_ROOT/skills/foundry-mcp-aca-jobs/templates"',
            fixture,
        )
        self.assertIn(
            'CANONICAL_JOB_DIR="$SCRATCH_ROOT/skills/azd-patterns/references/bicep"',
            fixture,
        )
        self.assertIn(
            'cp skills/azd-patterns/references/bicep/aca-job.bicep "$CANONICAL_JOB_DIR/aca-job.bicep"',
            fixture,
        )
        self.assertIn(
            'cp skills/foundry-mcp-aca-jobs/templates/bicepconfig.json "$PROJECT_DIR/bicepconfig.json"',
            fixture,
        )

        scratch = ROOT / ".scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="relocated-mcp-aca-jobs-", dir=scratch
        ) as directory:
            mirror = pathlib.Path(directory)
            relocated_template = (
                mirror / "skills" / "foundry-mcp-aca-jobs" / "templates"
            )
            relocated_job_dir = (
                mirror / "skills" / "azd-patterns" / "references" / "bicep"
            )
            shutil.copytree(self._template_dir(), relocated_template)
            self.assertEqual(
                json.loads(
                    (relocated_template / "bicepconfig.json").read_text(
                        encoding="utf-8"
                    )
                ),
                {"experimentalFeaturesEnabled": {"assertions": True}},
            )
            relocated_job_dir.mkdir(parents=True)
            shutil.copy2(
                ROOT
                / "skills"
                / "azd-patterns"
                / "references"
                / "bicep"
                / "aca-job.bicep",
                relocated_job_dir / "aca-job.bicep",
            )
            result = subprocess.run(
                [
                    "az",
                    "bicep",
                    "build",
                    "--file",
                    str(relocated_template / "infra" / "main.bicep"),
                    "--outfile",
                    str(mirror / "relocated-main.json"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_main_parameters_exactly_match_all_declared_main_params(self) -> None:
        main = (self._infra_dir() / "main.bicep").read_text(encoding="utf-8")
        declared = set(
            re.findall(
                r"(?m)^\s*param\s+([A-Za-z_][A-Za-z0-9_]*)\s+",
                main,
            )
        )
        parameters = json.loads(
            (self._infra_dir() / "main.parameters.json").read_text(
                encoding="utf-8"
            )
        )["parameters"]
        self.assertEqual(set(parameters), declared)

    def test_locks_use_only_hash_verified_registry_artifacts(self) -> None:
        tracked = subprocess.check_output(
            ["git", "ls-files", str(SKILL.relative_to(ROOT))],
            cwd=ROOT,
            text=True,
        ).splitlines()
        self.assertFalse(
            [
                path
                for path in tracked
                if ("/.wheelhouse/" in path or path.endswith(".whl"))
                and (ROOT / path).exists()
            ]
        )
        for lock_path in (
            self._template_dir() / "uv.lock",
            self._infra_dir() / "scripts" / "uv.lock",
        ):
            with self.subTest(lock=lock_path):
                lock = lock_path.read_text(encoding="utf-8")
                self.assertNotIn("exclude-newer", lock)
                self.assertNotIn(".wheelhouse", lock)
                self.assertNotIn("{ path =", lock)
                for line in lock.splitlines():
                    if "source = { registry =" in line:
                        self.assertIn("https://pypi.org/simple", line)
                    if "{ url =" in line:
                        self.assertIn('hash = "sha256:', line)

    def test_fixture_documents_standing_blob_role_without_regranting(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for text in (fixture, agents):
            self.assertIn("Storage Blob Data Contributor", text)
            self.assertIn("<ci-uami-name>", text)
            self.assertIn("<ci-storage-account>", text)
        prerequisite = fixture[
            fixture.index("Storage Blob Data Contributor")
            - 300 : fixture.index("Storage Blob Data Contributor")
            + 500
        ]
        self.assertIn("do not re-grant", prerequisite.lower())
        self.assertNotIn("az role assignment create", prerequisite)

    def test_agent_smokes_grade_actual_mcp_call_outputs(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            fixture.count(
                'getattr(item, "type", None) == "mcp_call"'
            ),
            2,
        )
        call_sets = re.findall(
            r'assert set\(calls_by_name\) == \{(.*?)\}, f"required MCP calls missing',
            fixture,
            re.S,
        )
        self.assertEqual(len(call_sets), 2)
        for call_set in call_sets:
            self.assertIn('"start_aca_job"', call_set)
            self.assertIn('"get_aca_job_status"', call_set)
        self.assertEqual(
            fixture.count('getattr(item, "error", None) in ('),
            2,
        )
        self.assertEqual(
            fixture.count("assert marker in str("),
            2,
        )
        self.assertNotIn('assert "start_aca_job" in evidence', fixture)
        self.assertNotIn('assert "get_aca_job_status" in evidence', fixture)

    def test_legacy_fallback_reads_public_status_field(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        fallback = fixture.split("    fallback = dict(request)", 1)[1].split(
            "    callback_url = (", 1
        )[0]

        self.assertEqual(fallback.count('cancelled["status"]'), 2)
        self.assertNotIn('cancelled["lifecycleState"]', fallback)

    def test_agent_smoke_input_refs_are_uploaded_before_invocation(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        upload_step = fixture.split(
            "## Step 4 — task-aware and fallback client smoke", 1
        )[1].split("## Step 5 — prompt agent smoke", 1)[0]
        self.assertIn("agent_input_refs = (", upload_step)
        for marker in (
            "PROMPT_AGENT_MCP_PASS",
            "HOSTED_AGENT_MCP_PASS",
        ):
            self.assertIn(
                f'f"{{storage_url}}/{{output_container}}/inputs/{marker}-"'
                "\n"
                "        f\"{os.environ['SUFFIX']}.json\"",
                upload_step,
            )
        self.assertIn("for agent_input_ref in agent_input_refs:", upload_step)
        self.assertIn(
            "agent_input_blob = BlobClient.from_blob_url(",
            upload_step,
        )
        self.assertIn(
            "await agent_input_blob.upload_blob(",
            upload_step,
        )

    def test_agent_smoke_retries_report_redacted_last_exception(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(fixture.count("last_error = None"), 2)
        self.assertEqual(
            fixture.count("last_error_repr = redact_error(repr(last_error))"),
            2,
        )
        self.assertEqual(
            fixture.count('assert response is not None, f"invoke never succeeded: {last_error_repr}"'),
            2,
        )
        self.assertEqual(fixture.count("last_error={last_error_repr}"), 6)
        self.assertIn("<redacted-bearer>", fixture)
        self.assertIn("<redacted-jwt>", fixture)

    def test_fixture_captures_and_checks_exact_deployment_verifier_markers(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('verifier_output="$(', fixture)
        self.assertIn(
            'grep -Fxq "SHARED_IMAGE_DIGEST_MATCH" <<<"$verifier_output"',
            fixture,
        )
        self.assertIn(
            'grep -Fxq "ENTRYPOINTS_MATCH" <<<"$verifier_output"',
            fixture,
        )

    def test_static_mcp_bearers_are_marked_smoke_only(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            fixture.count(
                "Static bearer is smoke-only; production must use a header provider."
            ),
            1,
        )
        self.assertIn(
            "Static bearer is smoke-only; production must use project_connection_id.",
            fixture,
        )

    def test_skill_canonical_tables_cover_deploy_inputs_without_self_link(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "For the companion itself, see [foundry-mcp-aca-jobs]",
            skill,
        )
        for path in (
            "templates/uv.lock",
            "templates/infra/main.parameters.json",
            "templates/infra/identity-rbac/assignments.bicep",
            "templates/infra/identity-rbac/job-operator.bicep",
            "templates/infra/identity-rbac/uami.bicep",
            "templates/infra/scripts/pyproject.toml",
            "templates/infra/scripts/uv.lock",
        ):
            with self.subTest(path=path):
                self.assertIn(f"[{path}]({path})", skill)
                self.assertIn(f"- `{path}`", skill)

    def test_skill_and_readme_document_self_contained_sibling_catalog_layout(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        readme = (SKILL / "README.md").read_text(encoding="utf-8")
        for text in (skill, readme):
            normalized = " ".join(text.split())
            self.assertIn(
                "requires the sibling catalog checkout layout",
                normalized,
            )
            self.assertIn(
                "skills/foundry-mcp-aca-jobs/templates/infra/main.bicep",
                text,
            )
            self.assertIn(
                "skills/azd-patterns/references/bicep/aca-job.bicep",
                text,
            )
            self.assertIn(
                "skills/foundry-mcp-aca-jobs/templates",
                text,
            )
            self.assertIn(
                'WORKDIR="<workdir>"',
                text,
            )
            self.assertIn(
                'cp -R skills/foundry-mcp-aca-jobs/templates "$WORKDIR/skills/foundry-mcp-aca-jobs/"',
                text,
            )
            self.assertIn(
                'cp skills/azd-patterns/references/bicep/aca-job.bicep "$WORKDIR/skills/azd-patterns/references/bicep/"',
                text,
            )
        self.assertIn(
            "Composition root; requires the sibling catalog checkout layout",
            skill,
        )

    def test_skill_and_readme_document_mutually_exclusive_easy_auth_modes(
        self,
    ) -> None:
        for path in (SKILL / "SKILL.md", SKILL / "README.md"):
            with self.subTest(path=path.name):
                normalized = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("client ID", normalized)
                self.assertIn("principal object ID", normalized)
                self.assertIn("mutually exclusive", normalized)
                self.assertIn("hosted", normalized.lower())
                self.assertNotIn(
                    "adding the principal ID alongside client IDs", normalized
                )

    def test_live_fixture_contract_requires_deterministic_bash_only_azure_smoke(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(encoding="utf-8")
        normalized = " ".join(fixture.split())
        marker = "/tmp/foundry-mcp-aca-jobs-smoke-result"
        shared_rg = "rg-awesome-gbb-ci"

        self.assertIn("## Step -1 — acknowledge the skill contract", fixture)
        self.assertIn('echo "skills/foundry-mcp-aca-jobs/SKILL.md"', fixture)
        self.assertIn("Do NOT browse the repository.", fixture)
        self.assertIn("never invoke `copilot` recursively", fixture)
        self.assertFalse((SKILL / "test-fixture" / "run_e2e.py").exists())
        self.assertIn(marker, fixture)
        self.assertNotIn(".foundry-mcp-aca-jobs-smoke-result", fixture)
        self.assertNotIn("do not use `/tmp`", fixture.lower())
        self.assertIn("## Step 0 — auth context", fixture)
        required_env = (
            "AZURE_CLIENT_ID",
            "AZURE_TENANT_ID",
            "AZURE_SUBSCRIPTION_ID",
            "ACR_LOGIN_SERVER",
            "FOUNDRY_PROJECT_ENDPOINT",
            "AZURE_AI_PROJECT_ID",
            "FOUNDRY_MODEL_DEPLOYMENT",
            "MCP_AUTH_APP_CLIENT_ID",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL",
        )
        for variable in required_env:
            self.assertIn(
                f"SMOKE_RESULT=FAIL missing {variable}",
                fixture,
                f"{variable} hard precondition needs a deterministic FAIL marker",
            )
        self.assertIn("brownfield Cosmos CI mode", normalized)
        self.assertIn("az account show --output table || echo", fixture)
        self.assertIn(
            "azd auth login \\\n  --federated-credential-provider github \\\n  --client-id \"$AZURE_CLIENT_ID\" \\\n  --tenant-id \"$AZURE_TENANT_ID\"",
            fixture,
        )
        self.assertIn("SMOKE_RESULT=FAIL azd auth login failed", fixture)
        self.assertIn("## Step 1 — goal and constraints", fixture)
        self.assertIn(".scratch/ci-smoke-mcp-jobs-", fixture)
        self.assertIn("uuidgen", fixture)
        self.assertIn("cut -c1-8", fixture)
        self.assertIn('CHILD_RG="rg-foundry-mcp-aca-jobs-ci-$SUFFIX"', fixture)
        self.assertIn('az group create --name "$CHILD_RG"', fixture)
        self.assertIn("--tags cleanup=true created-by=ci-smoke", fixture)
        self.assertIn('AZURE_RESOURCE_GROUP="$CHILD_RG"', fixture)
        self.assertIn('MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP="rg-awesome-gbb-ci"', fixture)
        self.assertNotIn(f'AZURE_RESOURCE_GROUP="{shared_rg}"', fixture)
        self.assertNotRegex(fixture, rf"azd (?:up|deploy|down)[^\n]*{shared_rg}")
        self.assertIn("No repository writes outside `.scratch/`.", fixture)
        self.assertIn("`uv`", fixture)
        self.assertIn("uv sync --frozen --group fixture", fixture)
        self.assertIn("uv run --frozen --group fixture python - <<'PY'", fixture)
        self.assertNotIn("pip install", fixture)
        self.assertIn("azd ext install microsoft.foundry", fixture)
        self.assertIn('select(.id == "microsoft.foundry")', fixture)
        self.assertIn('select(.id == "azure.ai.agents")', fixture)
        self.assertIn("RBAC_PROVIDER_ACTIONS_MATCH", fixture)
        self.assertIn(
            '.name? | select(type == "string") |\n'
            "     select(ascii_downcase == ($action | ascii_downcase))",
            fixture,
        )
        expected_provider_actions = (
            "Microsoft.App/jobs/read",
            "Microsoft.App/jobs/start/action",
            "Microsoft.App/jobs/execution/read",
            "Microsoft.App/jobs/executions/read",
            "Microsoft.App/jobs/stop/execution/action",
        )
        provider_loop = fixture.split("for action in \\", 1)[1].split(
            "echo RBAC_PROVIDER_ACTIONS_MATCH", 1
        )[0]
        self.assertEqual(
            re.findall(r"(?m)^  (Microsoft\.App/\S+)(?: \\)?$", provider_loop),
            list(expected_provider_actions),
        )
        for action in expected_provider_actions:
            self.assertIn(action, fixture)
        self.assertIn("SHARED_IMAGE_DIGEST_MATCH", fixture)
        self.assertIn("ENTRYPOINTS_MATCH", fixture)
        self.assertIn("from fastmcp_tasks.client import TasksClientExtension", fixture)
        self.assertIn("from fastmcp_tasks.client import call_tool_task", fixture)
        self.assertIn("extensions=[TasksClientExtension()]", fixture)
        self.assertIn("await task.wait(timeout=", fixture)
        self.assertIn("await task.result()", fixture)
        self.assertIn("await cancel_task.cancel()", fixture)
        self.assertIn("auth=access_token", fixture)
        self.assertIn("extensions=[]", fixture)
        self.assertIn('mode="legacy"', fixture)
        self.assertIn("resultType", fixture)
        self.assertIn("MCP_TASKS_COMPLETED", fixture)
        self.assertIn("FALLBACK_TOOLS_COMPLETED", fixture)
        self.assertIn("IDEMPOTENCY_DUPLICATE_SAME_TASK", fixture)
        self.assertIn("CALLBACK_PAYLOAD_VALID", fixture)
        self.assertIn("CANCELLATION_TERMINAL", fixture)
        self.assertIn("from azure.ai.projects.models import MCPTool, PromptAgentDefinition", fixture)
        self.assertIn("definition=PromptAgentDefinition(", fixture)
        self.assertIn("MCPTool(", fixture)
        self.assertIn("authorization=access_token", fixture)
        self.assertEqual(
            fixture.count('headers={"Authorization": "Bearer " + access_token}'),
            1,
        )
        self.assertNotIn('headers={"Authorization": f"Bearer {access_token}"}', fixture)
        self.assertIn("project.agents.create_version(", fixture)
        self.assertIn("openai.conversations.create()", fixture)
        self.assertIn("openai.responses.create(", fixture)
        self.assertIn("project.agents.delete_version(", fixture)
        self.assertIn("from agent_framework.foundry import FoundryChatClient", fixture)
        self.assertIn("from azure.identity import DefaultAzureCredential", fixture)
        self.assertIn(
            "from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential",
            fixture,
        )
        self.assertIn(
            "from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential",
            fixture,
        )
        self.assertIn("token_credential = SyncDefaultAzureCredential()", fixture)
        self.assertIn("credential=AsyncDefaultAzureCredential()", fixture)
        self.assertIn("token_credential.get_token(", fixture)
        self.assertIn('os.environ["MCP_AUTH_AUDIENCE"]', fixture)
        self.assertIn("client.get_mcp_tool(", fixture)
        self.assertIn('approval_mode="never_require"', fixture)
        self.assertIn("ResponsesHostServer", fixture)
        self.assertNotIn("MCP_BEARER_TOKEN", fixture)
        self.assertNotRegex(fixture, r"(?m)^[^#\n]*(?:TOKEN|access_token)=[^=\n]*>>.*\\.azure")
        self.assertIn("PROMPT_AGENT_MCP_PASS", fixture)
        self.assertIn("HOSTED_AGENT_MCP_PASS", fixture)
        self.assertIn("exact four fields", normalized)
        self.assertIn("best-effort targeted cleanup", fixture)
        self.assertIn("marker-first", normalized)
        self.assertIn("## Step 2 — deterministic scaffold", fixture)
        self.assertIn("## Step 3 — provider and build verification", fixture)
        self.assertIn("## Step 4 — task-aware and fallback client smoke", fixture)
        self.assertIn("## Step 5 — prompt agent smoke", fixture)
        self.assertIn("## Step 6 — hosted agent smoke", fixture)
        self.assertIn("## Step 7 — marker-first teardown", fixture)
        pass_write = f"printf 'SMOKE_RESULT=PASS\\n' > {marker}"
        self.assertIn(pass_write, fixture)
        self.assertIn('rm -rf "$SCRATCH_ROOT"', fixture)
        self.assertLess(fixture.index(pass_write), fixture.index('rm -rf "$SCRATCH_ROOT"'))
        self.assertNotIn("az account get-access-token", fixture)
        self.assertNotIn("az deployment", fixture)
        self.assertNotIn("az containerapp create", fixture)

        python_heredocs = re.findall(
            r"(?:uv run --frozen --group fixture python -|cat > \"\\$HOSTED_DIR/container\\.py\") <<'PY'\n(.*?)\nPY",
            fixture,
            re.S,
        )
        self.assertGreaterEqual(len(python_heredocs), 3)
        for index, source in enumerate(python_heredocs):
            compile(source, f"<consumer_prompt heredoc {index}>", "exec")

    def test_hosted_agent_instance_identity_is_added_to_easy_auth_allowlist(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(fixture.split())
        compact = re.sub(r"\s+", "", fixture)
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn('print("HOSTED_AGENT_ACTIVE")', fixture)
        self.assertIn(
            '--url "${FOUNDRY_PROJECT_ENDPOINT%/}/agents/${HOSTED_NAME}?api-version=v1"',
            fixture,
        )
        self.assertIn("--resource https://ai.azure.com", fixture)
        self.assertIn("--output json", fixture)
        self.assertIn(".instance_identity.principal_id", fixture)
        self.assertIn(".versions.latest.instance_identity.principal_id", fixture)
        self.assertIn("for attempt in $(seq 1 6); do", fixture)
        self.assertIn("HOSTED_IDENTITY_LAST_ERROR", fixture)
        self.assertIn('sleep 10', fixture)
        self.assertIn('test -n "$HOSTED_PRINCIPAL_ID"', fixture)
        self.assertIn(
            'resourceGroups/${CHILD_RG}/providers/Microsoft.App/containerApps/${APP_NAME}/authConfigs/current?api-version=2025-01-01',
            fixture,
        )
        self.assertIn('AUTH_CONFIG_PROPERTIES="$(', fixture)
        self.assertIn(
            re.sub(
                r"\s+",
                "",
                ".identityProviders.azureActiveDirectory.validation."
                "defaultAuthorizationPolicy.allowedPrincipals.identities",
            ),
            compact,
        )
        self.assertIn("index($principal_id)", fixture)
        self.assertNotIn("| unique", fixture)
        for initializer in (
            "(.identityProviders //= {})",
            "(.identityProviders.azureActiveDirectory //= {})",
            "(.identityProviders.azureActiveDirectory.validation //= {})",
            "(.identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy //= {})",
            "(.identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy.allowedPrincipals //= {})",
            "(.identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy.allowedPrincipals.identities //= [])",
        ):
            self.assertIn(re.sub(r"\s+", "", initializer), compact)
        self.assertIn("| {properties: .}", fixture)
        self.assertIn("--method put", fixture)
        self.assertIn('--body "$UPDATED_AUTH_CONFIG_BODY"', fixture)
        self.assertIn("for attempt in $(seq 1 12); do", fixture)
        self.assertIn('sleep 5', fixture)
        self.assertIn(
            "--query properties.identityProviders.azureActiveDirectory."
            "validation.defaultAuthorizationPolicy",
            normalized,
        )
        self.assertIn("(.allowedApplications? == null)", fixture)
        self.assertIn(
            "hosted agent identity lookup failed after 6 attempts: $HOSTED_IDENTITY_LAST_ERROR",
            fixture,
        )
        self.assertIn(
            "Easy Auth configuration read failed",
            fixture,
        )
        self.assertIn(
            "Easy Auth allowed principal identities update failed",
            fixture,
        )
        self.assertIn(
            "hosted agent principal object ID missing from Easy Auth allowed principal identities after bounded poll",
            fixture,
        )
        self.assertNotIn('echo "$HOSTED_PRINCIPAL_ID"', fixture)
        for forbidden in (
            "az ad sp show",
            "--query appId",
            "Microsoft Graph",
            "Application.Read.All",
            "Directory.Read.All",
            "ServicePrincipal.Read.All",
        ):
            self.assertNotIn(forbidden, fixture)
        self.assertIn(
            "Post-deploy hosted-agent callers use principal object ID mode",
            skill,
        )
        self.assertIn(
            "defaultAuthorizationPolicy.allowedPrincipals.identities", skill
        )

        deploy = fixture.index('azd deploy "$HOSTED_NAME"')
        active = fixture.index('print("HOSTED_AGENT_ACTIVE")')
        identity = fixture.index(".instance_identity.principal_id")
        update = fixture.index("--method put", identity)
        restart = fixture.index(
            'az containerapp revision restart --resource-group "$CHILD_RG" '
            '--name "$APP_NAME" --revision "$revision"',
            update,
        )
        invoke = fixture.index("project.agents.update_details(", update)
        self.assertLess(deploy, active)
        self.assertLess(active, identity)
        self.assertLess(identity, update)
        self.assertLess(update, restart)
        self.assertLess(restart, invoke)

        identity_assignment = fixture.index('if HOSTED_PRINCIPAL_ID="$(')
        identity_filter_start = (
            fixture.index("jq -er '", identity_assignment) + len("jq -er '")
        )
        identity_filter_end = fixture.index(
            '\' <<<"$HOSTED_IDENTITY_RESPONSE"', identity_filter_start
        )
        identity_filter = fixture[identity_filter_start:identity_filter_end]
        for response_shape in (
            {"instance_identity": {"principal_id": "hosted-principal-object-id"}},
            {
                "versions": {
                    "latest": {
                        "instance_identity": {
                            "principal_id": "hosted-principal-object-id"
                        }
                    }
                }
            },
            {
                "instance_identity": {"principal_id": ""},
                "versions": {
                    "latest": {
                        "instance_identity": {
                            "principal_id": "hosted-principal-object-id"
                        }
                    }
                },
            },
        ):
            with self.subTest(response_shape=response_shape):
                parsed = subprocess.run(
                    ["jq", "-er", identity_filter],
                    input=json.dumps(response_shape),
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                self.assertEqual(
                    parsed.stdout.strip(), "hosted-principal-object-id"
                )

        jq_program_match = re.search(
            r"UPDATED_AUTH_CONFIG_BODY=\"\$\(.*?"
            r"jq -c --arg principal_id \"\$HOSTED_PRINCIPAL_ID\" '"
            r"(?P<program>.*?)"
            r"'\s+<<<\"\$AUTH_CONFIG_PROPERTIES\"",
            fixture,
            re.S,
        )
        self.assertIsNotNone(jq_program_match)
        original_properties = {
            "platform": {"enabled": True},
            "globalValidation": {"unauthenticatedClientAction": "Return401"},
            "identityProviders": {
                "azureActiveDirectory": {
                    "registration": {"clientId": "resource-app-client"},
                    "validation": {
                        "allowedAudiences": ["api://resource-app-client"],
                        "defaultAuthorizationPolicy": {
                            "allowedApplications": [
                                "existing-caller-client",
                                "hosted-caller-client",
                            ],
                            "allowedPrincipals": {
                                "identities": [
                                    "ci-uami-principal-object-id",
                                    "job-uami-principal-object-id",
                                ]
                            },
                        },
                    },
                }
            },
            "sentinel": {"mustRemain": ["full", "properties", "object"]},
        }
        transformed = subprocess.run(
            [
                "jq",
                "-c",
                "--arg",
                "principal_id",
                "hosted-principal-object-id",
                jq_program_match.group("program"),
            ],
            input=json.dumps(original_properties),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(transformed.returncode, 0, transformed.stderr)
        updated_body = json.loads(transformed.stdout)
        self.assertEqual(
            updated_body["properties"]["sentinel"],
            original_properties["sentinel"],
        )
        policy = updated_body["properties"]["identityProviders"][
            "azureActiveDirectory"
        ]["validation"]["defaultAuthorizationPolicy"]
        self.assertNotIn("allowedApplications", policy)
        self.assertEqual(
            policy["allowedPrincipals"]["identities"],
            [
                "ci-uami-principal-object-id",
                "job-uami-principal-object-id",
                "hosted-principal-object-id",
            ],
        )
        transformed_again = subprocess.run(
            [
                "jq",
                "-c",
                "--arg",
                "principal_id",
                "hosted-principal-object-id",
                jq_program_match.group("program"),
            ],
            input=json.dumps(updated_body["properties"]),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(transformed_again.returncode, 0, transformed_again.stderr)
        self.assertEqual(
            json.loads(transformed_again.stdout)["properties"][
                "identityProviders"
            ]["azureActiveDirectory"]["validation"]["defaultAuthorizationPolicy"][
                "allowedPrincipals"
            ]["identities"],
            [
                "ci-uami-principal-object-id",
                "job-uami-principal-object-id",
                "hosted-principal-object-id",
            ],
        )

    def test_fixture_resolves_ci_uami_principal_through_arm_before_single_azd_up(
        self,
    ) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(fixture.split())
        parameters = json.loads(
            (self._infra_dir() / "main.parameters.json").read_text(encoding="utf-8")
        )["parameters"]

        self.assertEqual(parameters["allowedMcpCallerClientIds"]["value"], [])
        self.assertEqual(
            parameters["allowedMcpCallerPrincipalIds"]["value"],
            ["${MCP_ACA_JOBS_CALLER_PRINCIPAL_ID}"],
        )
        self.assertIn("az identity list", fixture)
        self.assertIn(
            "--query \"[?clientId=='$AZURE_CLIENT_ID'].principalId\"",
            fixture,
        )
        self.assertNotIn("az resource list", fixture)
        self.assertNotIn("properties.clientId", fixture)
        self.assertIn('MCP_ACA_JOBS_CALLER_PRINCIPAL_ID="$(', fixture)
        self.assertIn(
            'MCP_ACA_JOBS_CALLER_PRINCIPAL_ID="$MCP_ACA_JOBS_CALLER_PRINCIPAL_ID"',
            fixture,
        )
        self.assertNotIn('echo "$MCP_ACA_JOBS_CALLER_PRINCIPAL_ID"', fixture)
        self.assertEqual(fixture.count("azd up --no-prompt"), 1)
        self.assertLess(
            fixture.index("az identity list"),
            fixture.index("azd up --no-prompt"),
        )
        for forbidden in (
            "az ad sp show",
            "Application.Read.All",
            "Directory.Read.All",
            "ServicePrincipal.Read.All",
        ):
            self.assertNotIn(forbidden, fixture)

    def test_fixture_restarts_active_revisions_after_auth_put_before_invoke(
        self,
    ) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        update = fixture.index("--method put")
        convergence = fixture.index("AUTH_ALLOWLIST_CONVERGED", update)
        restart = fixture.index(
            'az containerapp revision restart --resource-group "$CHILD_RG" '
            '--name "$APP_NAME" --revision "$revision"',
            convergence,
        )
        invoke = fixture.index("project.agents.update_details(", restart)

        self.assertIn("az containerapp revision list", fixture)
        self.assertIn("[?properties.active].name", fixture)
        self.assertIn("for attempt in $(seq 1 6); do", fixture[convergence:invoke])
        self.assertIn("active Container App revision restart failed", fixture)
        self.assertLess(update, convergence)
        self.assertLess(convergence, restart)
        self.assertLess(restart, invoke)

    def test_copilot_cli_matrix_timeout_covers_longest_task15_leg(self) -> None:
        workflow_text = (
            ROOT / ".github" / "workflows" / "skill-test.yml"
        ).read_text(encoding="utf-8")
        workflow = yaml.safe_load(workflow_text)
        matrix = workflow["jobs"]["copilot-cli-matrix"]

        self.assertEqual(matrix["timeout-minutes"], 120)
        self.assertIn(
            "- name: Retry once on classified-transient failure", workflow_text
        )
        self.assertIn("COOLDOWN=$((90 + RANDOM % 90))", workflow_text)
        for phrase in (
            "Primary Task15 P99",
            "Pattern 19 cooldown",
            "Retry Task15 P99",
            "teardown",
            "COMPOUND BUDGET",
            "Pattern 14",
        ):
            self.assertIn(phrase, workflow_text)

    def test_fixture_workflow_installs_pinned_uv(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "skill-test.yml").read_text(encoding="utf-8")
        self.assertIn("uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9", workflow)
        self.assertIn('version: "0.12.6"', workflow)

    def test_azd_parameters_bind_every_brownfield_value(self) -> None:
        parameters = (
            self._infra_dir() / "main.parameters.json"
        ).read_text(encoding="utf-8")

        for binding in (
            "${AZURE_RESOURCE_GROUP}",
            "${AZURE_LOCATION}",
            "${ACR_NAME}",
            "${MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP}",
            "${MCP_ACA_JOBS_ENVIRONMENT_NAME}",
            "${MCP_ACA_JOBS_APP_NAME}",
            "${MCP_ACA_JOBS_JOB_NAME}",
            "${MCP_ACA_JOBS_STORAGE_ACCOUNT_URL}",
            "${MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME}",
            "${MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME}",
            "${MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME}",
            "${MCP_ACA_JOBS_COSMOS_DATABASE}",
            "${MCP_ACA_JOBS_COSMOS_CONTAINER}",
            "${MCP_AUTH_APP_CLIENT_ID}",
            "${MCP_ACA_JOBS_CALLER_PRINCIPAL_ID}",
        ):
            self.assertIn(binding, parameters)
        parsed = json.loads(parameters)
        self.assertNotIn("expectedSubscriptionId", parsed["parameters"])
        self.assertNotIn("expectedTenantId", parsed["parameters"])
        self.assertFalse(
            parsed["parameters"]["cosmosUseExistingAccount"]["value"],
            "ordinary consumer default must provision a new Cosmos account",
        )
        main_bicep = (self._infra_dir() / "main.bicep").read_text(encoding="utf-8")
        self.assertIn("param platformResourceGroupName string = resourceGroupName", main_bicep)
        self.assertIn("scope: resourceGroup(platformResourceGroupName)", main_bicep)
        self.assertIn(
            "scope: resourceGroup(cosmosUseExistingAccount ? platformResourceGroupName : resourceGroupName)",
            main_bicep,
        )
        self.assertIn("module preRuntimeCosmosRbac", main_bicep)
        self.assertIn(
            "scope: resourceGroup(cosmosUseExistingAccount ? platformResourceGroupName : resourceGroupName)",
            main_bicep,
        )
        assignments = (
            self._infra_dir() / "identity-rbac" / "assignments.bicep"
        ).read_text(encoding="utf-8")
        self.assertIn("param createPlatformAssignments bool = true", assignments)
        self.assertIn("param createCosmosAssignments bool = true", assignments)
        callback = parsed["parameters"]["callbackConfig"]["value"]
        self.assertEqual(
            callback,
            {
                "authMode": "managed_identity",
            },
        )

    def test_upstream_pin_and_validation_contract_match_pyproject(self) -> None:
        pin_fm, body = self._frontmatter_and_body(SKILL / "references" / "upstream-pin.md")
        pyproject = tomllib.loads((self._template_dir() / "pyproject.toml").read_text(encoding="utf-8"))
        expected = [
            *pyproject["project"]["dependencies"],
            *pyproject["dependency-groups"]["fixture"],
        ]

        self.assertEqual(pin_fm["schema_version"], 2)
        self.assertEqual(pin_fm["freshness_tier"], "B")
        self.assertEqual(pin_fm["automation_tier"], "auto")
        self.assertEqual(pin_fm["validation"]["requires"], ["pypi"])
        self.assertTrue(pin_fm["validation"]["runnable"])
        self.assertEqual(len(pin_fm["packages"]), 13)

        normalized_expected = []
        for dep in expected:
            package, version = dep.split("~=", 1)
            normalized_expected.append((package.replace("[aio]", ""), version))
        actual = [(pkg["name"], pkg["version"]) for pkg in pin_fm["packages"]]
        self.assertEqual(actual, normalized_expected)

        script = pin_fm["validation"]["script"]
        for dep in expected:
            self.assertIn(f'"{dep}"', script)
        self.assertEqual(
            pin_fm["validation"]["expected_output"],
            [
                "ok fastmcp external tasks adapter",
                "ok aca jobs sdk surface",
                "ok azure ai projects prompt mcp authorization surface",
                "ok foundry-mcp-aca-jobs imports",
            ],
        )
        self.assertIn("prefecthq/fastmcp/issues/2754".lower(), str(pin_fm["known_issues"][0]["upstream_url"]).lower())
        self.assertIn("from fastmcp_tasks import TasksExtension", script)
        self.assertIn("inspect.getsource(TasksExtension.lifespan)", script)
        self.assertIn('assert "docket_lifespan" in tasks_source', script)
        self.assertIn('assert "docket_lifespan" not in aca_source', script)
        self.assertIn("AcaTasksExtension", script)
        self.assertIn("JobsOperations", script)
        self.assertIn("TasksExtension", script)
        self.assertIn("docket_lifespan", script)
        projects_package = next(
            package
            for package in pin_fm["packages"]
            if package["name"] == "azure-ai-projects"
        )
        self.assertEqual(projects_package["version"], "2.3.0")
        self.assertEqual(
            projects_package["upstream_changelog"],
            "https://pypi.org/project/azure-ai-projects/#history",
        )
        self.assertIn(
            "https://pypi.org/project/azure-ai-projects/",
            pin_fm["docs_to_revalidate"],
        )
        self.assertIn(
            "https://learn.microsoft.com/python/api/azure-ai-projects/azure.ai.projects.models.mcptool",
            pin_fm["docs_to_revalidate"],
        )
        self.assertIn(
            "https://learn.microsoft.com/python/api/azure-ai-projects/azure.ai.projects.models.promptagentdefinition",
            pin_fm["docs_to_revalidate"],
        )
        self.assertIn(
            "from azure.ai.projects.models import MCPTool, PromptAgentDefinition",
            script,
        )
        self.assertIn(
            'authorization="task20-token"',
            script,
        )
        self.assertIn(
            'assert prompt_definition.tools[0].authorization == "task20-token"',
            script,
        )
        self.assertIn(
            'print("ok azure ai projects prompt mcp authorization surface")',
            script,
        )
        self.assertIn(
            "| `azure-ai-projects` | PyPI | **2.3.0** |",
            body,
        )
        self.assertIn("Task20", body)

    def test_pattern25_assigns_manual_cosmos_native_role_cleanup(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        janitor = agents.split("**Janitor contract.**", 1)[1].split(
            "**Diagnostic protocol.**", 1
        )[0]

        self.assertIn(
            "- Cosmos native SQL role assignments (`az cosmosdb sql role assignment`)",
            janitor,
        )
        self.assertIn("manual", janitor.lower())
        self.assertIn("deleted principals", janitor)

    def test_validation_script_uses_concrete_imports_and_compiles(self) -> None:
        pin_fm, _ = self._frontmatter_and_body(SKILL / "references" / "upstream-pin.md")
        script = pin_fm["validation"]["script"]

        self.assertIn('REPO_ROOT="${PIN_VALIDATION_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"', script)
        self.assertIn('git -C "$REPO_ROOT" rev-parse --is-inside-work-tree', script)
        self.assertIn(
            "could not determine repository root; set PIN_VALIDATION_REPO_ROOT or run this validation from inside the awesome-gbb git repository.",
            script,
        )
        self.assertIn(
            'export PYTHONPATH="$REPO_ROOT/skills/foundry-mcp-aca-jobs/references/python${PYTHONPATH:+:$PYTHONPATH}"',
            script,
        )
        self.assertIn("from azure.mgmt.appcontainers.operations import JobsOperations, JobsExecutionsOperations", script)
        self.assertNotIn("JobExecutionsOperations", script)
        self.assertNotIn("from app import (", script)
        for required in (
            "from app.callbacks import AsyncTokenCredential, CallbackSender, callback_payload",
            "from app.aca_jobs import AcaExecution, AcaJobsAdapter, AcaJobsClient",
            "from app.aca_tasks_extension import AcaTasksExtension",
            "from app.control_store import ControlStore, CosmosControlStore, InMemoryControlStore",
            "from app.job_worker import JobWorker, build_arg_parser as build_worker_arg_parser, build_worker_from_env, demo_handler",
            "from app.mcp_server import Runtime, build_server, owner_scope_from_headers, runtime_from_env",
            "from app.models import CallbackDeliveryState, CallbackEvent, CallbackPolicy, GetTaskResult, JobPolicy, LifecycleState, Policy, PublicError, StartRequest, TaskRecord, map_aca_state, to_mcp_task",
            "from app.orchestrator import Orchestrator",
            "from app.telemetry import Telemetry, configure, telemetry",
            'print("ok fastmcp external tasks adapter")',
            'print("ok aca jobs sdk surface")',
            "from azure.ai.projects.models import MCPTool, PromptAgentDefinition",
            'mcp_tool = MCPTool(',
            'authorization="task20-token"',
            'prompt_definition = PromptAgentDefinition(',
            'assert prompt_definition.tools[0].authorization == "task20-token"',
            'print("ok azure ai projects prompt mcp authorization surface")',
            'print("ok foundry-mcp-aca-jobs imports")',
        ):
            self.assertIn(required, script)

        match = re.search(r"python - <<'PY'\n(?P<body>.*)\n\s*PY\n?", script, re.S)
        self.assertIsNotNone(match)
        compile(match.group("body"), "<foundry-mcp-aca-jobs validation.script>", "exec")

    def test_validation_script_falls_back_to_git_repo_root(self) -> None:
        pin_fm, _ = self._frontmatter_and_body(SKILL / "references" / "upstream-pin.md")
        script = pin_fm["validation"]["script"]

        self.assertIn("git rev-parse --show-toplevel", script)
        self.assertIn("git -C \"$REPO_ROOT\" rev-parse --is-inside-work-tree", script)
        self.assertIn("PIN_VALIDATION_REPO_ROOT:-", script)
        self.assertIn("could not determine repository root", script)

    def test_stable_errors_document_all_raised_public_error_codes(self) -> None:
        skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        stable_errors = skill_text.split("## Stable errors", 1)[1].split("## Test the implementation", 1)[0]

        source_codes: set[str] = set()
        for path in (
            self._reference_app_dir() / "aca_jobs.py",
            self._reference_app_dir() / "callbacks.py",
            self._reference_app_dir() / "control_store.py",
            self._reference_app_dir() / "mcp_server.py",
            self._reference_app_dir() / "models.py",
            self._reference_app_dir() / "orchestrator.py",
        ):
            source_codes.update(re.findall(r'(?:PublicError|_raise_public_error)\("([A-Z_]+)"', path.read_text(encoding="utf-8")))

        self.assertTrue(source_codes, "expected to discover stable PublicError codes in source")
        for code in sorted(source_codes):
            with self.subTest(code=code):
                self.assertIn(code, stable_errors)

    def test_dockerfile_contract_is_single_shared_runtime_image(self) -> None:
        templates = self._template_dir()
        dockerfiles = list(templates.glob("Dockerfile*"))
        self.assertEqual(
            dockerfiles,
            [templates / "Dockerfile"],
            "templates must contain exactly one Dockerfile and no variants",
        )

        dockerfile = (templates / "Dockerfile").read_text(encoding="utf-8")
        python_image = (
            "python:3.12-slim@sha256:"
            "78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
        )
        uv_image = (
            "ghcr.io/astral-sh/uv:0.12.6@sha256:"
            "88bc6eb1ccd4b82efd0e1b530caffabddf50dc2bf612e66c14ea25b8ee8a4d3d"
        )
        self.assertTrue(dockerfile.startswith(f"FROM {python_image}\n"))
        self.assertEqual(dockerfile.count("FROM "), 1)
        self.assertIn("WORKDIR /srv", dockerfile)
        self.assertIn(f"COPY --from={uv_image} /uv /uvx /bin/", dockerfile)
        self.assertIn("COPY pyproject.toml uv.lock ./", dockerfile)
        self.assertIn("COPY app ./app", dockerfile)
        self.assertIn("RUN uv sync --frozen --no-dev --no-editable", dockerfile)
        self.assertIn('ENV PATH="/srv/.venv/bin:$PATH"', dockerfile)
        self.assertIn("RUN python -m py_compile app/*.py", dockerfile)
        self.assertIn("RUN useradd --create-home --shell /usr/sbin/nologin appuser", dockerfile)
        self.assertIn("USER appuser", dockerfile)
        self.assertIn("EXPOSE 8080", dockerfile)
        self.assertIn('CMD ["python", "-m", "app.mcp_server"]', dockerfile)
        self.assertNotIn("app.job_worker", dockerfile)
        self.assertNotIn("COPY .", dockerfile)
        self.assertNotIn("ADD ", dockerfile)
        self.assertNotIn("ARG ", dockerfile)
        self.assertNotIn("--mount=type=secret", dockerfile)
        self.assertNotIn("pip install", dockerfile)
        for token in ("SECRET", "TOKEN", "PASSWORD", "GITHUB_TOKEN", "AZURE_CLIENT_SECRET"):
            self.assertNotIn(token, dockerfile)
        self.assertLess(dockerfile.index("COPY pyproject.toml uv.lock ./"), dockerfile.index("RUN uv sync --frozen --no-dev --no-editable"))
        self.assertLess(dockerfile.index("COPY app ./app"), dockerfile.index("RUN uv sync --frozen --no-dev --no-editable"))
        self.assertLess(dockerfile.index("RUN uv sync --frozen --no-dev --no-editable"), dockerfile.index("RUN python -m py_compile app/*.py"))
        self.assertLess(dockerfile.index("RUN python -m py_compile app/*.py"), dockerfile.index("USER appuser"))
        self.assertLess(dockerfile.index("USER appuser"), dockerfile.index('CMD ["python", "-m", "app.mcp_server"]'))

    def test_canonical_aca_job_module_contract_is_shared_with_azd_patterns(self) -> None:
        job = (ROOT / "skills" / "azd-patterns" / "references" / "bicep" / "aca-job.bicep").read_text(
            encoding="utf-8"
        )
        self.assertIn("param imageDigest string", job)
        self.assertIn("param command array", job)
        self.assertIn("param args array = []", job)
        self.assertIn("param environmentVariables array = []", job)
        self.assertIn("resource job 'Microsoft.App/jobs@2026-01-01' = {", job)
        self.assertIn("triggerType: 'Manual'", job)
        self.assertIn("image: imageDigest", job)
        self.assertIn("command: command", job)
        self.assertIn("args: args", job)
        self.assertIn("env: environmentVariables", job)
        self.assertNotIn("jobs/write", job)
        self.assertNotIn("delete", job.lower())

    def test_infra_template_files_exist(self) -> None:
        infra = self._infra_dir()
        self.assertEqual(
            sorted(path.name for path in infra.glob("*.bicep")),
            ["app.bicep", "cosmos.bicep", "identity-rbac.bicep", "main.bicep"],
        )
        self.assertTrue((infra / "identity-rbac" / "uami.bicep").is_file())
        self.assertTrue((infra / "identity-rbac" / "assignments.bicep").is_file())
        self.assertTrue((infra / "identity-rbac" / "job-operator.bicep").is_file())

    def test_standalone_template_manifest_includes_assertion_config(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        readme = (SKILL / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "| [templates/bicepconfig.json](templates/bicepconfig.json) |",
            skill,
        )
        self.assertIn("- `templates/bicepconfig.json`", skill)
        self.assertIn("│   └── bicepconfig.json", readme)

    def test_app_module_contract_includes_auth_and_health(self) -> None:
        app = (self._infra_dir() / "app.bicep").read_text(encoding="utf-8")
        normalized = " ".join(app.split())
        self.assertIn("resource app 'Microsoft.App/containerApps@", app)
        self.assertIn("external: true", app)
        self.assertIn("targetPort: 8080", app)
        self.assertIn("transport: 'http'", app)
        self.assertIn("allowInsecure: false", app)
        self.assertIn("name: 'mcp'", app)
        self.assertIn("image: imageDigest", app)
        self.assertIn("command: [ 'python' '-m' 'app.mcp_server' ]", normalized)
        self.assertIn("MCP_ACA_JOBS_AUTH_MODE", app)
        self.assertIn("aca-easy-auth", app)
        self.assertIn("authConfigs@2025-01-01", app)
        self.assertIn("unauthenticatedClientAction: 'Return401'", app)
        self.assertIn("clientId: authClientId", app)
        self.assertIn("allowedAudiences", app)
        self.assertIn("environment().authentication.loginEndpoint", app)
        self.assertIn("param allowedMcpCallerClientIds array = []", app)
        self.assertIn("param allowedMcpCallerPrincipalIds array = []", app)
        self.assertIn(
            "assert exactlyOneMcpCallerAllowlistMode = "
            "(empty(allowedMcpCallerClientIds) && !empty(allowedMcpCallerPrincipalIds)) "
            "|| (!empty(allowedMcpCallerClientIds) && empty(allowedMcpCallerPrincipalIds))",
            normalized,
        )
        self.assertIn(
            "assert nonemptyMcpCallerClientIds = "
            "empty(filter(allowedMcpCallerClientIds, id => empty(trim(id))))",
            normalized,
        )
        self.assertIn(
            "assert nonemptyMcpCallerPrincipalIds = "
            "empty(filter(allowedMcpCallerPrincipalIds, id => empty(trim(id))))",
            normalized,
        )
        self.assertIn(
            "defaultAuthorizationPolicy: !empty(allowedMcpCallerClientIds) "
            "? { allowedApplications: allowedMcpCallerClientIds } "
            ": { allowedPrincipals: { identities: allowedMcpCallerPrincipalIds } }",
            normalized,
        )
        self.assertIn("param azdServiceName string = 'mcp'", app)
        self.assertIn("'azd-service-name': azdServiceName", app)
        self.assertNotIn("'azd-service-name': name", app)
        self.assertIn("livenessProbe", app)
        self.assertIn("startupProbe", app)

    def test_cosmos_module_contract_is_keyless_serverless_with_control_container(self) -> None:
        cosmos = (self._infra_dir() / "cosmos.bicep").read_text(encoding="utf-8")
        normalized = " ".join(cosmos.split())
        self.assertIn("Microsoft.DocumentDB/databaseAccounts@", cosmos)
        self.assertIn("EnableServerless", cosmos)
        self.assertIn("disableLocalAuth: true", cosmos)
        self.assertIn("param useExistingAccount bool = false", cosmos)
        self.assertIn("param existingAccountEndpoint string = ''", cosmos)
        self.assertIn("Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15", cosmos)
        self.assertIn("Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15", cosmos)
        self.assertIn("resource existingAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = if (useExistingAccount)", cosmos)
        self.assertIn("resource brownfieldDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = if (useExistingAccount)", cosmos)
        self.assertIn("resource brownfieldTasks 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = if (useExistingAccount)", cosmos)
        self.assertNotIn("existingDatabase", cosmos)
        self.assertNotIn("existingTasks", cosmos)
        self.assertIn("paths: [ '/ownerScope' ]", normalized)
        self.assertIn("paths: [ '/idempotencyKeyHash' ]", normalized)
        self.assertNotIn("COSMOS_AUTH_KEY", cosmos)
        self.assertIn("storageAccountUrlHost = replace(replace(storageAccountUrl, 'https://', ''), 'http://', '')", (self._infra_dir() / "main.bicep").read_text(encoding="utf-8"))

    def test_identity_rbac_contract_uses_two_uamis_and_only_allowed_job_actions(self) -> None:
        identity = (self._infra_dir() / "identity-rbac.bicep").read_text(encoding="utf-8")
        assignments = (self._infra_dir() / "identity-rbac" / "assignments.bicep").read_text(encoding="utf-8")
        job_operator = (self._infra_dir() / "identity-rbac" / "job-operator.bicep").read_text(
            encoding="utf-8"
        )
        identity_params = self._param_names(identity)
        assignment_params = self._param_names(assignments)
        job_operator_params = self._param_names(job_operator)
        self.assertIn("outputStorageContainerName", identity_params)
        self.assertIn("outputStorageContainerName", assignment_params)
        self.assertNotIn("storageContainerName", identity_params)
        self.assertNotIn("storageContainerName", assignment_params)
        self.assertNotIn("callbackStorageContainerName", identity_params)
        self.assertNotIn("callbackStorageContainerName", assignment_params)
        self.assertIn("jobName", job_operator_params)
        self.assertIn("customRoleDefinitionId", job_operator_params)
        self.assertIn("appUami", identity)
        self.assertIn("jobUami", identity)
        self.assertIn("roleDefinition", identity)
        self.assertIn("assignableScopes", identity)
        self.assertNotIn("callbackStorageContainerName", identity)
        self.assertIn("var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", assignments)

        job_role = self._extract_bicep_block(identity, "jobRoleDefinition")
        actions_match = re.search(r"actions:\s*\[(.*?)\n\s*notActions:", job_role, re.S)
        self.assertIsNotNone(actions_match, "job custom role actions block missing")
        actions = set(re.findall(r"'([^']+)'", actions_match.group(1)))
        self.assertEqual(
            actions,
            {
                "Microsoft.App/jobs/read",
                "Microsoft.App/jobs/start/action",
                "Microsoft.App/jobs/execution/read",
                "Microsoft.App/jobs/executions/read",
                "Microsoft.App/jobs/stop/execution/action",
            },
        )

        for action in (
            "Microsoft.App/jobs/read",
            "Microsoft.App/jobs/start/action",
            "Microsoft.App/jobs/execution/read",
            "Microsoft.App/jobs/executions/read",
            "Microsoft.App/jobs/stop/execution/action",
        ):
            self.assertIn(action, job_role)
        self.assertIn("ba92f5b4-2d11-453d-a403-e96b0029c9fe", identity + "\n" + assignments)
        self.assertIn("sqlRoleDefinitions/00000000-0000-0000-0000-000000000002", assignments)
        self.assertIn("dbs/${cosmosDatabaseName}/colls/${cosmosContainerName}", assignments)
        self.assertNotIn("Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c'", identity + "\n" + assignments)
        for forbidden in ("jobs/write", "jobs/delete", "listsecrets", "stop/multiple", "appJobOperator"):
            self.assertNotIn(forbidden, assignments)

        self.assertNotIn("jobName", assignments)
        self.assertNotIn("customRoleDefinitionId", assignments)
        self.assertIn("resource job 'Microsoft.App/jobs@2026-01-01' existing = {", job_operator)
        self.assertIn("scope: job", job_operator)
        self.assertIn("name: jobName", job_operator)
        self.assertIn("roleDefinitionId: customRoleDefinitionId", job_operator)
        self.assertNotIn("Microsoft.App/jobs/read", job_operator)
        self.assertNotIn("ba92f5b4-2d11-453d-a403-e96b0029c9fe", job_operator)

        scope_expectations = {
            "appAcrPull": "acr",
            "jobAcrPull": "acr",
            "appCosmosData": "cosmos",
            "jobCosmosData": "cosmos",
            "appBlobData": "callbackStorageContainer",
            "jobBlobData": "outputStorageContainer",
            "jobKeyVaultSecretsUser": "keyVault",
        }
        for resource_name, expected_scope in scope_expectations.items():
            block = self._extract_bicep_block(assignments, f"resource {resource_name} ")
            scope_match = re.search(r"(?m)^\s*(scope|parent):\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", block)
            self.assertIsNotNone(scope_match, f"{resource_name} scope/parent missing")
            self.assertEqual(scope_match.group(2), expected_scope, resource_name)

        self.assertIn("resource outputStorageContainer", assignments)
        self.assertIn("resource callbackStorageContainer", assignments)
        self.assertNotRegex(
            assignments,
            r"resource outputStorageContainer [^{\n]+ existing =",
        )
        self.assertNotRegex(
            assignments,
            r"resource callbackStorageContainer [^{\n]+ existing =",
        )
        self.assertNotIn("resource storageContainer ", assignments)
        self.assertIn("scope: callbackStorageContainer", assignments)
        self.assertIn("scope: outputStorageContainer", assignments)
        self.assertNotIn("scope: storageContainer", assignments)
        self.assertNotIn("jobRoleDefinition", assignments)

    def test_main_module_wires_required_env_and_dependency_order(self) -> None:
        main = (self._infra_dir() / "main.bicep").read_text(encoding="utf-8")
        normalized = " ".join(main.split())

        for param in ("inputHosts array", "resultHosts array"):
            self.assertIn(f"param {param}", main)

        self.assertIn("type CallbackAuthMode = 'managed_identity' | 'key_vault'", main)
        self.assertIn("@discriminator('authMode')", main)
        self.assertIn("type CallbackConfig = CallbackManagedIdentityConfig | CallbackKeyVaultConfig", main)
        self.assertIn("param callbackConfig CallbackConfig", main)
        self.assertNotIn("param callbackAuthMode", main)
        self.assertNotIn("param externalCallbackUrl", main)
        self.assertNotIn("param callbackAudience", main)
        self.assertNotIn("param callbackSecretName", main)
        self.assertNotIn("param keyVaultName", main)
        self.assertNotIn("param callbackStorageContainerName", main)
        self.assertIn("param storageAccountUrl string", main)
        self.assertIn("param cosmosAccountEndpoint string = ''", main)
        self.assertIn("param cosmosUseExistingAccount bool = false", main)
        self.assertIn("@maxLength(53)", main)
        self.assertIn("var storageAccountUrlHost = replace(replace(storageAccountUrl, 'https://', ''), 'http://', '')", main)
        self.assertIn("var storageAccountNameFromUrl = split(storageAccountUrlHost, '.')[0]", main)
        self.assertIn("var cosmosAccountNameFromEndpoint = split(replace(replace(cosmosAccountEndpoint, 'https://', ''), 'http://', ''), '.')[0]", main)
        self.assertIn("var storageAccountContractMatches = storageAccountNameFromUrl == storageAccountName", main)
        self.assertIn("var cosmosAccountContractMatches = !cosmosUseExistingAccount || cosmosAccountNameFromEndpoint == cosmosAccountName", main)
        self.assertIn("var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", main)
        self.assertIn(
            "var outputStorageUrl = '${storageAccountUrl}/${outputStorageContainerName}'",
            main,
        )
        self.assertIn("callbackStorageContainerUrl", main)
        self.assertIn("var storageHost = storageAccountUrlHost", main)
        self.assertIn("var effectiveResultHosts = union(resultHosts, [storageHost])", main)
        self.assertIn("useExistingAccount: cosmosUseExistingAccount", main)
        self.assertIn("existingAccountEndpoint: cosmosAccountEndpoint", main)

        self.assertIn("var authAudience = 'api://${authClientId}'", main)
        self.assertIn("callbackConfig.authMode == 'managed_identity' ? 'https://${appName}.${managedEnvironment.properties.defaultDomain}/callbacks/jobs' : callbackConfig.externalCallbackUrl", normalized)
        self.assertIn("auth_mode: callbackConfig.authMode", main)
        self.assertIn("ops: callbackPolicy", main)
        self.assertIn("callbackConfig.authMode == 'managed_identity' ? [", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_AUDIENCE'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_VAULT_URL'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_SECRET_NAME'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME'", main)
        self.assertIn("value: authAudience", main)
        self.assertIn("value: callbackConfig.callbackSecretName", main)
        self.assertIn("value: identities.outputs.jobUamiPrincipalId", main)
        self.assertIn("environment().suffixes.keyvaultDns", main)
        self.assertIn("callbackConfig.authMode == 'key_vault' ? callbackConfig.keyVaultName : ''", normalized)
        self.assertIn("callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", main)

        for required in (
            "AZURE_CLIENT_ID",
            "AZURE_SUBSCRIPTION_ID",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL",
            "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT",
            "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME",
            "MCP_ACA_JOBS_COSMOS_DATABASE",
            "MCP_ACA_JOBS_COSMOS_CONTAINER",
            "MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID",
            "MCP_ACA_JOBS_CALLBACK_CONTAINER_URL",
            "MCP_ACA_JOBS_POLICY_JSON",
            "MCP_ACA_JOBS_JOB_TYPE",
            "MCP_ACA_JOBS_JOB_RESOURCE_GROUP",
            "MCP_ACA_JOBS_JOB_NAME",
            "MCP_ACA_JOBS_JOB_CONTAINER_NAME",
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST",
            "MCP_ACA_JOBS_CALLBACK_URL",
            "MCP_ACA_JOBS_CALLBACK_AUTH_MODE",
            "MCP_ACA_JOBS_CALLBACK_AUDIENCE",
            "MCP_ACA_JOBS_CALLBACK_VAULT_URL",
            "MCP_ACA_JOBS_CALLBACK_SECRET_NAME",
            "MCP_ACA_JOBS_OUTPUT_CONTAINER_URL",
            "MCP_ACA_JOBS_INPUT_HOSTS",
            "MCP_ACA_JOBS_RESULT_HOSTS",
        ):
            self.assertIn(required, main)

        self.assertIn("short-job", main)
        self.assertIn("string({", main)
        self.assertIn("managedEnvironment.properties.defaultDomain", main)
        self.assertIn("callbacks: {", main)
        self.assertIn("audience: authAudience", main)
        self.assertIn("join(inputHosts, ',')", normalized)
        self.assertIn("result_hosts: effectiveResultHosts", main)
        self.assertIn("join(effectiveResultHosts, ',')", normalized)
        self.assertNotIn("join(resultHosts, ',')", normalized)
        self.assertNotIn("CONTAINER_APP_JOB_EXECUTION_NAME", main)
        self.assertNotIn("AZURE_CLIENT_SECRET", main)
        self.assertNotIn("auth_mode: 'managed_identity'", main)
        self.assertNotIn("MCP_ACA_JOBS_CALLBACK_SECRET_VALUE", main)
        self.assertNotIn("callbackSecretValue", main)
        self.assertNotIn("secretRef", main)
        self.assertNotIn("secureValue", main)
        self.assertNotIn("CALLBACK_SECRET_VALUE", main)

        module_order = [
            "module identities",
            "module cosmos",
            "module preRuntimeRbac",
            "module preRuntimeCosmosRbac",
            "module app",
            "module job",
            "module jobOperator",
        ]
        positions = [main.index(marker) for marker in module_order]
        self.assertEqual(positions, sorted(positions), msg=f"unexpected module order: {module_order}")
        self.assertIn("dependsOn: [\n    preRuntimeRbac\n    preRuntimeCosmosRbac\n  ]", main)
        self.assertIn(
            "dependsOn: [\n    app\n    preRuntimeRbac\n    preRuntimeCosmosRbac\n  ]",
            main,
        )

        identity_rbac = (self._infra_dir() / "identity-rbac.bicep").read_text(encoding="utf-8")
        self.assertIn("keyVaultName: callbackConfig.authMode == 'key_vault' ? callbackConfig.keyVaultName : ''", main)
        self.assertIn("keyVaultName: keyVaultName", identity_rbac)
        self.assertIn(
            "if (createPlatformAssignments && !empty(keyVaultName))",
            (self._infra_dir() / "identity-rbac" / "assignments.bicep").read_text(
                encoding="utf-8"
            ),
        )
        self.assertIn("output storageAccountNameFromUrl string", main)
        self.assertIn("output storageAccountContractMatches bool", main)
        self.assertIn("output cosmosAccountNameFromEndpoint string", main)
        self.assertIn("output cosmosAccountContractMatches bool", main)
        self.assertIn(
            "assert storageAccountUrlMatchesName = storageAccountContractMatches",
            main,
        )
        self.assertIn(
            "assert cosmosEndpointMatchesName = cosmosAccountContractMatches",
            main,
        )

    def test_callback_config_bicepparam_variants_compile_and_invalid_key_vault_is_rejected(self) -> None:
        managed_identity_params = """using './main.bicep'

param resourceGroupName = 'rg-jobs'
param location = 'swedencentral'
param acrName = 'acr-jobs'
param environmentName = 'env-jobs'
param storageAccountName = 'storagejobs'
param storageAccountUrl = 'https://storagejobs.blob.core.windows.net'
param outputStorageContainerName = 'outputs'
param allowedMcpCallerClientIds = []
param inputHosts = [
  'input.example.com'
]
param resultHosts = [
  'results.example.com'
]
param cosmosAccountName = 'cosmos-jobs'
param appName = 'mcp-app'
param jobName = 'mcp-job'
param authClientId = 'auth-client-id'
param callbackConfig = {
  authMode: 'managed_identity'
}
"""
        result, compiled = self._build_bicepparam(".test-callback-mi.bicepparam", managed_identity_params)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIsNotNone(compiled)
        self.assertEqual(
            compiled["parameters"]["callbackConfig"]["value"]["authMode"],
            "managed_identity",
        )

        key_vault_params = """using './main.bicep'

param resourceGroupName = 'rg-jobs'
param location = 'swedencentral'
param acrName = 'acr-jobs'
param environmentName = 'env-jobs'
param storageAccountName = 'storagejobs'
param storageAccountUrl = 'https://storagejobs.blob.core.windows.net'
param outputStorageContainerName = 'outputs'
param allowedMcpCallerClientIds = []
param inputHosts = [
  'input.example.com'
]
param resultHosts = [
  'results.example.com'
]
param cosmosAccountName = 'cosmos-jobs'
param appName = 'mcp-app'
param jobName = 'mcp-job'
param authClientId = 'auth-client-id'
param callbackConfig = {
  authMode: 'key_vault'
  externalCallbackUrl: 'https://callback.example.com/callbacks/jobs'
  callbackSecretName: 'callback-secret'
  keyVaultName: 'kv-jobs'
}
"""
        result, compiled = self._build_bicepparam(".test-callback-kv.bicepparam", key_vault_params)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIsNotNone(compiled)
        self.assertEqual(compiled["parameters"]["callbackConfig"]["value"]["authMode"], "key_vault")
        self.assertEqual(
            compiled["parameters"]["callbackConfig"]["value"]["externalCallbackUrl"],
            "https://callback.example.com/callbacks/jobs",
        )
        self.assertEqual(compiled["parameters"]["callbackConfig"]["value"]["callbackSecretName"], "callback-secret")
        self.assertEqual(compiled["parameters"]["callbackConfig"]["value"]["keyVaultName"], "kv-jobs")

        invalid_key_vault_params = """using './main.bicep'

param resourceGroupName = 'rg-jobs'
param location = 'swedencentral'
param acrName = 'acr-jobs'
param environmentName = 'env-jobs'
param storageAccountName = 'storagejobs'
param storageAccountUrl = 'https://storagejobs.blob.core.windows.net'
param outputStorageContainerName = 'outputs'
param allowedMcpCallerClientIds = []
param inputHosts = [
  'input.example.com'
]
param resultHosts = [
  'results.example.com'
]
param cosmosAccountName = 'cosmos-jobs'
param appName = 'mcp-app'
param jobName = 'mcp-job'
param authClientId = 'auth-client-id'
param callbackConfig = {
  authMode: 'key_vault'
}
"""
        result, _ = self._build_bicepparam(".test-callback-kv-invalid.bicepparam", invalid_key_vault_params)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BCP035", result.stderr)
        self.assertIn("callbackSecretName", result.stderr)
        self.assertIn("externalCallbackUrl", result.stderr)
        self.assertIn("keyVaultName", result.stderr)

    def test_easy_auth_allowlist_parameter_variants_have_exact_truth_table(
        self,
    ) -> None:
        def variant(
            client_ids: list[str], principal_ids: list[str]
        ) -> tuple[subprocess.CompletedProcess[str], dict[str, object] | None]:
            def array(values: list[str]) -> str:
                if not values:
                    return "[]"
                return "[\n" + "".join(f"  '{value}'\n" for value in values) + "]"

            contents = f"""using './main.bicep'

param resourceGroupName = 'rg-jobs'
param location = 'swedencentral'
param acrName = 'acr-jobs'
param environmentName = 'env-jobs'
param storageAccountName = 'storagejobs'
param storageAccountUrl = 'https://storagejobs.blob.core.windows.net'
param outputStorageContainerName = 'outputs'
param allowedMcpCallerClientIds = {array(client_ids)}
param allowedMcpCallerPrincipalIds = {array(principal_ids)}
param inputHosts = [
  'input.example.com'
]
param resultHosts = [
  'results.example.com'
]
param cosmosAccountName = 'cosmos-jobs'
param appName = 'mcp-app'
param jobName = 'mcp-job'
param authClientId = 'auth-client-id'
param callbackConfig = {{
  authMode: 'managed_identity'
}}
"""
            return self._build_bicepparam(
                ".test-easy-auth-allowlist.bicepparam", contents
            )

        cases = (
            ("client-only", ["caller-client"], [], True),
            ("principal-only", [], ["caller-principal"], True),
            ("both", ["caller-client"], ["caller-principal"], False),
            ("neither", [], [], False),
            ("client-empty-entry", [""], [], False),
            ("principal-whitespace-entry", [], ["   "], False),
        )
        for label, client_ids, principal_ids, expected in cases:
            with self.subTest(label=label):
                result, compiled = variant(client_ids, principal_ids)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNotNone(compiled)
                assert compiled is not None
                self.assertEqual(
                    compiled["parameters"]["allowedMcpCallerClientIds"]["value"],
                    client_ids,
                )
                self.assertEqual(
                    compiled["parameters"]["allowedMcpCallerPrincipalIds"]["value"],
                    principal_ids,
                )
                self.assertEqual(
                    self._allowlist_assertions_accept(client_ids, principal_ids),
                    expected,
                )

    def test_compiled_arm_contains_exact_easy_auth_allowlist_assertions(
        self,
    ) -> None:
        expected_asserts = {
            "exactlyOneMcpCallerAllowlistMode": (
                "[or(and(empty(parameters('allowedMcpCallerClientIds')), "
                "not(empty(parameters('allowedMcpCallerPrincipalIds')))), "
                "and(not(empty(parameters('allowedMcpCallerClientIds'))), "
                "empty(parameters('allowedMcpCallerPrincipalIds'))))]"
            ),
            "nonemptyMcpCallerClientIds": (
                "[empty(filter(parameters('allowedMcpCallerClientIds'), "
                "lambda('id', empty(trim(lambdaVariables('id'))))))]"
            ),
            "nonemptyMcpCallerPrincipalIds": (
                "[empty(filter(parameters('allowedMcpCallerPrincipalIds'), "
                "lambda('id', empty(trim(lambdaVariables('id'))))))]"
            ),
        }
        for source in (
            self._infra_dir() / "app.bicep",
            self._infra_dir() / "main.bicep",
        ):
            with self.subTest(source=source.name):
                result = subprocess.run(
                    [
                        "az",
                        "bicep",
                        "build",
                        "--file",
                        str(source),
                        "--stdout",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                compiled = json.loads(result.stdout)
                self.assertEqual(compiled["languageVersion"], "2.1-experimental")
                for assertion_name, expression in expected_asserts.items():
                    self.assertEqual(compiled["asserts"][assertion_name], expression)
                expressions = " ".join(
                    compiled["asserts"][name] for name in expected_asserts
                )
                for token in (
                    "parameters('allowedMcpCallerClientIds')",
                    "parameters('allowedMcpCallerPrincipalIds')",
                    "filter(",
                    "trim(",
                ):
                    self.assertIn(token, expressions)

    def test_bicep_builds_without_experimental_assertion_warnings(self) -> None:
        files = [
            self._infra_dir() / "app.bicep",
            self._infra_dir() / "cosmos.bicep",
            self._infra_dir() / "identity-rbac.bicep",
            self._infra_dir() / "main.bicep",
            self._infra_dir() / "identity-rbac" / "assignments.bicep",
            self._infra_dir() / "identity-rbac" / "job-operator.bicep",
            self._infra_dir() / "identity-rbac" / "uami.bicep",
        ]
        scratch = ROOT / ".scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bicep-builds-", dir=scratch) as directory:
            for index, source in enumerate(files):
                with self.subTest(source=source.name):
                    result = subprocess.run(
                        [
                            "az",
                            "bicep",
                            "build",
                            "--file",
                            str(source),
                            "--outfile",
                            str(pathlib.Path(directory) / f"{index}-{source.stem}.json"),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, msg=result.stderr)
                    combined = f"{result.stdout}\n{result.stderr}"
                    warning_lines = [
                        line
                        for line in combined.splitlines()
                        if line.lower().startswith("warning:")
                    ]
                    for line in warning_lines:
                        self.assertTrue(
                            "a new bicep release is available" in line.lower()
                            or "experimental bicep features have been enabled" in line.lower(),
                            msg=f"unexpected bicep warning for {source.name}: {line}",
                        )

    def test_main_module_composes_shared_digest_and_outputs_contract(self) -> None:
        main = (self._infra_dir() / "main.bicep").read_text(encoding="utf-8")
        normalized = " ".join(main.split())
        self.assertIn("../../../azd-patterns/references/bicep/aca-job.bicep", main)
        self.assertIn("mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48", main)
        self.assertIn("param allowedMcpCallerClientIds array = []", main)
        self.assertIn("param allowedMcpCallerPrincipalIds array = []", main)
        self.assertIn(
            "assert exactlyOneMcpCallerAllowlistMode = "
            "(empty(allowedMcpCallerClientIds) && !empty(allowedMcpCallerPrincipalIds)) "
            "|| (!empty(allowedMcpCallerClientIds) && empty(allowedMcpCallerPrincipalIds))",
            normalized,
        )
        self.assertRegex(
            normalized,
            r"allowedMcpCallerClientIds:\s*!empty\(allowedMcpCallerClientIds\)\s*"
            r"\?\s*union\(allowedMcpCallerClientIds,\s*\[\s*identities\.outputs\.jobUamiClientId\s*\]\)\s*"
            r":\s*\[\]",
        )
        self.assertRegex(
            normalized,
            r"allowedMcpCallerPrincipalIds:\s*!empty\(allowedMcpCallerPrincipalIds\)\s*"
            r"\?\s*union\(allowedMcpCallerPrincipalIds,\s*\[\s*identities\.outputs\.jobUamiPrincipalId\s*\]\)\s*"
            r":\s*\[\]",
        )
        self.assertIn("param outputStorageContainerName string", main)
        self.assertIn("@maxLength(53)", main)
        self.assertIn("var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", main)
        self.assertNotIn("param storageContainerName string", main)
        self.assertIn("output outputStorageContainerUrl string", main)
        self.assertIn("output callbackStorageContainerUrl string", main)
        self.assertIn("/${outputStorageContainerName}", main)
        self.assertIn("/${callbackStorageContainerName}", main)
        self.assertIn("output ACR_NAME string =", main)
        self.assertIn("output ACR_LOGIN_SERVER string =", main)
        self.assertNotIn("output storageUrl string", main)
        self.assertIn("appResourceName", main)
        self.assertIn("jobResourceName", main)
        self.assertIn("appFqdn", main)
        self.assertIn("appIdentity", main)
        self.assertIn("jobIdentity", main)
        self.assertIn("cosmosEndpoint", main)
        self.assertIn("outputStorageContainerUrl", main)
        self.assertIn("callbackStorageContainerUrl", main)
        self.assertIn("authAudience", main)
        self.assertIn("appImageDigest", main)

    def test_policy_validates_the_template_output_storage_url_when_storage_host_is_allowlisted(self) -> None:
        policy = Policy(input_hosts={"input.example.com"}, result_hosts={"results.example.com", "storagejobs.blob.core.windows.net"})

        approved = policy.validate_result("https://storagejobs.blob.core.windows.net/outputs")
        self.assertEqual(str(approved), "https://storagejobs.blob.core.windows.net/outputs")
        self.assertIn("storagejobs.blob.core.windows.net", policy.result_hosts)

    def test_source_modules_expose_both_helpable_clis(self) -> None:
        server_source = (self._reference_app_dir() / "mcp_server.py").read_text(encoding="utf-8")
        worker_source = (self._reference_app_dir() / "job_worker.py").read_text(encoding="utf-8")

        self.assertIn('argparse.ArgumentParser(description="Run the foundry-mcp-aca-jobs MCP server.")', server_source)
        self.assertIn('argparse.ArgumentParser(description="Run the foundry-mcp-aca-jobs ACA Job worker.")', worker_source)
        self.assertIn("def main(", server_source)
        self.assertIn("def main(", worker_source)
        self.assertIn("raise SystemExit(main())", server_source)
        self.assertIn("raise SystemExit(main())", worker_source)

    def test_azure_yaml_has_one_service_and_one_postdeploy_chain(self) -> None:
        azure_yaml_path = self._template_dir() / "azure.yaml"
        text = azure_yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)

        self.assertEqual(list(data["services"].keys()), ["mcp"])
        self.assertEqual(data["services"]["mcp"]["project"], ".")
        self.assertEqual(data["services"]["mcp"]["language"], "python")
        self.assertEqual(data["services"]["mcp"]["host"], "containerapp")
        self.assertEqual(data["services"]["mcp"]["docker"], {"path": "Dockerfile", "context": "."})
        self.assertIn("postdeploy", data["hooks"])
        self.assertEqual(data["hooks"]["postdeploy"]["shell"], "sh")
        hook_lines = data["hooks"]["postdeploy"]["run"].splitlines()
        self.assertEqual(hook_lines[0], "set -eu")
        self.assertNotIn("pipefail", data["hooks"]["postdeploy"]["run"])
        self.assertIn("converge_image.py", text)
        self.assertIn("verify_deployment.py", text)
        self.assertIn("cd infra/scripts && uv sync --frozen", text)
        self.assertIn('EXPECTED_IMAGE_DIGEST="$(uv run --frozen python converge_image.py)"', text)
        self.assertIn(
            'EXPECTED_IMAGE_DIGEST="$EXPECTED_IMAGE_DIGEST" uv run --frozen python verify_deployment.py',
            text,
        )
        self.assertIn("uv run --frozen python converge_image.py", text)
        self.assertIn("uv run --frozen python verify_deployment.py", text)
        for forbidden in ("az acr build", "az containerapp job", "azd-service-name: job"):
            self.assertNotIn(forbidden, text)

    def test_infra_scripts_pyproject_and_lockfile_are_present(self) -> None:
        scripts = self._script_dir()
        pyproject = tomllib.loads((scripts / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(pyproject["project"]["requires-python"], ">=3.12")
        self.assertEqual(
            pyproject["project"]["dependencies"],
            [
                "azure-identity~=1.25.3",
                "azure-mgmt-appcontainers~=5.0.0",
            ],
        )
        self.assertTrue((scripts / "uv.lock").is_file())

    def test_parse_image_reference_requires_exact_login_server_match(self) -> None:
        module = self._load_script("converge_image.py", "foundry_mcp_aca_jobs_converge_image_parse")
        self.assertEqual(
            module.parse_image_reference("myregistry.azurecr.us/mcp/service:20260903.1", "myregistry.azurecr.us"),
            ("myregistry.azurecr.us", "mcp/service", "20260903.1"),
        )
        with self.assertRaisesRegex(ValueError, r"must exactly match ACR_LOGIN_SERVER"):
            module.parse_image_reference("other.azurecr.us/mcp/service:20260903.1", "myregistry.azurecr.us")

    def test_converge_image_parses_digest_and_updates_drifting_resources_once(self) -> None:
        module = self._load_script("converge_image.py", "foundry_mcp_aca_jobs_converge_image")
        image_name = "myregistry.azurecr.us/mcp/service:20260903.1"
        env_values = self._azd_env_values()
        manifest_digest = "sha256:" + "a" * 64
        expected_image = "myregistry.azurecr.us/mcp/service@" + manifest_digest

        app_container = SimpleNamespace(
            name="mcp",
            image=image_name,
            command=["python", "-m", "app.mcp_server"],
            env=self._env_items(
                {
                    "MCP_ACA_JOBS_POLICY_JSON": self._policy_json(expected_image),
                    "APP_ENV": "1",
                }
            ),
            secrets=[SimpleNamespace(name="APP_SECRET", value="redacted")],
        )
        job_container = SimpleNamespace(
            name="job",
            image=image_name,
            command=["python", "-m", "app.job_worker"],
            env=self._env_items(
                {
                    "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": expected_image,
                    "JOB_ENV": "1",
                }
            ),
            secrets=[SimpleNamespace(name="JOB_SECRET", value="redacted")],
        )
        app_identity = SimpleNamespace(type="UserAssigned", userAssignedIdentities={"app-id": {}})
        job_identity = SimpleNamespace(type="UserAssigned", userAssignedIdentities={"job-id": {}})
        app = SimpleNamespace(
            identity=app_identity,
            properties=SimpleNamespace(
                configuration=SimpleNamespace(
                    ingress=SimpleNamespace(external=True, targetPort=8080, transport="http", allowInsecure=False),
                    registries=[SimpleNamespace(server="myregistry.azurecr.us", identity="app-id")],
                    secrets=[SimpleNamespace(name="APP_SECRET")],
                    activeRevisionsMode="Single",
                ),
                template=SimpleNamespace(
                    containers=[app_container],
                    revision_suffix="azd-existing",
                ),
            ),
        )
        job = SimpleNamespace(
            identity=job_identity,
            properties=SimpleNamespace(
                configuration=SimpleNamespace(
                    triggerType="Manual",
                    registries=[SimpleNamespace(server="myregistry.azurecr.us", identity="job-id")],
                    secrets=[SimpleNamespace(name="JOB_SECRET")],
                ),
                template=SimpleNamespace(containers=[job_container]),
            ),
        )
        app_result = SimpleNamespace(result=lambda: app)
        job_result = SimpleNamespace(result=lambda: job)
        app_updates: list[tuple[str, str, object]] = []
        job_updates: list[tuple[str, str, object]] = []

        client = SimpleNamespace(
            container_apps=SimpleNamespace(
                get=lambda resource_group, name: app,
                begin_create_or_update=lambda resource_group, name, body: app_updates.append((resource_group, name, body)) or app_result,
            ),
            jobs=SimpleNamespace(
                get=lambda resource_group, name: job,
                begin_create_or_update=lambda resource_group, name, body: job_updates.append((resource_group, name, body)) or job_result,
            ),
        )

        digest_calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(args, **kwargs):
            digest_calls.append((list(args), kwargs))
            return SimpleNamespace(stdout=json.dumps(env_values), returncode=0)

        def fake_check_output(args, **kwargs):
            self.assertEqual(
                list(args),
                [
                    "az",
                    "acr",
                    "manifest",
                    "show-metadata",
                    "--registry",
                    "task13acr",
                    "--name",
                    "mcp/service:20260903.1",
                    "--query",
                    "digest",
                    "-o",
                    "tsv",
                ],
            )
            return manifest_digest

        result = module.converge_image(
            run=fake_run,
            check_output=fake_check_output,
            credential_factory=lambda: object(),
            client_factory=lambda credential, subscription_id: client,
        )

        self.assertEqual(result, expected_image)
        self.assertEqual(len(digest_calls), 1)
        self.assertEqual(len(app_updates), 1)
        self.assertEqual(len(job_updates), 1)
        self.assertEqual(app_updates[0][0:2], ("rg-jobs", "mcp-app"))
        self.assertEqual(job_updates[0][0:2], ("rg-jobs", "mcp-job"))
        self.assertEqual(app_updates[0][2].properties.template.containers[0].image, expected_image)
        self.assertIsNone(app_updates[0][2].properties.template.revision_suffix)
        self.assertEqual(job_updates[0][2].properties.template.containers[0].image, expected_image)
        updated_policy = json.loads(
            app_updates[0][2].properties.template.containers[0].env[0].value
        )
        self.assertEqual(
            {
                value["image_digest"]
                for value in updated_policy["jobs"].values()
            },
            {expected_image},
        )
        self.assertEqual(
            job_updates[0][2].properties.template.containers[0].env[0].value,
            expected_image,
        )
        self.assertEqual(app.properties.template.revision_suffix, "azd-existing")
        self.assertEqual(app.properties.template.containers[0].env[1].value, "1")
        self.assertEqual(job.properties.template.containers[0].secrets[0].name, "JOB_SECRET")

    def test_converge_image_rejects_invalid_tag_digest_and_contract_drift(self) -> None:
        module = self._load_script("converge_image.py", "foundry_mcp_aca_jobs_converge_image_invalid")
        env_values = self._azd_env_values()
        base_run = lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(env_values), returncode=0)
        base_check_output = lambda *args, **kwargs: "sha256:" + "b" * 64

        with self.assertRaises(ValueError):
            module.parse_image_reference("not-a-registry-image", "myregistry.azurecr.us")
        with self.assertRaises(ValueError):
            module.parse_image_reference("myregistry.example.com/mcp/service:tag", "myregistry.azurecr.us")
        with self.assertRaises(ValueError):
            module.parse_image_reference("myregistry.azurecr.us/mcp/service", "myregistry.azurecr.us")
        with self.assertRaises(ValueError):
            module.parse_image_reference("other.azurecr.us/mcp/service:tag", "myregistry.azurecr.us")
        with self.assertRaises(ValueError):
            module.resolve_image_digest(
                "myregistry.azurecr.us/mcp/service:20260903.1",
                acr_name="task13acr",
                acr_login_server="myregistry.azurecr.us",
                check_output=lambda *args, **kwargs: "not-a-digest",
            )

        app = SimpleNamespace(
            identity=SimpleNamespace(type="UserAssigned", userAssignedIdentities={"app-id": {}}),
            properties=SimpleNamespace(
                configuration=SimpleNamespace(registries=[], secrets=[], activeRevisionsMode="Single"),
                template=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            name="mcp",
                            image="myregistry.azurecr.us/mcp/service@sha256:" + "c" * 64,
                            command=["python", "-m", "app.other_server"],
                            env=self._env_items(
                                {
                                    "MCP_ACA_JOBS_POLICY_JSON": self._policy_json(
                                        "myregistry.azurecr.us/mcp/service@sha256:"
                                        + "b" * 64
                                    )
                                }
                            ),
                            secrets=[],
                        )
                    ]
                ),
            ),
        )
        job = SimpleNamespace(
            identity=SimpleNamespace(type="UserAssigned", userAssignedIdentities={"app-id": {}}),
            properties=SimpleNamespace(
                configuration=SimpleNamespace(triggerType="Manual", registries=[], secrets=[]),
                template=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            name="job",
                            image="myregistry.azurecr.us/mcp/service@sha256:" + "c" * 64,
                            command=["python", "-m", "app.job_worker"],
                            env=self._env_items(
                                {
                                    "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": (
                                        "myregistry.azurecr.us/mcp/service@sha256:"
                                        + "b" * 64
                                    )
                                }
                            ),
                            secrets=[],
                        )
                    ]
                ),
            ),
        )
        client = SimpleNamespace(
            container_apps=SimpleNamespace(
                get=lambda resource_group, name: app,
                begin_create_or_update=lambda *args, **kwargs: self.fail("should not update on contract drift"),
            ),
            jobs=SimpleNamespace(
                get=lambda resource_group, name: job,
                begin_create_or_update=lambda *args, **kwargs: self.fail("should not update on contract drift"),
            ),
        )

        with self.assertRaises(RuntimeError):
            module.converge_image(
                run=base_run,
                check_output=base_check_output,
                credential_factory=lambda: object(),
                client_factory=lambda credential, subscription_id: client,
            )

        app.properties.template.containers[0].command = ["python", "-m", "app.mcp_server"]
        app.properties.template.containers[0].image = "myregistry.azurecr.us/mcp/service@sha256:" + "b" * 64
        job.properties.template.containers[0].image = "myregistry.azurecr.us/mcp/service@sha256:" + "b" * 64
        job.identity.userAssignedIdentities = {"app-id": {}}
        with self.assertRaises(RuntimeError):
            module.converge_image(
                run=base_run,
                check_output=base_check_output,
                credential_factory=lambda: object(),
                client_factory=lambda credential, subscription_id: client,
            )

    def test_converge_image_updates_stale_policy_and_job_env_with_mapping_env_shapes(self) -> None:
        module = self._load_script(
            "converge_image.py",
            "foundry_mcp_aca_jobs_converge_image_mapping_policy",
        )
        manifest_digest = "sha256:" + "d" * 64
        expected_image = "myregistry.azurecr.us/mcp/service@" + manifest_digest
        stale_image = "myregistry.azurecr.us/mcp/service@sha256:" + "c" * 64
        app = {
            "identity": {"userAssignedIdentities": {"app-id": {}}},
            "properties": {
                "template": {
                    "revisionSuffix": "app-revision",
                    "containers": [
                        {
                            "name": "mcp",
                            "image": expected_image,
                            "command": ["python", "-m", "app.mcp_server"],
                            "env": [
                                {
                                    "name": "MCP_ACA_JOBS_POLICY_JSON",
                                    "value": self._policy_json(
                                        stale_image,
                                        second_image=expected_image,
                                    ),
                                }
                            ],
                        }
                    ],
                }
            },
        }
        job = {
            "identity": {"userAssignedIdentities": {"job-id": {}}},
            "properties": {
                "template": {
                    "revisionSuffix": "job-value-must-remain",
                    "containers": [
                        {
                            "name": "job",
                            "image": expected_image,
                            "command": ["python", "-m", "app.job_worker"],
                            "env": [
                                {
                                    "name": "MCP_ACA_JOBS_JOB_IMAGE_DIGEST",
                                    "value": stale_image,
                                }
                            ],
                        }
                    ],
                }
            },
        }
        app_updates: list[dict[str, object]] = []
        job_updates: list[dict[str, object]] = []
        client = SimpleNamespace(
            container_apps=SimpleNamespace(
                get=lambda resource_group, name: app,
                begin_create_or_update=lambda resource_group, name, body: (
                    app_updates.append(body)
                    or SimpleNamespace(result=lambda: body)
                ),
            ),
            jobs=SimpleNamespace(
                get=lambda resource_group, name: job,
                begin_create_or_update=lambda resource_group, name, body: (
                    job_updates.append(body)
                    or SimpleNamespace(result=lambda: body)
                ),
            ),
        )

        result = module.converge_image(
            run=lambda *args, **kwargs: SimpleNamespace(
                stdout=json.dumps(self._azd_env_values()),
                returncode=0,
            ),
            check_output=lambda *args, **kwargs: manifest_digest,
            credential_factory=lambda: object(),
            client_factory=lambda credential, subscription_id: client,
        )

        self.assertEqual(result, expected_image)
        self.assertEqual(len(app_updates), 1)
        self.assertEqual(len(job_updates), 1)
        app_template = app_updates[0]["properties"]["template"]
        job_template = job_updates[0]["properties"]["template"]
        self.assertNotIn("revisionSuffix", app_template)
        self.assertEqual(job_template["revisionSuffix"], "job-value-must-remain")
        app_container = app_template["containers"][0]
        job_container = job_template["containers"][0]
        self.assertEqual(app_container["image"], expected_image)
        self.assertEqual(job_container["image"], expected_image)
        policy = json.loads(app_container["env"][0]["value"])
        self.assertEqual(
            {
                entry["image_digest"]
                for entry in policy["jobs"].values()
            },
            {expected_image},
        )
        self.assertEqual(job_container["env"][0]["value"], expected_image)
        self.assertEqual(
            json.loads(app["properties"]["template"]["containers"][0]["env"][0]["value"])[
                "jobs"
            ]["short-job"]["image_digest"],
            stale_image,
        )
        self.assertEqual(
            job["properties"]["template"]["containers"][0]["env"][0]["value"],
            stale_image,
        )

    def test_converge_image_rejects_invalid_policy_shapes_before_any_update(self) -> None:
        module = self._load_script(
            "converge_image.py",
            "foundry_mcp_aca_jobs_converge_image_invalid_policy",
        )
        manifest_digest = "sha256:" + "d" * 64
        expected_image = "myregistry.azurecr.us/mcp/service@" + manifest_digest
        invalid_policies = (
            "{",
            "{}",
            '{"jobs":[]}',
            '{"jobs":{}}',
            '{"jobs":{"short-job":[]}}',
            '{"jobs":{"short-job":{}}}',
            '{"jobs":{"short-job":{"image_digest":"repo:tag"}}}',
        )

        for invalid_policy in invalid_policies:
            with self.subTest(policy=invalid_policy):
                client = self._verify_deployment_client(
                    expected_image=expected_image,
                    app_env_overrides={
                        "MCP_ACA_JOBS_POLICY_JSON": invalid_policy
                    },
                )
                app_updates: list[object] = []
                job_updates: list[object] = []
                client.container_apps.begin_create_or_update = (
                    lambda *args: app_updates.append(args)
                )
                client.jobs.begin_create_or_update = (
                    lambda *args: job_updates.append(args)
                )

                with self.assertRaisesRegex(
                    RuntimeError,
                    "MCP_ACA_JOBS_POLICY_JSON",
                ):
                    module.converge_image(
                        run=lambda *args, **kwargs: SimpleNamespace(
                            stdout=json.dumps(self._azd_env_values()),
                            returncode=0,
                        ),
                        check_output=lambda *args, **kwargs: manifest_digest,
                        credential_factory=lambda: object(),
                        client_factory=lambda credential, subscription_id: client,
                    )
                self.assertEqual(app_updates, [])
                self.assertEqual(job_updates, [])

        client = self._verify_deployment_client(expected_image=expected_image)
        job = client.jobs.get("rg-jobs", "mcp-job")
        job.properties.template.containers[0].env = [
            item
            for item in job.properties.template.containers[0].env
            if item.name != "MCP_ACA_JOBS_JOB_IMAGE_DIGEST"
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST",
        ):
            module.converge_image(
                run=lambda *args, **kwargs: SimpleNamespace(
                    stdout=json.dumps(self._azd_env_values()),
                    returncode=0,
                ),
                check_output=lambda *args, **kwargs: manifest_digest,
                credential_factory=lambda: object(),
                client_factory=lambda credential, subscription_id: client,
            )

    def test_converge_image_is_idempotent_when_both_resources_match(self) -> None:
        module = self._load_script("converge_image.py", "foundry_mcp_aca_jobs_converge_image_idempotent")
        env_values = self._azd_env_values()
        manifest_digest = "sha256:" + "d" * 64
        expected_image = "myregistry.azurecr.us/mcp/service@" + manifest_digest
        app = SimpleNamespace(
            identity=SimpleNamespace(type="UserAssigned", userAssignedIdentities={"app-id": {}}),
            properties=SimpleNamespace(
                configuration=SimpleNamespace(registries=[], secrets=[], activeRevisionsMode="Single"),
                template=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            name="mcp",
                            image=expected_image,
                            command=["python", "-m", "app.mcp_server"],
                            env=self._env_items(
                                {
                                    "MCP_ACA_JOBS_POLICY_JSON": self._policy_json(
                                        expected_image
                                    )
                                }
                            ),
                            secrets=[],
                        )
                    ]
                ),
            ),
        )
        job = SimpleNamespace(
            identity=SimpleNamespace(type="UserAssigned", userAssignedIdentities={"job-id": {}}),
            properties=SimpleNamespace(
                configuration=SimpleNamespace(triggerType="Manual", registries=[], secrets=[]),
                template=SimpleNamespace(
                    containers=[
                        SimpleNamespace(
                            name="job",
                            image=expected_image,
                            command=["python", "-m", "app.job_worker"],
                            env=self._env_items(
                                {
                                    "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": expected_image
                                }
                            ),
                            secrets=[],
                        )
                    ]
                ),
            ),
        )
        client = SimpleNamespace(
            container_apps=SimpleNamespace(
                get=lambda resource_group, name: app,
                begin_create_or_update=lambda *args, **kwargs: self.fail("idempotent converge should not update"),
            ),
            jobs=SimpleNamespace(
                get=lambda resource_group, name: job,
                begin_create_or_update=lambda *args, **kwargs: self.fail("idempotent converge should not update"),
            ),
        )

        result = module.converge_image(
            run=lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(env_values), returncode=0),
            check_output=lambda *args, **kwargs: manifest_digest,
            credential_factory=lambda: object(),
            client_factory=lambda credential, subscription_id: client,
        )

        self.assertEqual(result, expected_image)

    def test_load_azd_env_values_accepts_supported_json_shapes_and_requires_keys(self) -> None:
        module = self._load_script("converge_image.py", "foundry_mcp_aca_jobs_converge_image_env_shapes")
        env_values = self._azd_env_values()

        for payload in (env_values, {"values": env_values}):
            with self.subTest(payload=payload):
                result = module.load_azd_env_values(
                    run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                )
                self.assertEqual(result, env_values)

        missing_values = env_values.copy()
        missing_values.pop("AZURE_SUBSCRIPTION_ID")
        for payload in (missing_values, {"values": missing_values}):
            with self.subTest(missing=payload):
                with self.assertRaisesRegex(RuntimeError, r"missing required azd env values: .*AZURE_SUBSCRIPTION_ID"):
                    module.load_azd_env_values(
                        run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                    )

        missing_registry = env_values.copy()
        missing_registry.pop("ACR_NAME")
        for payload in (missing_registry, {"values": missing_registry}):
            with self.subTest(missing_registry=payload):
                with self.assertRaisesRegex(RuntimeError, r"missing required azd env values: .*ACR_NAME"):
                    module.load_azd_env_values(
                        run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                    )

        missing_storage_url = env_values.copy()
        missing_storage_url.pop("MCP_ACA_JOBS_STORAGE_ACCOUNT_URL")
        for payload in (missing_storage_url, {"values": missing_storage_url}):
            with self.subTest(missing_storage_url=payload):
                with self.assertRaisesRegex(RuntimeError, r"missing required azd env values: .*MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"):
                    module.load_azd_env_values(
                        run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                    )

        missing_cosmos_account = env_values.copy()
        missing_cosmos_account.pop("MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME")
        for payload in (missing_cosmos_account, {"values": missing_cosmos_account}):
            with self.subTest(missing_cosmos_account=payload):
                with self.assertRaisesRegex(RuntimeError, r"missing required azd env values: .*MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME"):
                    module.load_azd_env_values(
                        run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                    )

        missing_cosmos_mode = env_values.copy()
        missing_cosmos_mode.pop("MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT")
        for payload in (missing_cosmos_mode, {"values": missing_cosmos_mode}):
            with self.subTest(missing_cosmos_mode=payload):
                with self.assertRaisesRegex(RuntimeError, r"missing required azd env values: .*MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT"):
                    module.load_azd_env_values(
                        run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                    )

        missing_login_server = env_values.copy()
        missing_login_server.pop("ACR_LOGIN_SERVER")
        for payload in (missing_login_server, {"values": missing_login_server}):
            with self.subTest(missing_login_server=payload):
                with self.assertRaisesRegex(RuntimeError, r"missing required azd env values: .*ACR_LOGIN_SERVER"):
                    module.load_azd_env_values(
                        run=lambda *args, payload=payload, **kwargs: SimpleNamespace(stdout=json.dumps(payload), returncode=0),
                    )

    def test_verify_deployment_reads_expected_digest_from_process_env_and_prints_markers(self) -> None:
        module = self._load_script("verify_deployment.py", "foundry_mcp_aca_jobs_verify_deployment")
        expected_image = "myregistry.azurecr.us/mcp/service@sha256:" + "e" * 64
        for mapping_env in (False, True):
            with self.subTest(mapping_env=mapping_env):
                client = self._verify_deployment_client(
                    expected_image=expected_image,
                    mapping_env=mapping_env,
                )
                stdout = io.StringIO()

                with patch.dict(os.environ, {"EXPECTED_IMAGE_DIGEST": expected_image}, clear=False):
                    result = module.verify_deployment(
                        run=lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(self._azd_env_values()), returncode=0),
                        credential_factory=lambda: object(),
                        client_factory=lambda credential, subscription_id: client,
                        stdout=stdout,
                    )

                self.assertIsNone(result)
                self.assertEqual(stdout.getvalue().splitlines(), ["SHARED_IMAGE_DIGEST_MATCH", "ENTRYPOINTS_MATCH"])

    def test_verify_deployment_rejects_contract_drift_without_printing_markers(self) -> None:
        module = self._load_script("verify_deployment.py", "foundry_mcp_aca_jobs_verify_deployment_drift")
        expected_image = "myregistry.azurecr.us/mcp/service@sha256:" + "e" * 64
        base_env = self._azd_env_values()
        failure_cases = (
            ("image drift", {"job_image": "myregistry.azurecr.us/mcp/service@sha256:" + "f" * 64}, "shared image digest mismatch"),
            ("command drift", {"job_command": ["python", "-m", "app.other_worker"]}, "job entrypoint mismatch"),
            ("distinct uami drift", {"job_identity_id": "app-id"}, "app and job must use distinct UAMI IDs"),
            ("app auth mode drift", {"app_env_overrides": {"MCP_ACA_JOBS_AUTH_MODE": "broken"}}, "app easy-auth mode missing"),
            ("job auth mode drift", {"job_env_overrides": {"MCP_ACA_JOBS_AUTH_MODE": "aca-easy-auth"}}, "job must not inherit app easy-auth mode"),
            ("callback auth mode drift", {"job_env_overrides": {"MCP_ACA_JOBS_CALLBACK_AUTH_MODE": "bogus"}}, "job callback auth mode invalid"),
            (
                "app policy image drift",
                {
                    "app_env_overrides": {
                        "MCP_ACA_JOBS_POLICY_JSON": self._policy_json(
                            expected_image,
                            second_image=(
                                "myregistry.azurecr.us/mcp/service@sha256:"
                                + "f" * 64
                            ),
                        )
                    }
                },
                "app policy image digest mismatch",
            ),
            (
                "app policy invalid",
                {
                    "app_env_overrides": {
                        "MCP_ACA_JOBS_POLICY_JSON": '{"jobs":[]}'
                    }
                },
                "MCP_ACA_JOBS_POLICY_JSON",
            ),
            (
                "job digest env drift",
                {
                    "job_env_overrides": {
                        "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": (
                            "myregistry.azurecr.us/mcp/service@sha256:"
                            + "f" * 64
                        )
                    }
                },
                "job image digest environment mismatch",
            ),
            (
                "storage url drift",
                {"job_env_overrides": {"MCP_ACA_JOBS_OUTPUT_CONTAINER_URL": "https://storage.example.com/outputs-callbacks"}},
                "storage scopes must be distinct",
            ),
        )

        for label, client_kwargs, expected_error in failure_cases:
            with self.subTest(label=label):
                client = self._verify_deployment_client(expected_image=expected_image, **client_kwargs)
                stdout = io.StringIO()
                with patch.dict(os.environ, {"EXPECTED_IMAGE_DIGEST": expected_image}, clear=False):
                    with self.assertRaisesRegex(RuntimeError, re.escape(expected_error)):
                        module.verify_deployment(
                            run=lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(base_env), returncode=0),
                            credential_factory=lambda: object(),
                            client_factory=lambda credential, subscription_id, client=client: client,
                            stdout=stdout,
                        )
                self.assertEqual(stdout.getvalue(), "")

    def test_built_image_runs_both_entrypoint_help_commands(self) -> None:
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("docker is not available")

        with tempfile.TemporaryDirectory(prefix="foundry-mcp-aca-jobs-build-", dir=pathlib.Path.cwd()) as temp_dir:
            context = pathlib.Path(temp_dir)
            shutil.copy2(self._template_dir() / "Dockerfile", context / "Dockerfile")
            shutil.copy2(self._template_dir() / "pyproject.toml", context / "pyproject.toml")
            shutil.copy2(self._template_dir() / "uv.lock", context / "uv.lock")
            shutil.copytree(self._reference_app_dir(), context / "app")

            build = subprocess.run(
                [docker, "build", "--progress=plain", "-t", "foundry-mcp-aca-jobs:test", str(context)],
                check=False,
                capture_output=True,
                text=True,
            )
            if build.returncode != 0:
                blocker = self._docker_blocker_excerpt(
                    build.stdout + "\n" + build.stderr,
                )
                if blocker is not None:
                    blocker_kind, _, blocker_body = blocker.partition("\n")
                    if blocker_kind == "docker-daemon":
                        self.skipTest("docker daemon unavailable:\n" + blocker_body)
                    if blocker_kind == "docker-network":
                        self.skipTest("docker network transport unavailable:\n" + blocker_body)
                self.fail(
                    "docker build failed for a reason other than the known daemon/network blockers:\n"
                    f"stdout:\n{build.stdout}\n"
                    f"stderr:\n{build.stderr}"
                )

            uid = subprocess.run(
                [docker, "run", "--rm", "foundry-mcp-aca-jobs:test", "id", "-u"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertNotEqual(uid, "0", "built image must run as a non-root user")

            server_help = subprocess.run(
                [docker, "run", "--rm", "foundry-mcp-aca-jobs:test", "python", "-m", "app.mcp_server", "--help"],
                check=True,
                capture_output=True,
                text=True,
            )
            worker_help = subprocess.run(
                [docker, "run", "--rm", "foundry-mcp-aca-jobs:test", "python", "-m", "app.job_worker", "--help"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("usage:", server_help.stdout.lower())
            self.assertIn("usage:", worker_help.stdout.lower())

    def test_docker_blocker_classifier_skips_only_daemon_unavailability(self) -> None:
        daemon_output = (
            "Error response from daemon: Cannot connect to the Docker daemon "
            "at unix:///var/run/docker.sock. Is the docker daemon running?"
        )

        self.assertTrue(self._docker_blocker_excerpt(daemon_output).startswith("docker-daemon"))

    def test_docker_blocker_classifier_rejects_missing_package_versions(self) -> None:
        package_output = (
            "ERROR: Could not find a version that satisfies the requirement fastmcp==4.0.1 "
            "(from versions: none)\nERROR: No matching distribution found for fastmcp==4.0.1"
        )

        self.assertIsNone(self._docker_blocker_excerpt(package_output))

    def test_docker_blocker_classifier_allows_dns_only_with_env(self) -> None:
        network_outputs = (
            (
                "WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, "
                "status=None)) after connection broken by 'NewConnectionError("
                "<urllib3.connection.HTTPSConnection object at 0x0>: "
                "Failed to establish a new connection: [Errno -2] Temporary failure in name resolution'"
            ),
            (
                "Failed to download pydantic-core: request failed after 3 retries; "
                "client error (Connect): tls handshake eof"
            ),
        )

        previous = os.environ.get("ALLOW_NETWORK_DOCKER_SKIP")
        try:
            os.environ.pop("ALLOW_NETWORK_DOCKER_SKIP", None)
            for output in network_outputs:
                with self.subTest(skip_allowed=False, output=output):
                    self.assertIsNone(self._docker_blocker_excerpt(output))
            os.environ["ALLOW_NETWORK_DOCKER_SKIP"] = "1"
            for output in network_outputs:
                with self.subTest(skip_allowed=True, output=output):
                    classified = self._docker_blocker_excerpt(output)
                    self.assertIsNotNone(classified)
                    self.assertTrue(classified.startswith("docker-network"))
        finally:
            if previous is None:
                os.environ.pop("ALLOW_NETWORK_DOCKER_SKIP", None)
            else:
                os.environ["ALLOW_NETWORK_DOCKER_SKIP"] = previous


if __name__ == "__main__":
    unittest.main()
