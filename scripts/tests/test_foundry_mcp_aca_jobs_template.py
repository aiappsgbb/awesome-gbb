#!/usr/bin/env python3
"""Template contract tests for foundry-mcp-aca-jobs."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import tempfile
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-mcp-aca-jobs"


class FoundryMcpAcaJobsTemplateTests(unittest.TestCase):
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
        rbac = identity + "\n" + assignments
        for token in ("appUami", "jobUami", "roleDefinition", "assignableScopes", "scope: job", "AcrPull"):
            self.assertIn(token, rbac)
        for action in (
            "Microsoft.App/jobs/read",
            "Microsoft.App/jobs/start/action",
            "Microsoft.App/jobs/execution/read",
            "Microsoft.App/jobs/executions/read",
            "Microsoft.App/jobs/stop/execution/action",
        ):
            self.assertIn(action, rbac)
        self.assertIn("ba92f5b4-2d11-453d-a403-e96b0029c9fe", rbac)
        self.assertIn("sqlRoleDefinitions/00000000-0000-0000-0000-000000000002", rbac)
        self.assertIn("dbs/${cosmosDatabaseName}/colls/${cosmosContainerName}", rbac)
        self.assertIn("scope: storageContainer", rbac)
        self.assertNotIn("Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c'", rbac)
        for forbidden in ("jobs/write", "jobs/delete", "listsecrets", "stop/multiple"):
            self.assertNotIn(forbidden, rbac)

    def test_main_module_composes_shared_digest_and_outputs_contract(self) -> None:
        main = (self._infra_dir() / "main.bicep").read_text(encoding="utf-8")
        self.assertIn("../../../azd-patterns/references/bicep/aca-job.bicep", main)
        self.assertIn("mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48", main)
        self.assertIn("allowedMcpCallerClientIds array", main)
        self.assertIn("union(allowedMcpCallerClientIds, [", " ".join(main.split()))
        self.assertIn("appName", main)
        self.assertIn("jobName", main)
        self.assertIn("fqdn", main)
        self.assertIn("appIdentity", main)
        self.assertIn("jobIdentity", main)
        self.assertIn("cosmosEndpoint", main)
        self.assertIn("storageUrl", main)
        self.assertIn("authAudience", main)
        self.assertIn("imageDigest", main)

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
