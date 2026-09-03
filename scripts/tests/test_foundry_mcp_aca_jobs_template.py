#!/usr/bin/env python3
"""Template contract tests for foundry-mcp-aca-jobs."""

from __future__ import annotations

import os
import pathlib
import re
import sys
import shutil
import subprocess
import json
import tempfile
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-mcp-aca-jobs"
SKILL_DIR = SKILL / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from app.models import Policy


class FoundryMcpAcaJobsTemplateTests(unittest.TestCase):
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

    def test_dockerfile_contract_is_single_shared_runtime_image(self) -> None:
        templates = self._template_dir()
        dockerfiles = list(templates.glob("Dockerfile*"))
        self.assertEqual(
            dockerfiles,
            [templates / "Dockerfile"],
            "templates must contain exactly one Dockerfile and no variants",
        )

        dockerfile = (templates / "Dockerfile").read_text(encoding="utf-8")
        self.assertTrue(dockerfile.startswith("FROM python:3.12-slim"))
        self.assertEqual(dockerfile.count("FROM "), 1)
        self.assertIn("WORKDIR /srv", dockerfile)
        self.assertIn("COPY pyproject.toml .", dockerfile)
        self.assertIn("COPY app ./app", dockerfile)
        self.assertIn("RUN pip install --no-cache-dir .", dockerfile)
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
        for token in ("SECRET", "TOKEN", "PASSWORD", "GITHUB_TOKEN", "AZURE_CLIENT_SECRET"):
            self.assertNotIn(token, dockerfile)
        self.assertLess(dockerfile.index("COPY pyproject.toml ."), dockerfile.index("RUN pip install --no-cache-dir ."))
        self.assertLess(dockerfile.index("COPY app ./app"), dockerfile.index("RUN pip install --no-cache-dir ."))
        self.assertLess(dockerfile.index("RUN pip install --no-cache-dir ."), dockerfile.index("RUN python -m py_compile app/*.py"))
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

    def test_app_module_contract_includes_auth_and_health(self) -> None:
        app = (self._infra_dir() / "app.bicep").read_text(encoding="utf-8")
        normalized = " ".join(app.split())
        self.assertIn("resource app 'Microsoft.App/containerApps@", app)
        self.assertIn("external: true", app)
        self.assertIn("targetPort: 8080", app)
        self.assertIn("transport: 'http'", app)
        self.assertIn("allowInsecure: false", app)
        self.assertIn("image: imageDigest", app)
        self.assertIn("command: [ 'python' '-m' 'app.mcp_server' ]", normalized)
        self.assertIn("MCP_ACA_JOBS_AUTH_MODE", app)
        self.assertIn("aca-easy-auth", app)
        self.assertIn("authConfigs@2025-01-01", app)
        self.assertIn("unauthenticatedClientAction: 'Return401'", app)
        self.assertIn("clientId: authClientId", app)
        self.assertIn("allowedAudiences", app)
        self.assertIn("environment().authentication.loginEndpoint", app)
        self.assertIn("allowedMcpCallerClientIds", app)
        self.assertIn("livenessProbe", app)
        self.assertIn("startupProbe", app)

    def test_cosmos_module_contract_is_keyless_serverless_with_control_container(self) -> None:
        cosmos = (self._infra_dir() / "cosmos.bicep").read_text(encoding="utf-8")
        normalized = " ".join(cosmos.split())
        self.assertIn("Microsoft.DocumentDB/databaseAccounts@", cosmos)
        self.assertIn("EnableServerless", cosmos)
        self.assertIn("disableLocalAuth: true", cosmos)
        self.assertIn("Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15", cosmos)
        self.assertIn("Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15", cosmos)
        self.assertIn("paths: [ '/ownerScope' ]", normalized)
        self.assertIn("paths: [ '/idempotencyKeyHash' ]", normalized)
        self.assertNotIn("COSMOS_AUTH_KEY", cosmos)
        self.assertIn("environment().suffixes.storage", (self._infra_dir() / "main.bicep").read_text(encoding="utf-8"))

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
        self.assertIn("var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", identity)
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
        self.assertIn("@maxLength(53)", main)
        self.assertIn("var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", main)
        self.assertIn("callbackStorageContainerUrl", main)
        self.assertIn("var storageHost = '${storageAccountName}.${environment().suffixes.storage}'", main)
        self.assertIn("var effectiveResultHosts = union(resultHosts, [storageHost])", main)

        self.assertIn("var authAudience = 'api://${authClientId}'", main)
        self.assertIn("callbackConfig.authMode == 'managed_identity' ? 'https://${appName}.${managedEnvironment.properties.defaultDomain}/callbacks/jobs' : callbackConfig.externalCallbackUrl", normalized)
        self.assertIn("auth_mode: callbackConfig.authMode", main)
        self.assertIn("ops: callbackPolicy", main)
        self.assertIn("callbackConfig.authMode == 'managed_identity' ? [", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_AUDIENCE'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_VAULT_URL'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_SECRET_NAME'", main)
        self.assertIn("name: 'MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID'", main)
        self.assertIn("value: authAudience", main)
        self.assertIn("value: callbackConfig.callbackSecretName", main)
        self.assertIn("value: identities.outputs.jobUamiPrincipalId", main)
        self.assertIn("environment().suffixes.keyvaultDns", main)
        self.assertIn("callbackConfig.authMode == 'key_vault' ? callbackConfig.keyVaultName : ''", normalized)
        self.assertIn("callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", main)

        for required in (
            "AZURE_CLIENT_ID",
            "AZURE_SUBSCRIPTION_ID",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT",
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
            "module app",
            "module job",
            "module jobOperator",
        ]
        positions = [main.index(marker) for marker in module_order]
        self.assertEqual(positions, sorted(positions), msg=f"unexpected module order: {module_order}")
        self.assertIn("dependsOn: [\n    preRuntimeRbac\n  ]", main)
        self.assertIn("dependsOn: [\n    app\n    preRuntimeRbac\n  ]", main)

        identity_rbac = (self._infra_dir() / "identity-rbac.bicep").read_text(encoding="utf-8")
        self.assertIn("keyVaultName: callbackConfig.authMode == 'key_vault' ? callbackConfig.keyVaultName : ''", main)
        self.assertIn("keyVaultName: keyVaultName", identity_rbac)
        self.assertIn("if (!empty(keyVaultName))", (self._infra_dir() / "identity-rbac" / "assignments.bicep").read_text(encoding="utf-8"))

    def test_callback_config_bicepparam_variants_compile_and_invalid_key_vault_is_rejected(self) -> None:
        managed_identity_params = """using './main.bicep'

param resourceGroupName = 'rg-jobs'
param location = 'swedencentral'
param acrName = 'acr-jobs'
param environmentName = 'env-jobs'
param storageAccountName = 'storagejobs'
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
        for source in files:
            with self.subTest(source=source.name):
                result = subprocess.run(
                    [
                        "az",
                        "bicep",
                        "build",
                        "--file",
                        str(source),
                        "--outfile",
                        str(source.with_suffix(".json")),
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
        self.assertIn("allowedMcpCallerClientIds array", main)
        self.assertRegex(
            normalized,
            r"allowedMcpCallerClientIds:\s*union\(allowedMcpCallerClientIds,\s*\[\s*identities\.outputs\.jobUamiClientId\s*\]\)",
        )
        self.assertIn("param outputStorageContainerName string", main)
        self.assertIn("@maxLength(53)", main)
        self.assertIn("var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'", main)
        self.assertNotIn("param storageContainerName string", main)
        self.assertIn("output outputStorageContainerUrl string", main)
        self.assertIn("output callbackStorageContainerUrl string", main)
        self.assertIn("/${outputStorageContainerName}", main)
        self.assertIn("/${callbackStorageContainerName}", main)
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
        policy = Policy(
            input_hosts={"input.example.com"},
            result_hosts={"results.example.com", "storagejobs.blob.core.windows.net"},
        )

        approved = policy.validate_result("https://storagejobs.blob.core.windows.net/outputs")
        self.assertEqual(str(approved), "https://storagejobs.blob.core.windows.net/outputs")

    def test_source_modules_expose_both_helpable_clis(self) -> None:
        server_source = (self._reference_app_dir() / "mcp_server.py").read_text(encoding="utf-8")
        worker_source = (self._reference_app_dir() / "job_worker.py").read_text(encoding="utf-8")

        self.assertIn('argparse.ArgumentParser(description="Run the foundry-mcp-aca-jobs MCP server.")', server_source)
        self.assertIn('argparse.ArgumentParser(description="Run the foundry-mcp-aca-jobs ACA Job worker.")', worker_source)
        self.assertIn("def main(", server_source)
        self.assertIn("def main(", worker_source)
        self.assertIn("raise SystemExit(main())", server_source)
        self.assertIn("raise SystemExit(main())", worker_source)

    def test_built_image_runs_both_entrypoint_help_commands(self) -> None:
        docker = shutil.which("docker")
        if docker is None:
            self.skipTest("docker is not available")

        with tempfile.TemporaryDirectory(prefix="foundry-mcp-aca-jobs-build-", dir=pathlib.Path.cwd()) as temp_dir:
            context = pathlib.Path(temp_dir)
            shutil.copy2(self._template_dir() / "Dockerfile", context / "Dockerfile")
            shutil.copy2(self._template_dir() / "pyproject.toml", context / "pyproject.toml")
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
        dns_output = (
            "WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, "
            "status=None)) after connection broken by 'NewConnectionError("
            "<urllib3.connection.HTTPSConnection object at 0x0>: "
            "Failed to establish a new connection: [Errno -2] Temporary failure in name resolution'"
        )

        self.assertIsNone(self._docker_blocker_excerpt(dns_output))

        previous = os.environ.get("ALLOW_NETWORK_DOCKER_SKIP")
        os.environ["ALLOW_NETWORK_DOCKER_SKIP"] = "1"
        try:
            self.assertTrue(self._docker_blocker_excerpt(dns_output).startswith("docker-network"))
        finally:
            if previous is None:
                os.environ.pop("ALLOW_NETWORK_DOCKER_SKIP", None)
            else:
                os.environ["ALLOW_NETWORK_DOCKER_SKIP"] = previous


if __name__ == "__main__":
    unittest.main()
