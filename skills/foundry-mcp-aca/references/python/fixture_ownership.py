"""Canonical exact-app ownership and cleanup for the MCP ACA CI fixture.

Source of truth for `../../SKILL.md § Option C: Custom ACA`.
No resource-group, registry, image, environment, identity or deployment deletion
is implemented. Unproven image/deployment custody is an explicit residual.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


class OwnershipError(RuntimeError):
    pass


class UnclassifiedNotFound(OwnershipError):
    """A 404 that is not yet an authoritative ARM absence response."""


@dataclass(frozen=True)
class Scope:
    run_id: str
    subscription: str
    tenant: str
    resource_group: str
    app_name: str
    registry: str

    def validate(self):
        for value in (self.run_id, self.subscription, self.tenant):
            if str(uuid.UUID(value)) != value.lower():
                raise OwnershipError("Expected canonical run/subscription/tenant UUID")
        if not re.fullmatch(r"[A-Za-z0-9_.()-]{1,90}", self.resource_group):
            raise OwnershipError("Invalid approved resource group")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}[a-z0-9]", self.app_name):
            raise OwnershipError("Invalid app name")
        if not re.fullmatch(r"[a-z0-9]+\.azurecr\.io", self.registry):
            raise OwnershipError("Invalid approved registry")

    @property
    def group_id(self):
        return f"/subscriptions/{self.subscription}/resourceGroups/{self.resource_group}"

    @property
    def app_id(self):
        return f"{self.group_id}/providers/Microsoft.App/containerApps/{self.app_name}"


class Arm:
    def __init__(self, scope: Scope, *, runner=subprocess.run, opener=urlopen):
        self.scope, self.runner, self.opener = scope, runner, opener
        self.token = None

    def _az(self, args):
        try:
            result = self.runner(
                ["az", *args, "--subscription", self.scope.subscription],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OwnershipError(f"CLI unavailable: {type(exc).__name__}") from exc
        if result.returncode:
            raise OwnershipError("Scoped Azure CLI command failed; no absence inferred")
        return result.stdout

    def verify_context(self):
        context = json.loads(self._az(["account", "show", "--output", "json"]))
        if (
            context.get("id", "").lower() != self.scope.subscription.lower()
            or context.get("tenantId", "").lower() != self.scope.tenant.lower()
        ):
            raise OwnershipError("Approved subscription/tenant mismatch")

    def request(self, method, resource_id, *, etag=None):
        if method not in ("GET", "DELETE"):
            raise OwnershipError("Unsupported fixture operation")
        if resource_id not in (self.scope.group_id, self.scope.app_id):
            raise OwnershipError("Resource outside exact fixture scope")
        if method == "DELETE":
            if resource_id != self.scope.app_id:
                raise OwnershipError("Only the inventoried app may be deleted")
            self.verify_context()
        if self.token is None:
            self.token = self._az([
                "account", "get-access-token", "--resource", "https://management.azure.com/",
                "--query", "accessToken", "--output", "tsv",
            ]).strip()
            if not self.token:
                raise OwnershipError("Empty ARM token")
        api = "2024-03-01" if resource_id == self.scope.app_id else "2022-09-01"
        headers = {"Authorization": "Bearer " + self.token}
        if etag:
            headers["If-Match"] = etag
        request = Request(
            f"https://management.azure.com{resource_id}?api-version={api}",
            method=method, headers=headers,
        )
        try:
            with self.opener(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            try:
                code = json.loads(exc.read()).get("error", {}).get("code")
            except (ValueError, AttributeError):
                code = None
            if exc.code == 404 and code in ("ResourceNotFound", "ResourceGroupNotFound"):
                return None
            if exc.code == 404:
                raise UnclassifiedNotFound("ARM HTTP 404; absence not established") from exc
            raise OwnershipError(f"ARM HTTP {exc.code}; absence not established") from exc
        except (URLError, TimeoutError) as exc:
            raise OwnershipError(f"ARM transport failure: {type(exc).__name__}") from exc


def _write(path: Path, state, *, create=False):
    if path.is_symlink():
        raise OwnershipError("Refusing symlinked inventory/report")
    if create:
        with path.open("x", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            json.dump(state, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(state, stream, indent=2)
        temporary.replace(path)


def report(path: Path, state, scope: Scope):
    raw = json.dumps(state)
    for value, placeholder in (
        (scope.subscription, "<approved-subscription>"),
        (scope.tenant, "<approved-tenant>"),
        (scope.resource_group, "<approved-resource-group>"),
        (scope.registry, "<approved-registry>"),
    ):
        raw = re.sub(re.escape(value), placeholder, raw, flags=re.IGNORECASE)
    exported = json.loads(raw)
    exported["scope_sha256"] = hashlib.sha256(json.dumps({
        "subscription": scope.subscription, "tenant": scope.tenant,
        "resource_group": scope.resource_group, "registry": scope.registry,
    }, sort_keys=True).encode()).hexdigest()
    _write(path, exported)


def load(path: Path, scope: Scope):
    scope.validate()
    if path.is_symlink() or not path.is_file():
        raise OwnershipError("Missing or unsafe ownership inventory; no deletion authorized")
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise OwnershipError("Malformed ownership inventory")
    expected = {
        "schema": 1, "run_id": scope.run_id, "subscription": scope.subscription,
        "tenant": scope.tenant, "resource_group": scope.resource_group,
        "app_name": scope.app_name, "app_id": scope.app_id, "registry": scope.registry,
    }
    if any(state.get(key) != value for key, value in expected.items()):
        raise OwnershipError("Inventory belongs to a different run or approved scope")
    if state.get("absent_before") is not True:
        raise OwnershipError("No pre-create absence proof")
    return state


def prepare(path: Path, scope: Scope, arm: Arm):
    scope.validate()
    if path.exists() or path.is_symlink():
        raise OwnershipError("Prior ownership inventory exists; reconcile it, never replay deployment")
    arm.verify_context()
    group = arm.request("GET", scope.group_id)
    if (
        not isinstance(group, dict)
        or not isinstance(group.get("id"), str)
        or group["id"].casefold() != scope.group_id.casefold()
    ):
        raise OwnershipError("Approved shared resource group must already exist")
    if arm.request("GET", scope.app_id) is not None:
        raise OwnershipError("App already exists; never adopt or delete it")
    state = {
        "schema": 1, **scope.__dict__, "app_id": scope.app_id,
        "absent_before": True, "absence_checked_at": datetime.now(timezone.utc).isoformat(),
        "owner": "this CI fixture run", "expiry": "end of this invocation",
        "deploy_started": False, "app_receipts": [], "cleanup_state": "prepared",
        "cleanup_complete": False, "residuals": [],
    }
    _write(path, state, create=True)
    return state


def start(path: Path, scope: Scope):
    state = load(path, scope)
    if state["deploy_started"]:
        raise OwnershipError("Deployment already attempted; reconcile instead of replaying")
    state["deploy_started"] = True
    state["cleanup_state"] = "deployment_outcome_pending"
    _write(path, state)
    return state


def _receipt(state, app, scope):
    if (
        not state["deploy_started"]
        or not isinstance(app, dict)
        or not isinstance(app.get("id"), str)
        or app["id"].casefold() != scope.app_id.casefold()
        or not isinstance(app.get("tags"), dict)
        or app["tags"].get("gbb-smoke-run") != scope.run_id
    ):
        raise OwnershipError("App identity/run tag does not match the recorded creation intent")
    receipt = {
        "id": app["id"], "run_tag": app["tags"]["gbb-smoke-run"], "etag": app.get("etag"),
        "created_at": app.get("systemData", {}).get("createdAt"),
        "images": [
            container.get("image")
            for container in app.get("properties", {}).get("template", {}).get("containers", [])
            if container.get("image")
        ],
    }
    state["app_receipts"].append(receipt)
    return receipt


def capture(path: Path, scope: Scope, arm: Arm):
    state = load(path, scope)
    arm.verify_context()
    app = arm.request("GET", scope.app_id)
    if app is None:
        raise OwnershipError("Deployment returned without an observable app")
    _receipt(state, app, scope)
    state["cleanup_state"] = "app_observed"
    _write(path, state)
    return state


def cleanup(path: Path, scope: Scope, arm: Arm, *, clock=time.monotonic, sleep=time.sleep):
    state = load(path, scope)
    arm.verify_context()
    try:
        app = arm.request("GET", scope.app_id)
        if app is not None:
            receipt = _receipt(state, app, scope)
            state["cleanup_state"] = "delete_intent"
            _write(path, state)
            arm.request("DELETE", scope.app_id, etag=receipt["etag"])
            deadline = clock() + 180
            while clock() < deadline:
                try:
                    app = arm.request("GET", scope.app_id)
                except UnclassifiedNotFound as exc:
                    state.setdefault("observation_notes", []).append(str(exc))
                    _write(path, state)
                    sleep(5)
                    continue
                if app is None:
                    break
                _receipt(state, app, scope)
                sleep(5)
            else:
                raise OwnershipError("App deletion still pending; do not replay or create replacements")
        state["cleanup_state"] = "app_absent_verified"
        state["residuals"] = []
        if state["deploy_started"]:
            state["residuals"] = [{
                "kind": "azd_image_and_deployment_artifacts",
                "registry": scope.registry,
                "observed_app_images": [r["images"] for r in state["app_receipts"]],
                "resource_group": scope.resource_group,
                "reason": "Immutable image/build and deployment-record custody not proven; no deletion attempted",
                "owner": state["owner"],
                "retention_approved": False,
                "review_deadline": "before another fixture deployment",
                "next_action": "Inspect this run's azd build/deployment receipts and hand off exact residuals",
            }]
        state["cleanup_complete"] = not state["residuals"]
        _write(path, state)
        return state
    except OwnershipError as exc:
        state["cleanup_state"] = "unresolved"
        state["cleanup_complete"] = False
        state["cleanup_error"] = str(exc)
        _write(path, state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "start", "capture", "cleanup"))
    for name in ("state", "evidence", "run-id", "subscription", "tenant",
                 "resource-group", "app-name", "registry"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    path, evidence = Path(args.state), Path(args.evidence)
    scope = Scope(args.run_id, args.subscription, args.tenant, args.resource_group, args.app_name, args.registry)
    try:
        if args.action == "start":
            state = start(path, scope)
        else:
            operation = {"prepare": prepare, "capture": capture, "cleanup": cleanup}[args.action]
            state = operation(path, scope, Arm(scope))
        report(evidence, state, scope)
        print(f"OWNERSHIP {args.action}: {state['cleanup_state']}")
        if args.action == "cleanup" and state["residuals"]:
            print("NOTE: unresolved azd artifacts; exact inventory exported, no shared deletion")
            return 2
        return 0
    except (OwnershipError, ValueError, OSError) as exc:
        print(f"OWNERSHIP ERROR: {exc}", file=sys.stderr)
        if path.is_file() and not path.is_symlink():
            try:
                state = load(path, scope)
                report(evidence, {"error": str(exc), "inventory": state}, scope)
            except (ValueError, OSError, OwnershipError) as report_error:
                print(f"OWNERSHIP REPORT ERROR: {type(report_error).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
