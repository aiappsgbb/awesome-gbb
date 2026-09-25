"""Canonical hosted profile selection and read-only artifact provenance.

Source of truth for `../../SKILL.md § Deployment preflight`.
No Azure calls, installation, account switching, or automatic migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REFERENCES = Path(__file__).resolve().parents[1]
CONTRACT = REFERENCES / "hosted-contract.json"
SUPPORTED_CONTRACT_VERSION = "1.0.0"


class ContractError(ValueError):
    pass


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("Duplicate contract key")
        result[key] = value
    return result


def load_contract() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if (type(contract.get("schema_version")) is not int or contract["schema_version"] != 1
            or contract.get("contract_version") != SUPPORTED_CONTRACT_VERSION
            or not isinstance(contract.get("profiles"), dict)):
        raise ContractError("Unsupported hosted contract schema")
    return contract


def select_profile(name: str, observed_consumer: dict) -> dict:
    contract = load_contract()
    if not isinstance(name, str):
        raise ContractError("Select an explicit hosted profile")
    profile = contract["profiles"].get(name)
    if not isinstance(profile, dict) or profile.get("status") != "supported":
        raise ContractError("Unsupported or migration-only profile; explicit compatibility review required")
    if not isinstance(observed_consumer, dict) or any(
        observed_consumer.get(key) != value for key, value in profile["consumer"].items()
    ):
        raise ContractError("Observed azd/extension pair does not match the selected contract")
    return profile


def validate_service(service: dict, profile: dict) -> None:
    """Validate the selected template shape, not a universal azd schema."""
    manifest = profile["manifest"]
    if not isinstance(service, dict) or service.get("host") != "azure.ai.agent" or service.get("kind") != "hosted":
        raise ContractError("Expected a hosted agent service")
    if "codeConfiguration" in service or "identity" in service:
        raise ContractError("This profile does not support code deploy or a user-defined agent identity")
    if "env" in service or "environment_variables" in service:
        raise ContractError("Mixed environment schemas; review the actual consumer before migration")
    entries = service.get(manifest["environment_key"])
    if not isinstance(entries, list):
        raise ContractError("Expected the selected consumer's name/value environment list")
    names = set()
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {"name", "value"}
                or not isinstance(entry["name"], str) or not entry["name"]
                or not isinstance(entry["value"], str) or entry["name"] in names):
            raise ContractError("Invalid or duplicate user environment entry")
        name = entry["name"]
        if (name.startswith(tuple(profile["reserved_environment_prefixes"]))
                or name in profile["reserved_environment_names"]):
            raise ContractError("User environment shadows a platform-reserved name")
        names.add(name)
    protocols = service.get("protocols")
    if protocols != [{"protocol": manifest["protocol"], "version": manifest["protocol_version"]}]:
        raise ContractError("Protocol does not match the selected runtime profile")


def provenance(references: Path = REFERENCES) -> dict:
    """Hash actual files, including helpers, rather than trusting version labels."""
    references = references.resolve()
    contract_path = references / "hosted-contract.json"
    contract = json.loads(contract_path.read_text(), object_pairs_hook=unique_keys)
    profile = contract["profiles"]["maf-container-beta14"]
    paths = [
        "hosted-contract.json", profile["manifest"]["path"], profile["runtime_dependencies"],
        *profile["runtime_sources"], "python/hosted_contract.py",
        "python/deploy_preflight.py", "python/private_bootstrap.py", "python/hosted_smoke.py",
        "python/operation_evidence.py", "python/version_rollout.py",
    ]
    hashes = {}
    for name in paths:
        relative = Path(name)
        path = references / relative
        if (relative.is_absolute() or ".." in relative.parts or not path.is_file()
                or path.is_symlink() or not path.resolve().is_relative_to(references)):
            raise ContractError("Missing or unsafe canonical artifact path")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"contract_version": contract["contract_version"], "sha256": hashes}


def require_adoption(reviewed: dict, adopted: dict) -> None:
    if (not isinstance(reviewed, dict) or not isinstance(adopted, dict)
            or not reviewed.get("sha256") or reviewed != adopted):
        raise ContractError("Adopted helper/template bytes differ from the reviewed contract")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, default=REFERENCES)
    args = parser.parse_args()
    try:
        result = provenance(args.references)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
