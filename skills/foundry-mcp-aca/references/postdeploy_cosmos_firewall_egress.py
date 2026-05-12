"""postdeploy_cosmos_firewall_egress.py

Auto-discover the cosmos-mcp ACA's egress IP and patch Cosmos firewall.

The Azure ACA managed environment NATs all egress through a regional public IP
that is NOT covered by Cosmos `networkAclBypass: AzureServices`. Verified KYC
PoC swedencentral, May 2026: even with `AzureServices` bypass enabled, every
ACA -> Cosmos write returns `Forbidden -- Request originated from IP X.X.X.X
through public internet`.

This script is the closing piece to make `azd up` truly hands-off for any
process that uses Cosmos via an MCP ACA. It:

  1. Reads the cosmos-mcp ACA name from azd env (or argv).
  2. Polls the ACA's recent logs for the Cosmos Forbidden error pattern.
  3. Extracts the egress IP from the error message.
  4. Patches Cosmos firewall via REST PATCH (CLI does not expose
     `--enable-public-network`).
  5. Polls Cosmos `provisioningState` until `Succeeded`.

Wire as the LAST step of `azure.yaml` postdeploy:

    hooks:
      postdeploy:
        shell: pwsh
        run: |
          cd infra/scripts && uv sync --frozen
          uv run postdeploy.py
          uv run postdeploy_cosmos_firewall_egress.py    # this script

Requires:
  - az CLI logged in
  - azd CLI logged in (uses `azd env get-value`)

Environment vars (resolved in priority order):
  AZURE_RESOURCE_GROUP, AZURE_COSMOS_ACCOUNT_NAME, AZURE_SUBSCRIPTION_ID -- from azd env
  COSMOS_MCP_ACA_NAME -- defaults to first ACA in RG with name matching '*cosmos-mcp*'

Idempotent: if the IP is already in `ipRules`, returns OK without patching.
Bounded: max ~12 minutes total wait time.
"""

from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import time

POLL_LOG_ATTEMPTS = 30
POLL_LOG_SLEEP_S = 10
POLL_PROV_ATTEMPTS = 30
POLL_PROV_SLEEP_S = 15

IP_PATTERN = re.compile(
    r"originated from IP (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
)


def sh(cmd: list[str], check: bool = True) -> str:
    """Run a shell command, return stdout. Raise on non-zero unless check=False."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(f"FAIL: {' '.join(cmd)}\n{r.stderr}\n")
        sys.exit(r.returncode)
    return r.stdout.strip()


def azd_env(key: str) -> str:
    return sh(["azd", "env", "get-value", key])


def find_cosmos_mcp_aca(rg: str) -> str:
    if v := os.environ.get("COSMOS_MCP_ACA_NAME"):
        return v
    out = sh([
        "az", "containerapp", "list", "-g", rg,
        "--query", "[?contains(name, 'cosmos-mcp') || contains(name, 'cosmos_mcp')].name",
        "-o", "json",
    ])
    names = json.loads(out)
    if not names:
        raise SystemExit(f"No ACA matching *cosmos-mcp* in RG {rg}.")
    return names[0]


def discover_egress_ip(rg: str, aca: str) -> str | None:
    """Poll ACA logs for the Cosmos Forbidden error and extract the egress IP."""
    for attempt in range(1, POLL_LOG_ATTEMPTS + 1):
        out = sh([
            "az", "containerapp", "logs", "show",
            "-g", rg, "-n", aca,
            "--tail", "200", "--type", "console",
        ], check=False)
        m = IP_PATTERN.search(out)
        if m:
            ip = m.group(1)
            print(f"[discover] attempt={attempt} found egress IP: {ip}")
            return ip
        print(f"[discover] attempt={attempt} no egress IP in logs yet, waiting {POLL_LOG_SLEEP_S}s...")
        time.sleep(POLL_LOG_SLEEP_S)
    print("[discover] gave up after 5 minutes -- no egress IP found in cosmos-mcp logs.")
    print("           This usually means: (a) the agent has not yet invoked Cosmos, or")
    print("           (b) Cosmos firewall is already open (no Forbidden errors).")
    return None


def patch_cosmos_firewall(sub: str, rg: str, account: str, ip: str) -> None:
    """REST PATCH Cosmos to enable public access + add IP to ipRules. Idempotent."""
    cur = sh([
        "az", "cosmosdb", "show", "-g", rg, "-n", account,
        "--query", "{publicNetworkAccess:publicNetworkAccess,ipRules:ipRules}",
        "-o", "json",
    ])
    state = json.loads(cur)
    existing_ips = {r["ipAddressOrRange"] for r in (state.get("ipRules") or [])}
    if state.get("publicNetworkAccess") == "Enabled" and ip in existing_ips:
        print(f"[patch] Cosmos already has publicNetworkAccess=Enabled and ipRules contains {ip} -- no-op.")
        return

    new_ips = sorted(existing_ips | {ip})
    body = {
        "properties": {
            "publicNetworkAccess": "Enabled",
            "ipRules": [{"ipAddressOrRange": x} for x in new_ips],
        }
    }
    body_path = ".cosmos-fw-patch.json"
    with open(body_path, "w", encoding="ascii") as f:
        json.dump(body, f)

    print(f"[patch] adding {ip} to Cosmos ipRules (will become {new_ips})...")
    sh([
        "az", "rest", "--method", "PATCH",
        "--url", (
            f"https://management.azure.com/subscriptions/{sub}"
            f"/resourceGroups/{rg}"
            f"/providers/Microsoft.DocumentDB/databaseAccounts/{account}"
            f"?api-version=2024-12-01-preview"
        ),
        "--body", f"@{body_path}",
        "--query", "properties.provisioningState", "-o", "tsv",
    ])

    for attempt in range(1, POLL_PROV_ATTEMPTS + 1):
        out = sh([
            "az", "cosmosdb", "show", "-g", rg, "-n", account,
            "--query", "{prov:provisioningState,n:length(ipRules)}", "-o", "json",
        ])
        st = json.loads(out)
        print(f"[patch] poll[{attempt}] prov={st['prov']} ipRulesCount={st['n']}")
        if st["prov"] == "Succeeded" and st["n"] >= len(new_ips):
            print(f"[patch] DONE -- Cosmos firewall now allows {len(new_ips)} IP(s) including {ip}.")
            try:
                os.remove(body_path)
            except OSError:
                pass
            return
        time.sleep(POLL_PROV_SLEEP_S)

    raise SystemExit("[patch] Cosmos firewall patch did not converge within 7.5 minutes.")


def main() -> int:
    rg = os.environ.get("AZURE_RESOURCE_GROUP") or azd_env("AZURE_RESOURCE_GROUP")
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID") or azd_env("AZURE_SUBSCRIPTION_ID")
    account = os.environ.get("AZURE_COSMOS_ACCOUNT_NAME") or azd_env("AZURE_COSMOS_ACCOUNT_NAME")

    aca = find_cosmos_mcp_aca(rg)
    print(f"[init] subscription={sub}")
    print(f"[init] resource_group={rg}")
    print(f"[init] cosmos_account={account}")
    print(f"[init] cosmos_mcp_aca={aca}")

    ip = discover_egress_ip(rg, aca)
    if not ip:
        print("[done] No firewall patch needed (or could not auto-discover).")
        return 0

    patch_cosmos_firewall(sub, rg, account, ip)
    print("[done] Cosmos firewall is now ACA-friendly. Re-run the eval/smoke now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
