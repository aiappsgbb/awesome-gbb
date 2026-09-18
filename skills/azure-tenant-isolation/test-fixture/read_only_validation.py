"""Manual read-only fixture: existing isolated session and one approved RG read.

No login, account selection, config creation, resource writes or retries.
Private evidence must be stored outside the repository.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("alias", "tenant-id", "subscription-id", "subscription-name",
                     "resource-group", "evidence-dir"):
        parser.add_argument("--" + argument, required=True)
    args = parser.parse_args()
    skill = Path(__file__).resolve().parents[1]
    repository = skill.parents[1]
    evidence_dir = Path(args.evidence_dir).expanduser().resolve()
    if evidence_dir == repository or repository in evidence_dir.parents:
        parser.error("Private evidence must be outside the repository")
    if not evidence_dir.is_dir():
        parser.error("Evidence directory must already exist")

    index = Path(os.environ.get("AZURE_TENANT_INDEX") or "~/.azure-tenants/index.json").expanduser()
    tenant = json.loads(index.read_text())["tenants"][args.alias]
    if tenant["tenant_id"] != args.tenant_id:
        parser.error("Index tenant differs from approved target")
    allowed = tenant.get("allowed_subscriptions", [])
    if not isinstance(allowed, list):
        parser.error("Invalid allowed_subscriptions")
    allowed = allowed or [tenant["default_subscription"]]
    if args.subscription_name not in allowed and args.subscription_id not in allowed:
        parser.error("Approved subscription is not allowlisted")
    if tenant["default_subscription"] in (args.subscription_name, args.subscription_id):
        parser.error("Regression fixture requires an allowed non-default target")
    for variable, field, root in (
        ("AZURE_CONFIG_DIR", "config_dir", ".azure-tenants"),
        ("AZD_CONFIG_DIR", "azd_config_dir", ".azd-tenants"),
    ):
        expected = Path(tenant.get(field) or f"~/{root}/{args.alias}").expanduser().resolve()
        configured = os.environ.get(variable)
        if not configured or Path(configured).expanduser().resolve() != expected or not expected.is_dir():
            parser.error(f"{variable} must match an existing approved isolated directory")

    helper = skill / "references/bash/bootstrap.sh"
    command = r'''
set -euo pipefail
source "$1" "$2" >&2
[ "$ACTUAL_TENANT" = "$3" ] || { echo "Explicit tenant mismatch" >&2; exit 1; }
[ "$ACTUAL_SUB_ID" = "$4" ] || { echo "Explicit subscription ID mismatch" >&2; exit 1; }
[ "$ACTUAL_SUB" = "$5" ] || { echo "Explicit subscription name mismatch" >&2; exit 1; }
az group show --name "$6" --subscription "$4" --query '{id:id,name:name}' --output json
'''
    process = subprocess.Popen(
        ["/bin/bash", "--noprofile", "--norc", "-c", command, "read-only-fixture",
         str(helper), args.alias, args.tenant_id, args.subscription_id,
         args.subscription_name, args.resource_group],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    passed = not timed_out and process.returncode == 0
    if passed:
        response = json.loads(stdout)
        expected_id = f"/subscriptions/{args.subscription_id}/resourceGroups/{args.resource_group}"
        passed = response.get("name") == args.resource_group and response.get("id", "").lower() == expected_id.lower()
    private = {
        "target": {key: value for key, value in vars(args).items() if key != "evidence_dir"},
        "returncode": process.returncode, "timed_out": timed_out,
        "stdout": stdout, "stderr": stderr,
    }
    sanitized = {
        "result": "PASS" if passed else "FAIL",
        "scope": "existing isolated session; explicit non-default target; one authenticated resource-group read",
        "bootstrap_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "timeout_seconds": 90,
        "azure_mutations": 0,
        "login_or_account_set": 0,
    }
    for name, record in (("tenant-isolation-private.json", private),
                         ("tenant-isolation-sanitized.json", sanitized)):
        path = evidence_dir / name
        with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
            json.dump(record, output, indent=2)
            output.write("\n")
    print(json.dumps(sanitized))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
