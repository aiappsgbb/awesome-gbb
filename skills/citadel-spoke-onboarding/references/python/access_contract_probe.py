"""Canonical Citadel hub-side Access Contract probe.

Source of truth for the prose example in `../../SKILL.md § Hub-side Access Contract probe`.

Exposes read-only hub inventory, not Foundry connection or runtime acceptance.

API/Product IDs are derived from *spoke_id* by default:
  - API:     ``{spoke_id}-api``
  - Product: ``{spoke_id}-product``

These are legacy defaults, not the native Access Contract naming convention.
Supply explicit ``api_id`` and ``product_id`` from the approved contract.
Pass ``apim_name=None`` to discover APIM only when the resource group contains
exactly one instance.

Backwards-compat: when ``hub_rg`` is the empty string the function reads the
``TL_CITADEL_HUB_RG`` environment variable, matching the threadlight
production convention.

Azure SDK imports are guarded with ``try/except ImportError`` so this module
can be imported under CI environments that have only ``pyyaml`` installed.
Call-time safety: if the SDK is absent, ``probe_hub_contract`` returns a safe
dict with a ``missing_perms`` entry explaining how to fix it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

# -- guarded SDK imports -------------------------------------------------------
try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.apimanagement import ApiManagementClient
    from azure.mgmt.resource import ResourceManagementClient
    from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
except ImportError:  # azure SDKs optional at import time; required at call time
    DefaultAzureCredential = None  # type: ignore[assignment,misc]
    ApiManagementClient = None  # type: ignore[assignment,misc]
    ResourceManagementClient = None  # type: ignore[assignment,misc]

    class ResourceNotFoundError(Exception):  # type: ignore[misc]
        """Stub: azure.core.exceptions.ResourceNotFoundError (SDK absent)."""

    class HttpResponseError(Exception):  # type: ignore[misc]
        """Stub: azure.core.exceptions.HttpResponseError (SDK absent)."""

# ------------------------------------------------------------------------------

_APIM_TYPE = "microsoft.apimanagement/service"


def _safe_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_result() -> dict[str, Any]:
    return {
        "api_present": False,
        "product_assigned": False,
        "foundry_connection_status": "unverified",
        "hub_contract_status": "errored",
        "evidence_scope": "hub-arm-inventory",
        "subscription_key_present": False,
        "rate_limit_policy": None,
        "last_probe_at": _safe_timestamp(),
        "confidence": 0.0,
        "missing_perms": [],
    }


def _compute_confidence(
    api_present: bool,
    product_assigned: bool,
    subscription_key_present: bool,
) -> float:
    """Return confidence 0.0..1.0 based on which checks passed.

    Weighting:
      all three True  → 1.0
      api + product   → 0.66
      api only        → 0.33
      none            → 0.0
    """
    if api_present and product_assigned and subscription_key_present:
        return 1.0
    if api_present and product_assigned:
        return 0.66
    if api_present:
        return 0.33
    return 0.0


def _same_id(actual: object, expected: str) -> bool:
    return isinstance(actual, str) and actual.rstrip("/").casefold() == expected.rstrip("/").casefold()


class _ObservationError(ValueError):
    """A fixed, credential-free diagnostic owned by this module."""


def _report_error(result: dict[str, Any], operation: str, exc: Exception) -> None:
    # SDK exception text can contain request URLs or credential-bearing bodies.
    status = getattr(exc, "status_code", None)
    code = f" HTTP {status}" if isinstance(status, int) else ""
    reason = str(exc) if isinstance(exc, _ObservationError) else type(exc).__name__
    result["missing_perms"].append(f"{operation} failed: {reason}{code}")


def probe_hub_contract(
    hub_rg: str,
    apim_name: str | None = None,
    *,
    spoke_id: str,
    subscription: str | None = None,
    credential: Any = None,
    api_id: str | None = None,
    product_id: str | None = None,
) -> dict[str, Any]:
    """Probe the Citadel hub-side Access Contract for a registered spoke.

    Parameters
    ----------
    hub_rg:
        Azure resource-group name where the Citadel APIM lives.  When the
        empty string is passed the function falls back to the
        ``TL_CITADEL_HUB_RG`` environment variable (threadlight compat).
    apim_name:
        APIM service name.  Pass ``None`` to auto-discover from the resource
        group; the RG must contain exactly one ``Microsoft.ApiManagement/service``
        resource, otherwise the probe returns ``confidence == 0.0`` with an
        ambiguity message in ``missing_perms``.
    spoke_id:
        Spoke identifier string (keyword-only, required).  Used to derive
        legacy API ID (``{spoke_id}-api``) and product ID
        (``{spoke_id}-product``) when explicit IDs are omitted.
    subscription:
        Azure subscription ID (optional).  When ``None`` or empty, the
        helper falls back to the ``AZURE_SUBSCRIPTION_ID`` environment
        variable.  If neither is set, the probe returns the error-path
        dict with an entry in ``missing_perms``.  No automatic CLI-context
        resolution is performed; the caller (or the env var) must supply
        the subscription.
    credential:
        Optional pre-built Azure credential object.  When ``None``,
        ``DefaultAzureCredential()`` is constructed automatically.
        The caller must establish tenant isolation and approved target context.
    api_id, product_id:
        Exact APIM resource names from the selected contract (not ARM IDs).

    Returns
    -------
    dict with keys:
      api_present: bool
      product_assigned: bool
      foundry_connection_status: "unverified" (no Foundry observation is made)
      hub_contract_status: "ok" | "missing" | "errored"
      evidence_scope: "hub-arm-inventory"
      subscription_key_present: bool
      rate_limit_policy: dict | None
      last_probe_at: ISO8601 str
      confidence: float  0.0..1.0 (hub inventory coverage only)
      missing_perms: list[str]

    Never raises.  ``KeyboardInterrupt`` / ``SystemExit`` (``BaseException``
    subclasses) are intentionally allowed to propagate — only ``Exception``
    is caught.

    Refs #246.
    """
    result = _empty_result()

    # -- env-var fallback ------------------------------------------------------
    if not hub_rg:
        hub_rg = os.environ.get("TL_CITADEL_HUB_RG", "")
    if not hub_rg:
        result["missing_perms"].append(
            "hub_rg is empty and TL_CITADEL_HUB_RG env var is not set"
        )
        return result

    # -- spoke_id guard --------------------------------------------------------
    if not spoke_id:
        result["missing_perms"].append("spoke_id must be a non-empty string")
        return result
    api_id = api_id if api_id is not None else f"{spoke_id}-api"
    product_id = product_id if product_id is not None else f"{spoke_id}-product"
    if any(not isinstance(value, str) or not value.strip()
           or any(char in value for char in "/?#")
           for value in (api_id, product_id)):
        result["missing_perms"].append("api_id and product_id must be exact APIM resource names")
        return result

    # -- subscription env-var fallback -----------------------------------------
    if not subscription:
        subscription = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription:
        result["missing_perms"].append(
            "subscription must be provided or set in AZURE_SUBSCRIPTION_ID env var"
        )
        return result

    # -- SDK availability guard ------------------------------------------------
    if ApiManagementClient is None or ResourceManagementClient is None:
        result["missing_perms"].append(
            "azure SDK not available: pip install azure-mgmt-apimanagement"
            " azure-mgmt-resource azure-identity"
        )
        return result

    # -- build credentials / clients -------------------------------------------
    try:
        if credential is None:
            if DefaultAzureCredential is None:
                result["missing_perms"].append(
                    "azure-identity not available: pip install azure-identity"
                )
                return result
            credential = DefaultAzureCredential()

        apim_client = ApiManagementClient(credential, subscription)
        resource_client = ResourceManagementClient(credential, subscription)
    except Exception as exc:
        _report_error(result, "credential/client init", exc)
        return result

    # -- auto-discover APIM when not provided ----------------------------------
    if apim_name is None:
        try:
            all_resources = list(resource_client.resources.list_by_resource_group(hub_rg))
            apim_resources = [
                r for r in all_resources
                if (r.type or "").lower() == _APIM_TYPE
            ]
            if len(apim_resources) == 0:
                result["missing_perms"].append(
                    f"no Microsoft.ApiManagement/service found in resource group '{hub_rg}'"
                )
                return result
            if len(apim_resources) > 1:
                names = ", ".join(r.name for r in apim_resources)
                result["missing_perms"].append(
                    f"ambiguous: multiple APIM instances found in '{hub_rg}': {names};"
                    " pass apim_name explicitly"
                )
                return result
            apim_name = apim_resources[0].name
        except Exception as exc:
            _report_error(result, "resource list", exc)
            return result

    service_scope = (
        f"/subscriptions/{subscription}/resourceGroups/{hub_rg}"
        f"/providers/Microsoft.ApiManagement/service/{apim_name}"
    )
    api_scope = f"{service_scope}/apis/{api_id}"
    product_scope = f"{service_scope}/products/{product_id}"

    # -- check API presence ----------------------------------------------------
    try:
        api = apim_client.api.get(hub_rg, apim_name, api_id)
        if not _same_id(getattr(api, "id", None), api_scope):
            raise _ObservationError("API readback scope mismatch")
        result["api_present"] = True
    except ResourceNotFoundError:
        result["api_present"] = False
        # 404 = spoke not onboarded yet; not a permission gap
    except Exception as exc:
        _report_error(result, "api.get", exc)

    # -- check product assignment ----------------------------------------------
    try:
        product = apim_client.product.get(hub_rg, apim_name, product_id)
        if not _same_id(getattr(product, "id", None), product_scope):
            raise _ObservationError("Product readback scope mismatch")
        if result["api_present"]:
            assigned = apim_client.product_api.check_entity_exists(
                hub_rg, apim_name, product_id, api_id,
            )
            if not isinstance(assigned, bool):
                raise _ObservationError("Unreadable product/API association")
            result["product_assigned"] = assigned
    except ResourceNotFoundError:
        result["product_assigned"] = False
        # 404 = product not onboarded yet; not a permission gap
    except Exception as exc:
        _report_error(result, "product.get/product_api.check_entity_exists", exc)

    # -- check subscription key ------------------------------------------------
    if result["product_assigned"]:
        try:
            subs = list(apim_client.subscription.list(hub_rg, apim_name))
            active_matching = False
            for sub in subs:
                sub_id = getattr(sub, "id", None)
                prefix = service_scope + "/subscriptions/"
                if (not isinstance(sub_id, str)
                        or not sub_id.casefold().startswith(prefix.casefold())
                        or not sub_id[len(prefix):] or "/" in sub_id[len(prefix):]
                        or not isinstance(getattr(sub, "scope", None), str)
                        or not isinstance(getattr(sub, "state", None), str)):
                    raise _ObservationError("Unreadable or wrong-scope subscription inventory")
                if sub.state == "active" and (
                    _same_id(sub.scope, product_scope)
                    or _same_id(sub.scope, f"/products/{product_id}")
                ):
                    active_matching = True
            result["subscription_key_present"] = active_matching
        except Exception as exc:
            _report_error(result, "subscription.list", exc)

    # -- check rate-limit policy -----------------------------------------------
    if result["api_present"]:
        try:
            policy = apim_client.api_policy.get(hub_rg, apim_name, api_id, "policy")
            policy_value = getattr(policy, "value", None)
            if policy_value is not None and not isinstance(policy_value, str):
                raise _ObservationError("Unreadable API policy")
            result["rate_limit_policy"] = {"raw_xml": policy_value} if policy_value else None
        except ResourceNotFoundError:
            pass  # An API-level policy is optional; product/global policies are separate.
        except Exception as exc:
            _report_error(result, "api_policy.get", exc)

    # -- compute final confidence + connection status --------------------------
    result["confidence"] = _compute_confidence(
        result["api_present"],
        result["product_assigned"],
        result["subscription_key_present"],
    )

    if result["missing_perms"]:
        result["hub_contract_status"] = "errored"
    elif all(result[key] for key in ("api_present", "product_assigned", "subscription_key_present")):
        result["hub_contract_status"] = "ok"
    else:
        result["hub_contract_status"] = "missing"

    result["last_probe_at"] = _safe_timestamp()
    return result
