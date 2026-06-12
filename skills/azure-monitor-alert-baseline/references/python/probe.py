"""SRE-104 probe: alert baseline validation at RG scope.

Source of truth for the prose example in `../../SKILL.md § Probe Reference`.
Checks that metric alerts in a resource group meet the configured baseline
(foundry_pilot | spoke_minimum | production) for name presence and
threshold tightness.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_baseline(kind: str) -> dict:
    """Load references/baselines/{kind}.yaml relative to this file."""
    if kind not in ("foundry_pilot", "spoke_minimum", "production"):
        raise ValueError(f"unknown alert_baseline_kind: {kind}")
    baseline_path = Path(__file__).resolve().parent.parent / "baselines" / f"{kind}.yaml"
    with open(baseline_path) as f:
        return yaml.safe_load(f)


def _write_manifest(result_dict: dict) -> None:
    try:
        out_dir = Path("out")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "SRE-104.json").write_text(json.dumps(result_dict, indent=2))
    except Exception:
        # Manifest write is best-effort — never let it block the return
        pass


def probe(
    subscription_id: str,
    resource_group: str,
    alert_baseline_kind: str,
    *,
    credential=None,
) -> dict:
    """Run the SRE-104 alert baseline check and return a spec §4.3.1 dict."""
    scope_dict = {
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "alert_baseline_kind": alert_baseline_kind,
    }

    try:
        baseline = _load_baseline(alert_baseline_kind)
        baseline_rules = {rule["name"]: rule for rule in baseline.get("alert_rules", [])}

        if credential is None:
            credential = DefaultAzureCredential()

        client = MonitorManagementClient(credential, subscription_id)
        live_alerts = list(
            client.metric_alerts.list_by_resource_group(resource_group_name=resource_group)
        )

        live_by_name = {alert.name: alert for alert in live_alerts}

        observations: list[dict] = []
        for rule_name, rule in baseline_rules.items():
            if rule_name not in live_by_name:
                observations.append({
                    "kind": "missing",
                    "alert_name": rule_name,
                    "severity": rule["severity"],
                    "max_threshold": rule["max_threshold"],
                })
            else:
                live_alert = live_by_name[rule_name]
                live_threshold = None
                try:
                    criteria = live_alert.criteria
                    if criteria is not None and criteria.all_of:
                        live_threshold = criteria.all_of[0].threshold
                except Exception:
                    live_threshold = None

                if live_threshold is not None and live_threshold > rule["max_threshold"]:
                    observations.append({
                        "kind": "threshold_mismatch",
                        "alert_name": rule_name,
                        "expected": rule["max_threshold"],
                        "actual": live_threshold,
                    })

        has_problems = any(
            o["kind"] in ("missing", "threshold_mismatch") for o in observations
        )
        result_val = "needs_attention" if has_problems else "ok"

        # Confidence heuristic (controller-locked): keyed on live alert count
        confidence = 0.5 if len(live_alerts) == 0 else 1.0

        remediation_hints: list[str] = []
        if result_val != "ok":
            if any(o["kind"] == "missing" for o in observations):
                remediation_hints.append(
                    f"Define missing alerts per the '{alert_baseline_kind}' baseline"
                    f" (see references/baselines/{alert_baseline_kind}.yaml)."
                )
            if any(o["kind"] == "threshold_mismatch" for o in observations):
                remediation_hints.append(
                    f"Tighten alert thresholds to match the '{alert_baseline_kind}' baseline"
                    f" (max_threshold values)."
                )

        result = {
            "finding_id": "SRE-104",
            "scope": scope_dict,
            "result": result_val,
            "observations": observations,
            "remediation_hints": remediation_hints,
            "confidence": confidence,
            "probed_at": _utc_now_iso(),
            "error": "",
        }

        _write_manifest(result)
        return result

    except Exception as exc:
        result = {
            "finding_id": "SRE-104",
            "scope": scope_dict,
            "result": "errored",
            "observations": [],
            "remediation_hints": [],
            "confidence": 0.0,
            "probed_at": _utc_now_iso(),
            "error": f"{type(exc).__name__}: {exc}",
        }

        _write_manifest(result)
        return result
