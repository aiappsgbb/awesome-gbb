"""Canonical Citadel hub-side Access Contract probe.

Source of truth for the prose example in `../../SKILL.md § Hub-side Access Contract probe`.

Exposes ``probe_hub_contract()`` so threadlight v0.5.2 can flip its NET-501/502
self-verify checks from ``kind: manual`` to ``kind: sibling-skill`` (issue #246).

API/Product IDs are derived from *spoke_id* by default:
  - API:     ``{spoke_id}-api``
  - Product: ``{spoke_id}-product``

These defaults match the naming convention that ``citadel-spoke-onboarding``
prescribes when a spoke is registered. Pass ``apim_name=None`` to auto-discover
the APIM instance when the resource group contains exactly one.

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
        "foundry_connection_status": "missing",
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


def probe_hub_contract(
    hub_rg: str,
    apim_name: str | None = None,
    *,
    spoke_id: str,
    subscription: str | None = None,
    credential: Any = None,
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
        API ID (``{spoke_id}-api``), product ID (``{spoke_id}-product``),
        and to match the subscription key display name.
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

    Returns
    -------
    dict with keys:
      api_present: bool
      product_assigned: bool
      foundry_connection_status: "ok" | "missing" | "errored"
      subscription_key_present: bool
      rate_limit_policy: dict | None
      last_probe_at: ISO8601 str
      confidence: float  0.0..1.0
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
        result["foundry_connection_status"] = "errored"
        result["missing_perms"].append(f"credential/client init failed: {exc}")
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
            result["foundry_connection_status"] = "errored"
            result["missing_perms"].append(f"resource list failed: {exc}")
            return result

    # -- derive API / product IDs from spoke_id --------------------------------
    api_id = f"{spoke_id}-api"
    product_id = f"{spoke_id}-product"

    # -- check API presence ----------------------------------------------------
    api_get_errored = False
    try:
        apim_client.api.get(hub_rg, apim_name, api_id)
        result["api_present"] = True
    except ResourceNotFoundError:
        result["api_present"] = False
        # 404 = spoke not onboarded yet; not a permission gap
    except HttpResponseError as exc:
        result["api_present"] = False
        if getattr(exc, "status_code", None) == 403 or "403" in str(exc):
            result["missing_perms"].append(f"api.get forbidden (403): {exc}")
        else:
            result["missing_perms"].append(f"api.get failed: {exc}")
        api_get_errored = True
    except Exception as exc:
        result["api_present"] = False
        result["missing_perms"].append(f"api.get failed: {exc}")
        api_get_errored = True

    # -- check product assignment ----------------------------------------------
    product_get_errored = False
    try:
        apim_client.product.get(hub_rg, apim_name, product_id)
        result["product_assigned"] = True
    except ResourceNotFoundError:
        result["product_assigned"] = False
        # 404 = product not onboarded yet; not a permission gap
    except HttpResponseError as exc:
        result["product_assigned"] = False
        if getattr(exc, "status_code", None) == 403 or "403" in str(exc):
            result["missing_perms"].append(f"product.get forbidden (403): {exc}")
        else:
            result["missing_perms"].append(f"product.get failed: {exc}")
        product_get_errored = True
    except Exception as exc:
        result["product_assigned"] = False
        result["missing_perms"].append(
            f"product.get failed (check APIM Product Reader role): {exc}"
        )
        product_get_errored = True

    # -- check subscription key ------------------------------------------------
    if result["product_assigned"]:
        try:
            subs = list(apim_client.subscription.list(hub_rg, apim_name))
            active_matching = [
                s for s in subs
                if getattr(s, "state", None) == "active"
                and spoke_id.lower() in (getattr(s, "display_name", None) or "").lower()
            ]
            result["subscription_key_present"] = len(active_matching) > 0
        except Exception as exc:
            result["missing_perms"].append(f"subscription.list failed: {exc}")

    # -- check rate-limit policy -----------------------------------------------
    try:
        policy = apim_client.api_policy.get(hub_rg, apim_name, api_id)
        policy_value = getattr(policy, "value", None)
        result["rate_limit_policy"] = (
            {"raw_xml": policy_value} if policy_value else None
        )
    except Exception:
        result["rate_limit_policy"] = None

    # -- compute final confidence + connection status --------------------------
    result["confidence"] = _compute_confidence(
        result["api_present"],
        result["product_assigned"],
        result["subscription_key_present"],
    )

    if api_get_errored or product_get_errored:
        result["foundry_connection_status"] = "errored"
    elif result["api_present"] and result["product_assigned"]:
        result["foundry_connection_status"] = "ok"
    else:
        result["foundry_connection_status"] = "missing"

    result["last_probe_at"] = _safe_timestamp()
    return result
