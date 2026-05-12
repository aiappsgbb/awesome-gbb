"""threadlight-safe-check — single-file CLI for the threadlight completeness gate.

Three lifecycle phases:
  --phase design       contract: specs/manifest.json must have deployment_manifest{}
  --phase pre-deploy   manifest <-> azure.yaml + infra/main.bicep + src/<dir>/Dockerfile
  --phase post-deploy  manifest <-> az resource list + channel reachability

Drop into a pilot repo as `tests/safe_check.py` (or install as a package)
and invoke:

    python -m threadlight.safe_check --phase post-deploy

Exit codes:
    0  gate passed (gaps empty)
    1  gate failed (gaps non-empty); JSON manifest written
    2  prerequisite missing (no manifest.json, no deployment_manifest, env vars)
    3  tooling error (az auth, az not on PATH)

See SKILL.md for the full specification.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SELECTOR_TO_RESOURCE_TYPES: dict[str, list[str]] = {
    "foundry-account":  ["Microsoft.CognitiveServices/accounts"],
    "cosmos-db":        ["Microsoft.DocumentDB/databaseAccounts"],
    "ai-search":        ["Microsoft.Search/searchServices"],
    "app-insights":     ["Microsoft.Insights/components",
                         "Microsoft.OperationalInsights/workspaces"],
    "acr":              ["Microsoft.ContainerRegistry/registries"],
    "uami":             ["Microsoft.ManagedIdentity/userAssignedIdentities"],
    "aca-environment":  ["Microsoft.App/managedEnvironments"],
    "aca-mcp":          ["Microsoft.App/containerApps"],
    "aca-bot":          ["Microsoft.App/containerApps",
                         "Microsoft.BotService/botServices"],
    "aca-job":          ["Microsoft.App/jobs"],
    "workspace-ui":     ["Microsoft.App/containerApps"],
    "event-grid":       ["Microsoft.EventGrid/topics"],
    "service-bus":      ["Microsoft.ServiceBus/namespaces"],
    "key-vault":        ["Microsoft.KeyVault/vaults"],
    "storage-blob":     ["Microsoft.Storage/storageAccounts"],
    "foundry-iq-index": ["Microsoft.Search/searchServices"],
}

ACA_ROLE_KEYWORDS = {
    "aca-mcp":      "mcp",
    "aca-bot":      "bot",
    "workspace-ui": "workspace",
}

# Behavioural-check tunables (post-deploy phase)
# ------------------------------------------------------------------
# G9.1 — Placeholder image regex. ANY ACA / ACA Job container image
# matching this pattern is the result of `azd provision` running before
# `azd deploy` (or a Bicep run that didn't honor SERVICE_*_RESOURCE_EXISTS).
# It means the SPEC asked for our code but Azure is running Microsoft's
# helloworld sample. azd reports SUCCESS, evals fall apart, deadline-watcher
# silently 404s. Catch it here.
PLACEHOLDER_IMAGE_REGEX = re.compile(
    r"^mcr\.microsoft\.com/azuredocs/.*", re.IGNORECASE,
)

# G9.2 — Job execution-success window. If the last N executions of an
# ACA Job all show status=Failed, the cron is dead — even if azd deploy
# succeeded and the image is the right one. Trip the gate.
JOB_EXECUTION_WINDOW = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _az(*args: str, capture: bool = True) -> str:
    """Run `az <args>` with shell=True so `az.cmd` resolves on Windows."""
    cmd = "az " + " ".join(args)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=capture,
            text=True, check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        print(f"[ERROR] {cmd}\n        {stderr}", file=sys.stderr)
        raise SystemExit(3)
    except FileNotFoundError:
        print("[ERROR] `az` not on PATH. Install Azure CLI and re-run.",
              file=sys.stderr)
        raise SystemExit(3)


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"[ERROR] specs/manifest.json missing at {path}", file=sys.stderr)
        raise SystemExit(2)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] specs/manifest.json invalid JSON: {e}", file=sys.stderr)
        raise SystemExit(2)
    if "deployment_manifest" not in data:
        print("[ERROR] specs/manifest.json missing top-level "
              "`deployment_manifest{}` block. See threadlight-design SKILL §3.",
              file=sys.stderr)
        raise SystemExit(2)
    return data


def _print_active_context() -> None:
    """First line of output: which tenant + sub will az calls hit."""
    try:
        out = _az("account", "show", "--query", "{t:tenantId,s:name,sid:id}",
                  "-o", "json").strip()
        ctx = json.loads(out)
        print(f"[ctx] tenant={ctx['t']} sub={ctx['s']!r} sub_id={ctx['sid']}")
    except SystemExit:
        raise
    except Exception:
        print("[ctx] (az account show failed; continuing)")


# ---------------------------------------------------------------------------
# Phase 1 — design
# ---------------------------------------------------------------------------

def phase_design(manifest_path: Path, out_path: Path) -> int:
    data = _load_manifest(manifest_path)
    dm = data["deployment_manifest"]
    gaps: list[str] = []

    selectors = dm.get("module_selectors", {})
    if not selectors or not isinstance(selectors, dict):
        gaps.append("deployment_manifest.module_selectors missing or not dict")
    else:
        for k, v in selectors.items():
            if v not in ("yes", "no"):
                gaps.append(
                    f"selector {k!r}={v!r} must be 'yes' or 'no'")

    services = dm.get("services", [])
    for svc in services:
        for required_key in ("name", "host", "src"):
            if required_key not in svc:
                gaps.append(f"service entry missing {required_key!r}: {svc}")

    if selectors.get("aca-job") == "yes":
        if not dm.get("scheduled_jobs"):
            gaps.append("aca-job:yes but no scheduled_jobs[] entries")

    expected = set(dm.get("expected_resource_types", []))
    if not expected:
        gaps.append("expected_resource_types[] is empty")
    else:
        for sel, val in selectors.items():
            if val != "yes":
                continue
            for required in SELECTOR_TO_RESOURCE_TYPES.get(sel, []):
                if required not in expected:
                    gaps.append(
                        f"selector {sel!r}=yes but expected_resource_types "
                        f"is missing {required!r}")

    manifest = {
        "phase": "design",
        "checked_at": _utc_now(),
        "manifest_source": str(manifest_path),
        "selectors": selectors,
        "services_count": len(services),
        "scheduled_jobs_count": len(dm.get("scheduled_jobs", [])),
        "channels_count": len(dm.get("channels", [])),
        "expected_resource_types_count": len(expected),
        "gaps": gaps,
    }
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return _emit(out_path, gaps)


# ---------------------------------------------------------------------------
# Phase 2 — pre-deploy
# ---------------------------------------------------------------------------

def phase_predeploy(repo: Path, manifest_path: Path, out_path: Path) -> int:
    data = _load_manifest(manifest_path)
    dm = data["deployment_manifest"]
    selectors = dm.get("module_selectors", {})
    services = {s["name"]: s for s in dm.get("services", [])}
    gaps: list[str] = []

    azure_yaml = repo / "azure.yaml"
    if not azure_yaml.exists():
        gaps.append("azure.yaml missing at repo root")
        return _write_and_emit(out_path, "pre-deploy", gaps,
                               extra={"repo": str(repo)})
    azure_text = azure_yaml.read_text(encoding="utf-8")

    main_bicep = repo / "infra" / "main.bicep"
    if not main_bicep.exists():
        gaps.append("infra/main.bicep missing")
        return _write_and_emit(out_path, "pre-deploy", gaps,
                               extra={"repo": str(repo)})
    main_text = main_bicep.read_text(encoding="utf-8")

    for selector, val in selectors.items():
        if val != "yes":
            continue
        if selector == "aca-bot":
            if "project: ./src/bot" not in azure_text:
                gaps.append(
                    "aca-bot:yes but azure.yaml missing service with "
                    "project: ./src/bot")
            if "module botService" not in main_text and \
               "bot-service.bicep" not in main_text:
                gaps.append(
                    "aca-bot:yes but main.bicep missing bot-service module ref")
            if "module botApp" not in main_text and \
               not re.search(r"module\s+\w*[Bb]ot\w*\s+", main_text):
                gaps.append("aca-bot:yes but main.bicep missing bot ACA module")
            bot_dir = repo / "src" / "bot"
            for required in ("Dockerfile", "bot.py", "app.py"):
                if not (bot_dir / required).exists():
                    gaps.append(f"aca-bot:yes but src/bot/{required} missing")
            tm = bot_dir / "teams_package" / "manifest.json"
            if not tm.exists():
                gaps.append(
                    "aca-bot:yes but src/bot/teams_package/manifest.json missing")
        elif selector == "aca-mcp":
            if "project: ./src/mcp" not in azure_text:
                gaps.append(
                    "aca-mcp:yes but azure.yaml missing service with "
                    "project: ./src/mcp")
            if not (repo / "src" / "mcp" / "Dockerfile").exists():
                gaps.append("aca-mcp:yes but src/mcp/Dockerfile missing")
        elif selector == "workspace-ui":
            if "project: ./src/workspace" not in azure_text:
                gaps.append(
                    "workspace-ui:yes but azure.yaml missing service with "
                    "project: ./src/workspace")
            if not (repo / "src" / "workspace" / "Dockerfile").exists():
                gaps.append(
                    "workspace-ui:yes but src/workspace/Dockerfile missing "
                    "(static index.html-only is not 'deployed')")
        elif selector == "aca-job":
            for job in dm.get("scheduled_jobs", []):
                src = repo / job.get("src", f"src/jobs/{job['name']}")
                if not (src / "Dockerfile").exists():
                    gaps.append(
                        f"aca-job:yes but {src}/Dockerfile missing for "
                        f"job {job['name']!r}")
                if not (src / "main.py").exists():
                    gaps.append(
                        f"aca-job:yes but {src}/main.py missing for "
                        f"job {job['name']!r}")

    for bicep in (repo / "infra").glob("**/*.bicep"):
        rel = bicep.relative_to(repo / "infra")
        parts = rel.parts
        if "core" in parts or "modules" in parts or rel.name == "main.bicep":
            continue
        base = bicep.stem
        if base not in main_text and rel.as_posix() not in main_text:
            gaps.append(
                f"orphan Bicep module: infra/{rel.as_posix()} not "
                "referenced from main.bicep")

    src_dir = repo / "src"
    if src_dir.exists():
        for child in src_dir.iterdir():
            if not child.is_dir() or child.name in ("agent", "jobs", "__pycache__"):
                continue
            if child.name not in services:
                gaps.append(
                    f"orphan src folder: src/{child.name}/ has no entry in "
                    "azure.yaml services")
        jobs_dir = src_dir / "jobs"
        if jobs_dir.exists():
            for jchild in jobs_dir.iterdir():
                if not jchild.is_dir() or jchild.name == "__pycache__":
                    continue
                if jchild.name not in services:
                    gaps.append(
                        f"orphan src folder: src/jobs/{jchild.name}/ has no "
                        "entry in azure.yaml services")

    return _write_and_emit(out_path, "pre-deploy", gaps,
                           extra={"repo": str(repo)})


# ---------------------------------------------------------------------------
# Phase 3 — post-deploy
# ---------------------------------------------------------------------------

def phase_postdeploy(manifest_path: Path, out_path: Path,
                     rg: str | None) -> int:
    data = _load_manifest(manifest_path)
    dm = data["deployment_manifest"]
    selectors = {k for k, v in dm.get("module_selectors", {}).items() if v == "yes"}
    expected_types = set(dm.get("expected_resource_types", []))
    channels = dm.get("channels", [])
    scheduled_jobs = dm.get("scheduled_jobs", [])
    gaps: list[str] = []

    rg = rg or os.environ.get("AZURE_RESOURCE_GROUP")
    if not rg:
        try:
            rg = subprocess.run(
                "azd env get-value AZURE_RESOURCE_GROUP",
                shell=True, capture_output=True, text=True, check=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            rg = ""
    if not rg:
        print("[ERROR] AZURE_RESOURCE_GROUP env not set and "
              "`azd env get-value` failed. Pass --rg <name>.", file=sys.stderr)
        raise SystemExit(2)

    print(f"[ctx] resource_group={rg}")

    deployed_raw = _az("resource", "list", "-g", rg,
                       "--query", "[].{type:type,name:name}", "-o", "json")
    deployed_resources = json.loads(deployed_raw or "[]")
    deployed_types = {r["type"] for r in deployed_resources}

    acas_raw = _az("containerapp", "list", "-g", rg,
                   "--query",
                   "[].{name:name,fqdn:properties.configuration.ingress.fqdn,"
                   "image:properties.template.containers[0].image,"
                   "state:properties.runningStatus}",
                   "-o", "json")
    deployed_acas = json.loads(acas_raw or "[]")

    jobs_raw = _az("containerapp", "job", "list", "-g", rg,
                   "--query",
                   "[].{name:name,schedule:properties.configuration."
                   "scheduleTriggerConfig.cronExpression,"
                   "image:properties.template.containers[0].image}", "-o", "json")
    deployed_jobs = json.loads(jobs_raw or "[]")

    bots_raw = _az("resource", "list", "-g", rg,
                   "--resource-type", "Microsoft.BotService/botServices",
                   "-o", "json")
    deployed_bots = json.loads(bots_raw or "[]")

    missing_types = sorted(expected_types - deployed_types)
    for t in missing_types:
        gaps.append(f"missing resource type: {t}")

    for selector in selectors:
        if selector not in ACA_ROLE_KEYWORDS:
            continue
        keyword = ACA_ROLE_KEYWORDS[selector]
        if not any(keyword in a["name"].lower() for a in deployed_acas):
            gaps.append(
                f"selector {selector!r}=yes but no ACA matched name pattern "
                f"*{keyword}*")

    if "aca-bot" in selectors and not deployed_bots:
        gaps.append("aca-bot:yes but no Microsoft.BotService/botServices found")

    # ------------------------------------------------------------------
    # G9.1 — Image-probe behavioural check (image_probe_results)
    # Any deployed ACA / ACA Job whose container image matches the
    # azuredocs helloworld placeholder is a `azd provision`-only deploy
    # masquerading as a real one. azd will report SUCCESS but the SPEC
    # behaviour is missing.
    # ------------------------------------------------------------------
    image_probe_results: list[dict[str, Any]] = []
    for resource in deployed_acas + deployed_jobs:
        image = (resource.get("image") or "").strip()
        kind = "containerapp" if resource in deployed_acas else "containerapp-job"
        entry = {
            "name": resource.get("name"),
            "kind": kind,
            "image": image,
            "status": "OK",
        }
        if not image:
            entry["status"] = "no_image_reported"
            gaps.append(
                f"image-probe {kind} {resource.get('name')!r}: az returned "
                f"no image string (deploy state unknown)"
            )
        elif PLACEHOLDER_IMAGE_REGEX.match(image):
            entry["status"] = "PLACEHOLDER"
            gaps.append(
                f"image-probe {kind} {resource.get('name')!r} is running the "
                f"azuredocs helloworld placeholder ({image}). The real "
                f"application image was never promoted; run "
                f"`azd deploy <service>` for this service. See "
                f"threadlight-deploy Gotchas → fetch-container-image pattern."
            )
        image_probe_results.append(entry)

    # ------------------------------------------------------------------
    # G9.2 — Job execution-success behavioural check
    # For each deployed ACA Job, fetch the last JOB_EXECUTION_WINDOW
    # executions; trip the gate if ALL of them are status=Failed.
    # Catches silent cron rot — the deploy succeeded but the cron
    # crashes on every tick.
    # ------------------------------------------------------------------
    job_health_results: list[dict[str, Any]] = []
    for job in deployed_jobs:
        job_name = job.get("name") or ""
        if not job_name:
            continue
        try:
            execs_raw = _az(
                "containerapp", "job", "execution", "list",
                "-n", job_name, "-g", rg,
                "--query",
                f"sort_by([], &properties.startTime)[-{JOB_EXECUTION_WINDOW}:]"
                ".{name:name,status:properties.status,startTime:"
                "properties.startTime}",
                "-o", "json",
            )
            executions = json.loads(execs_raw or "[]")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            job_health_results.append({
                "name": job_name, "status": "probe_failed",
                "error": str(exc)[:200],
            })
            gaps.append(
                f"job-success probe failed for {job_name!r}: {exc} "
                f"(unable to verify last {JOB_EXECUTION_WINDOW} executions)"
            )
            continue
        statuses = [e.get("status") for e in executions]
        if not executions:
            job_health_results.append({
                "name": job_name, "status": "no_executions_yet",
                "executions": [],
            })
            continue
        all_failed = bool(statuses) and all(s == "Failed" for s in statuses)
        entry = {
            "name": job_name,
            "executions_checked": len(executions),
            "statuses": statuses,
            "status": "OK" if not all_failed else "ALL_FAILED",
        }
        if all_failed:
            gaps.append(
                f"job-success {job_name!r}: last {len(executions)} "
                f"executions ALL Failed ({', '.join(e.get('name','?') for e in executions)}). "
                f"Cron is dead even though deploy succeeded — investigate "
                f"replica logs and image entrypoint."
            )
        job_health_results.append(entry)

    # ------------------------------------------------------------------
    # G9.3 — App Insights existence behavioural check (appin_health)
    # If the SPEC declared `app-insights: yes` (or expected_resource_types
    # includes `Microsoft.Insights/components`), the post-deploy gate FAILS
    # if no AppIn resource exists in the deployed RG. Catches the silent
    # observability gap discovered after card-dispute v3 (azd up returned
    # 0 but App Insights stayed completely empty because the bicep module
    # was never composed in main.bicep). See foundry-observability skill.
    # ------------------------------------------------------------------
    appin_health_results: list[dict[str, Any]] = []
    appin_expected = (
        "app-insights" in selectors
        or "Microsoft.Insights/components" in expected_types
        or "appinsights" in selectors
    )
    if appin_expected:
        try:
            appin_raw = _az(
                "resource", "list",
                "-g", rg,
                "--resource-type", "Microsoft.Insights/components",
                "--query", "[].{name:name,id:id,kind:kind}",
                "-o", "json",
            )
            appin_resources = json.loads(appin_raw or "[]")
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            appin_health_results.append({
                "status": "probe_failed", "error": str(exc)[:200],
            })
            gaps.append(
                f"appin-existence probe failed: {exc} "
                f"(unable to verify Microsoft.Insights/components in {rg})"
            )
        else:
            if not appin_resources:
                appin_health_results.append({
                    "status": "MISSING",
                    "expected": "Microsoft.Insights/components",
                    "found_in_rg": [],
                })
                gaps.append(
                    f"appin-existence: SPEC declared app-insights but NO "
                    f"Microsoft.Insights/components resource exists in "
                    f"{rg!r}. azd up returned success but App Insights was "
                    f"never provisioned — agent traces, MCP tool calls, and "
                    f"cron logs will be silently lost. Check that "
                    f"infra/main.bicep includes app-insights.bicep (always-on). "
                    f"See foundry-observability skill for the drop-in module."
                )
            else:
                for appin in appin_resources:
                    appin_health_results.append({
                        "name": appin.get("name"),
                        "kind": appin.get("kind"),
                        "status": "OK",
                    })
    else:
        # SPEC did not declare AppIn. Record the check was skipped so the
        # auditor can see we considered it; do NOT trip the gate.
        appin_health_results.append({
            "status": "not_required_by_spec",
            "note": (
                "SPEC § 11c did not include app-insights selector AND "
                "expected_resource_types did not include "
                "Microsoft.Insights/components. Add them to enable "
                "this gate. (Threadlight default: app-insights is "
                "always-on — see foundry-observability skill.)"
            ),
        })

    # ------------------------------------------------------------------
    # G9.4 — Bot AUTHTYPE behavioural check (bot_auth_health)
    # When the SPEC declares aca-bot AND the deployed Bot Service is
    # registered as appType=UserAssignedMSI, the bot ACA's env block
    # MUST contain CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE
    # =UserManagedIdentity. Without it, the microsoft-agents-* SDK
    # falls back to ConfidentialClient flow and demands a client secret
    # the deploy never provisioned -> every real Teams message comes
    # back as HTTP 500 with AADSTS7000216 in the bot logs. The synthetic
    # _probe_teams() check returns OK_jwt_alive (JWT middleware fires
    # BEFORE outbound token acquisition), so this gap escapes channel
    # reachability. Caught it on KYC PoC v1; protecting future pilots.
    # ------------------------------------------------------------------
    bot_auth_health_results: list[dict[str, Any]] = []
    if "aca-bot" in selectors:
        for bot_svc in deployed_bots:
            bot_name = bot_svc.get("name") or ""
            try:
                bot_props_raw = _az(
                    "bot", "show", "-g", rg, "-n", bot_name,
                    "--query",
                    "{appType:properties.msaAppType,"
                    "msaAppId:properties.msaAppId}",
                    "-o", "json",
                )
                bot_props = json.loads(bot_props_raw or "{}")
            except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
                bot_auth_health_results.append({
                    "name": bot_name, "status": "probe_failed",
                    "error": str(exc)[:200],
                })
                continue
            app_type = (bot_props.get("appType") or "").strip()
            if app_type != "UserAssignedMSI":
                bot_auth_health_results.append({
                    "name": bot_name, "appType": app_type,
                    "status": "skipped_not_uami",
                })
                continue
            bot_aca = next(
                (a for a in deployed_acas if "bot" in a["name"].lower()),
                None,
            )
            if not bot_aca:
                bot_auth_health_results.append({
                    "bot_service": bot_name, "appType": app_type,
                    "status": "no_aca_matched",
                })
                gaps.append(
                    f"bot-authtype: Bot Service {bot_name!r} is "
                    f"appType=UserAssignedMSI but no ACA matched name "
                    f"pattern *bot* — cannot verify AUTHTYPE env"
                )
                continue
            try:
                env_raw = _az(
                    "containerapp", "show", "-g", rg, "-n", bot_aca["name"],
                    "--query",
                    "properties.template.containers[0].env[].{name:name,"
                    "value:value}",
                    "-o", "json",
                )
                env_vars = json.loads(env_raw or "[]")
            except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
                bot_auth_health_results.append({
                    "bot_service": bot_name, "aca": bot_aca["name"],
                    "status": "env_probe_failed", "error": str(exc)[:200],
                })
                continue
            authtype_var = next(
                (v for v in env_vars
                 if v.get("name") == "CONNECTIONS__SERVICE_CONNECTION__"
                                     "SETTINGS__AUTHTYPE"),
                None,
            )
            authtype_value = (authtype_var or {}).get("value", "")
            entry = {
                "bot_service": bot_name, "aca": bot_aca["name"],
                "appType": app_type, "authtype": authtype_value,
            }
            if authtype_value != "UserManagedIdentity":
                entry["status"] = "AUTHTYPE_MISSING_OR_WRONG"
                gaps.append(
                    f"bot-authtype {bot_aca['name']!r}: Bot Service "
                    f"{bot_name!r} is appType=UserAssignedMSI but ACA env "
                    f"CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE="
                    f"{authtype_value!r} (expected 'UserManagedIdentity'). "
                    f"Without it MSAL falls back to ConfidentialClient -> "
                    f"AADSTS7000216 on every Teams message. Patch with "
                    f"`az containerapp update --set-env-vars CONNECTIONS"
                    f"__SERVICE_CONNECTION__SETTINGS__AUTHTYPE="
                    f"UserManagedIdentity` AND fix Bicep main.bicep / "
                    f"foundry-teams-bot Bicep snippet."
                )
            else:
                entry["status"] = "OK"
            bot_auth_health_results.append(entry)

    channel_results: list[dict[str, Any]] = []
    for ch in channels:
        ch_type = ch.get("type", "").lower()
        ch_name = ch.get("name", "?")
        svc = ch.get("service", "")
        target = next((a for a in deployed_acas
                       if svc and svc in a["name"].lower()), None)
        result: dict[str, Any] = {
            "name": ch_name, "type": ch_type, "service": svc,
            "fqdn": target["fqdn"] if target else None,
            "status": "skipped",
        }
        if not target:
            result["status"] = "no_aca_matched"
            if ch_type in ("web", "teams"):
                gaps.append(f"channel {ch_name!r} ({ch_type}): no matching ACA")
        elif ch_type == "web":
            result["status"] = _probe_web(target["fqdn"], gaps, ch_name)
        elif ch_type == "teams":
            result["status"] = _probe_teams(target["fqdn"], gaps, ch_name)
        channel_results.append(result)

    job_results: list[dict[str, Any]] = []
    for job in scheduled_jobs:
        # Match deployed job by ANY token of manifest name (split on '-').
        # The Bicep convention drops descriptor suffixes (e.g. manifest
        # 'deadline-watcher' deploys as 'ca-job-deadline-{token}'),
        # so a strict substring match would false-flag.
        name_tokens = [t for t in job["name"].lower().split("-") if t]
        match = next(
            (j for j in deployed_jobs
             if any(tok in j["name"].lower() for tok in name_tokens)),
            None,
        )
        if not match:
            gaps.append(f"missing scheduled job: {job['name']}")
            job_results.append({"name": job["name"], "status": "missing"})
            continue
        if match["schedule"] != job.get("schedule"):
            gaps.append(
                f"job {job['name']} cron drift: deployed={match['schedule']!r} "
                f"expected={job.get('schedule')!r}")
            job_results.append({"name": job["name"],
                                "deployed_schedule": match["schedule"],
                                "expected_schedule": job.get("schedule"),
                                "status": "drift"})
        else:
            job_results.append({"name": job["name"],
                                "schedule": match["schedule"], "status": "OK"})

    payload = {
        "phase": "post-deploy",
        "deployed_at": _utc_now(),
        "rg": rg,
        "checked_selectors": sorted(selectors),
        "deployed_resource_types": sorted(deployed_types),
        "image_probe": image_probe_results,
        "job_health": job_health_results,
        "appin_health": appin_health_results,
        "bot_auth_health": bot_auth_health_results,
        "channels": channel_results,
        "scheduled_jobs": job_results,
        "gaps": gaps,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _emit(out_path, gaps)


def _probe_web(fqdn: str, gaps: list[str], name: str) -> str:
    if not fqdn:
        gaps.append(f"channel {name!r}: ACA has no fqdn")
        return "no_fqdn"
    try:
        with urllib.request.urlopen(f"https://{fqdn}/", timeout=10) as resp:
            if resp.status == 200:
                return "OK"
            gaps.append(f"channel {name!r}: GET / returned HTTP {resp.status}")
            return f"HTTP_{resp.status}"
    except urllib.error.HTTPError as e:
        gaps.append(f"channel {name!r}: HTTP {e.code} on GET /")
        return f"HTTP_{e.code}"
    except Exception as e:
        gaps.append(f"channel {name!r}: web probe failed: {e}")
        return "ERROR"


def _probe_teams(fqdn: str, gaps: list[str], name: str) -> str:
    """Bot is healthy when POST /api/messages returns 401 + JWT-rejection
    body (microsoft-agents SDK middleware alive)."""
    if not fqdn:
        gaps.append(f"channel {name!r}: bot ACA has no fqdn")
        return "no_fqdn"
    try:
        req = urllib.request.Request(
            f"https://{fqdn}/api/messages",
            data=b"{}", method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10):
            gaps.append(
                f"channel {name!r}: POST /api/messages returned 200 "
                "(JWT middleware NOT enforcing!)")
            return "JWT_NOT_ENFORCING"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "OK_jwt_alive"
        gaps.append(f"channel {name!r}: bot returned HTTP {e.code}")
        return f"HTTP_{e.code}"
    except Exception as e:
        gaps.append(f"channel {name!r}: bot probe failed: {e}")
        return "ERROR"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _emit(out_path: Path, gaps: list[str]) -> int:
    if gaps:
        print(f"\n[FAIL] {len(gaps)} gap(s):")
        for g in gaps:
            print(f"  - {g}")
        print(f"\n        manifest: {out_path}")
        return 1
    print(f"\n[OK] gate passed (manifest: {out_path})")
    return 0


def _write_and_emit(out_path: Path, phase: str, gaps: list[str],
                    extra: dict[str, Any] | None = None) -> int:
    payload = {"phase": phase, "checked_at": _utc_now(),
               **(extra or {}), "gaps": gaps}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _emit(out_path, gaps)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="safe-check",
        description="threadlight completeness gate (design / pre-deploy / "
                    "post-deploy)")
    parser.add_argument("--phase", required=True,
                        choices=["design", "pre-deploy", "post-deploy"])
    parser.add_argument("--manifest", default="specs/manifest.json",
                        help="Path to manifest.json (default: %(default)s)")
    parser.add_argument("--out", default="tests",
                        help="Output dir for safe-check manifest "
                             "(default: %(default)s)")
    parser.add_argument("--rg",
                        help="Override AZURE_RESOURCE_GROUP for post-deploy")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    repo = Path.cwd()
    manifest_path = (repo / args.manifest).resolve()
    out_dir = (repo / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.phase == "post-deploy":
        _print_active_context()
        out = out_dir / "postdeploy-manifest.json"
        return phase_postdeploy(manifest_path, out, args.rg)
    if args.phase == "design":
        out = out_dir / "safe-check-design-manifest.json"
        return phase_design(manifest_path, out)
    out = out_dir / "safe-check-predeploy-manifest.json"
    return phase_predeploy(repo, manifest_path, out)


if __name__ == "__main__":
    raise SystemExit(main())
