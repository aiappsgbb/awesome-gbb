#!/usr/bin/env python3
"""Template contract tests for foundry-mcp-aca-jobs."""

from __future__ import annotations

import pathlib
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-mcp-aca-jobs"


class FoundryMcpAcaJobsTemplateTests(unittest.TestCase):
    def test_pyproject_dependencies_match_canonical_stack(self) -> None:
        template = SKILL / "templates" / "pyproject.toml"
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


if __name__ == "__main__":
    unittest.main()
