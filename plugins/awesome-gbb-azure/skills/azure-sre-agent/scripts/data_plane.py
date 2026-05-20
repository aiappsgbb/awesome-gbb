"""
data_plane.py — Minimal SRE Agent data-plane client for awesome-gbb skills.

This is a thin helper, NOT a comprehensive SDK. It exists so other
awesome-gbb skills (Threadlight pilots, Citadel agents) can post into a
customer's running SRE Agent via documented data-plane endpoints.

Auth model (from learn.microsoft.com/en-us/azure/sre-agent/api-reference):
  - Control plane: management.azure.com  (Azure RBAC, default cred)
  - Data plane:    {agentEndpoint}        (separate token, audience https://azuresre.dev)

Usage:
    from data_plane import SREAgentClient

    c = SREAgentClient.from_arm("/subscriptions/.../agents/my-agent")
    trigger = c.create_http_trigger(name="threadlight-incident",
                                    prompt="Investigate: {{payload}}")
    print(trigger["webhook_url"])

    c.upload_knowledge("./runbooks/aks-incident-triage.md")
    c.install_plugin("./references/plugins/gbb-citadel")

CLI (for quick smoke + plugin install):
    python3 data_plane.py install-plugin --agent <arm-id> --plugin <dir>
    python3 data_plane.py upload-knowledge --agent <arm-id> --files <glob>
    python3 data_plane.py create-http-trigger --agent <arm-id> --name X --prompt 'Investigate {{payload}}'
"""

from __future__ import annotations

import argparse
import base64
import glob as _glob
import json
import os
import pathlib
import sys
from typing import Any

try:
    import requests
    from azure.identity import DefaultAzureCredential
except ImportError as e:
    print(
        f"ERR: missing dependency ({e}). Install: pip install requests azure-identity",
        file=sys.stderr,
    )
    sys.exit(2)

ARM_BASE = "https://management.azure.com"
ARM_API_VERSION = "2025-05-01-preview"
DATA_PLANE_AUDIENCE = "https://azuresre.dev"


class SREAgentClient:
    def __init__(self, arm_id: str, agent_endpoint: str | None = None) -> None:
        self.arm_id = arm_id.rstrip("/")
        self.cred = DefaultAzureCredential()
        self._arm_token: str | None = None
        self._dp_token: str | None = None
        self._endpoint = agent_endpoint

    @classmethod
    def from_arm(cls, arm_id: str) -> "SREAgentClient":
        c = cls(arm_id)
        c._endpoint = c._resolve_endpoint()
        return c

    def _arm_headers(self) -> dict[str, str]:
        if not self._arm_token:
            self._arm_token = self.cred.get_token("https://management.azure.com/.default").token
        return {"Authorization": f"Bearer {self._arm_token}", "Content-Type": "application/json"}

    def _dp_headers(self) -> dict[str, str]:
        if not self._dp_token:
            self._dp_token = self.cred.get_token(f"{DATA_PLANE_AUDIENCE}/.default").token
        return {"Authorization": f"Bearer {self._dp_token}", "Content-Type": "application/json"}

    def _resolve_endpoint(self) -> str:
        url = f"{ARM_BASE}{self.arm_id}?api-version={ARM_API_VERSION}"
        r = requests.get(url, headers=self._arm_headers(), timeout=30)
        r.raise_for_status()
        ep = r.json().get("properties", {}).get("agentEndpoint")
        if not ep:
            raise RuntimeError(f"No agentEndpoint on {self.arm_id} — agent not deployed?")
        return ep.rstrip("/")

    # ── HTTP triggers ──────────────────────────────────────────────────
    def create_http_trigger(self, *, name: str, prompt: str) -> dict[str, Any]:
        url = f"{self._endpoint}/api/v1/httptriggers/create"
        body = {"name": name, "prompt": prompt}
        r = requests.post(url, headers=self._dp_headers(), json=body, timeout=30)
        r.raise_for_status()
        return r.json()

    # ── Knowledge base (agentmemory) ───────────────────────────────────
    def upload_knowledge(self, *paths: str) -> list[dict[str, Any]]:
        url = f"{self._endpoint}/api/v1/agentmemory/upload"
        files = []
        for p in paths:
            for match in _glob.glob(p):
                files.append(("files", (os.path.basename(match), open(match, "rb"), "text/markdown")))
        if not files:
            raise RuntimeError(f"No files matched: {paths}")
        headers = self._dp_headers()
        headers.pop("Content-Type", None)
        r = requests.post(url, headers=headers, files=files, timeout=120)
        r.raise_for_status()
        return r.json()

    # ── Plugin install (control-plane sub-resources) ───────────────────
    def install_plugin(self, plugin_dir: str | pathlib.Path) -> list[dict[str, Any]]:
        pdir = pathlib.Path(plugin_dir)
        manifest = json.loads((pdir / "plugin.json").read_text())
        results: list[dict[str, Any]] = []
        for skill_dir in (pdir / "skills").iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            spec = {"name": skill_dir.name, "content": skill_md.read_text()}
            encoded = base64.b64encode(json.dumps(spec).encode()).decode()
            url = (
                f"{ARM_BASE}{self.arm_id}/skills/{skill_dir.name}"
                f"?api-version={ARM_API_VERSION}"
            )
            body = {"properties": {"value": encoded}}
            r = requests.put(url, headers=self._arm_headers(), json=body, timeout=60)
            r.raise_for_status()
            results.append({"skill": skill_dir.name, "status": r.status_code})
        return results


def _cli() -> None:
    p = argparse.ArgumentParser(description="Azure SRE Agent data-plane helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("install-plugin")
    pi.add_argument("--agent", required=True, help="ARM resource ID of the agent")
    pi.add_argument("--plugin", required=True, help="Path to plugin directory (contains plugin.json)")

    pu = sub.add_parser("upload-knowledge")
    pu.add_argument("--agent", required=True)
    pu.add_argument("--files", nargs="+", required=True, help="One or more file globs")

    pt = sub.add_parser("create-http-trigger")
    pt.add_argument("--agent", required=True)
    pt.add_argument("--name", required=True)
    pt.add_argument("--prompt", required=True)

    args = p.parse_args()
    c = SREAgentClient.from_arm(args.agent)

    if args.cmd == "install-plugin":
        out = c.install_plugin(args.plugin)
    elif args.cmd == "upload-knowledge":
        out = c.upload_knowledge(*args.files)
    elif args.cmd == "create-http-trigger":
        out = c.create_http_trigger(name=args.name, prompt=args.prompt)
    else:
        p.error(f"unknown command: {args.cmd}")
        return

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    _cli()
