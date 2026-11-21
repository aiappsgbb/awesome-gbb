"""Router-aware token usage from Azure Monitor platform metrics.

Source of truth for the prose in `../SKILL.md § Router-aware analysis`.

Model router traffic can only be split per served model through Azure Monitor
platform metrics on the Foundry resource: diagnostic-settings export to Log
Analytics (`AzureMetrics`) flattens metric dimensions, so `ModelName` is lost.
This module reads the metrics REST payload (the same JSON that
`az monitor metrics list -o json` prints), splits it by
`ModelDeploymentName` x `ModelName` and separates router-originated load:

- `InputTokens` / `OutputTokens` / `ModelRequests`: load per deployment and
  served model. Router-managed traffic appears under the router deployment
  name; routed requests served by your own deployment appear under that
  deployment's name, mixed with its direct traffic.
- `ModelRouterInputTokens` / `ModelRouterOutputTokens` / `ModelRouterRequests`
  / `ModelRouterCachedTokens`: everything the router processed, by router
  deployment and served model, including requests your own deployments served.

Router-originated load on your own deployments of model M is therefore
`ModelRouter*(M) - router-managed(M)`. Standard library only, so the parser is
testable without pandas; Azure calls (`fetch_metrics`, `fetch_router_fee`)
import their dependencies lazily.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Any, Iterable

LOAD_METRICS = ("ModelRequests", "InputTokens", "OutputTokens")
ROUTER_METRICS = (
    "ModelRouterRequests",
    "ModelRouterInputTokens",
    "ModelRouterOutputTokens",
    "ModelRouterCachedTokens",
)
ALL_METRICS = LOAD_METRICS + ROUTER_METRICS
METRICS_API_VERSION = "2024-02-01"
ARM_SCOPE = "https://management.azure.com/.default"
RETAIL_URL = "https://prices.azure.com/api/retail/prices"
ROUTER_FEE_METERS = {"global": "Model Routers GL 1M Tokens", "data_zone": "Model Routers DZ 1M Tokens"}
DEFAULT_WATCH_MODELS = ("gpt-4.1", "gpt-4o", "gpt-5.4")


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def parse_metrics_payload(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Flatten an Azure Monitor metrics payload into rows.

    Each row: `{"minute": iso str, "metric": str, "deployment": str, "model": str, "value": float}`.
    Deployment and model names are lower-cased (Azure Monitor is not consistent
    about casing between metric families). Null totals become 0 so idle minutes
    stay in the percentile window.
    """
    metrics = payload.get("value", []) if isinstance(payload, dict) else payload
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        name = metric.get("name", {})
        metric_name = name.get("value") if isinstance(name, dict) else str(name)
        if metric_name not in ALL_METRICS:
            continue
        for series in metric.get("timeseries", []) or []:
            dims = {
                _norm(d.get("name", {}).get("value")): d.get("value", "")
                for d in series.get("metadatavalues", []) or []
            }
            deployment = _norm(dims.get("modeldeploymentname"))
            model = _norm(dims.get("modelname"))
            for point in series.get("data", []) or []:
                rows.append(
                    {
                        "minute": point.get("timeStamp"),
                        "metric": metric_name,
                        "deployment": deployment,
                        "model": model,
                        "value": float(point.get("total") or 0.0),
                    }
                )
    if not rows:
        raise ValueError(
            "No usable metric rows. Query ModelRequests, InputTokens, OutputTokens and the "
            "ModelRouter* metrics with --filter \"ModelDeploymentName eq '*' and ModelName eq '*'\"."
        )
    return rows


def router_deployment_names(rows: Iterable[dict[str, Any]], extra: Iterable[str] = ()) -> set[str]:
    """Deployments that are model routers: seen in ModelRouter* metrics, named
    `model-router*` (Auto traffic can surface as `model-router-<version>`), or
    passed explicitly."""
    names = {_norm(x) for x in extra if x}
    for row in rows:
        if row["metric"] in ROUTER_METRICS or row["deployment"].startswith("model-router"):
            names.add(row["deployment"])
    names.discard("")
    return names


def _totals(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str, str], float]:
    out: dict[tuple[str, str, str], float] = defaultdict(float)
    for row in rows:
        out[(row["metric"], row["deployment"], row["model"])] += row["value"]
    return out


def summarize(
    rows: list[dict[str, Any]],
    router_deployments: Iterable[str] = (),
    watch_models: Iterable[str] = DEFAULT_WATCH_MODELS,
    ptu_catalog: Iterable[str] = (),
    candidate_model: str = "",
) -> dict[str, Any]:
    """Per deployment x served model table plus router-originated split.

    `watch_models` are family prefixes to flag (for example older pool models);
    `ptu_catalog` lists models you can size PTU for, so routed load on other
    models is flagged as not absorbable by a PTU of the candidate model.
    The PTU candidate (`candidate_model`) is never flagged as watched.
    """
    routers = router_deployment_names(rows, router_deployments)
    tot = _totals(rows)

    deployments: dict[tuple[str, str], dict[str, Any]] = {}
    for (metric, dep, model), value in tot.items():
        if metric not in LOAD_METRICS or not model:
            continue
        rec = deployments.setdefault(
            (dep, model),
            {"deployment": dep, "model": model, "is_router": dep in routers,
             "requests": 0.0, "input_tokens": 0.0, "output_tokens": 0.0},
        )
        key = {"ModelRequests": "requests", "InputTokens": "input_tokens", "OutputTokens": "output_tokens"}[metric]
        rec[key] += value

    served: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for (metric, dep, model), value in tot.items():
        if not model:
            continue
        s = served[model]
        if metric in LOAD_METRICS:
            field = {"ModelRequests": "requests", "InputTokens": "input_tokens", "OutputTokens": "output_tokens"}[metric]
            s[f"total_{field}"] += value
            if dep in routers:
                s[f"router_managed_{field}"] += value
        else:
            field = {"ModelRouterRequests": "requests", "ModelRouterInputTokens": "input_tokens",
                     "ModelRouterOutputTokens": "output_tokens", "ModelRouterCachedTokens": "cached_tokens"}[metric]
            s[f"routed_{field}"] += value

    has_router_metrics = any(m in ROUTER_METRICS for (m, _, _) in tot)
    per_model = []
    for model, s in sorted(served.items()):
        rec = {"model": model}
        for field in ("requests", "input_tokens", "output_tokens"):
            total = s.get(f"total_{field}", 0.0)
            managed = s.get(f"router_managed_{field}", 0.0)
            routed = s.get(f"routed_{field}", 0.0) if has_router_metrics else managed
            rec[f"total_{field}"] = total
            rec[f"routed_{field}"] = routed
            own = max(total - managed, 0.0)
            # Routed load that your own deployments served. The two metric
            # families are aggregated independently and can disagree (live
            # test: DeepSeek 84 vs 46 input tokens), so never attribute more
            # than the load seen on your non-router deployments.
            rec[f"routed_on_own_{field}"] = min(max(routed - managed, 0.0), own) if has_router_metrics else 0.0
            rec[f"direct_{field}"] = max(total - rec[f"routed_on_own_{field}"] - managed, 0.0)
        rec["routed_cached_tokens"] = s.get("routed_cached_tokens", 0.0)
        per_model.append(rec)

    routed_input = sum(r["routed_input_tokens"] for r in per_model)
    routed_cached = sum(r["routed_cached_tokens"] for r in per_model)
    watch = tuple(_norm(w) for w in watch_models if w)
    catalog = {_norm(c) for c in ptu_catalog}
    flags = []
    for r in per_model:
        if r["routed_input_tokens"] <= 0 and r["routed_requests"] <= 0:
            continue
        share = r["routed_input_tokens"] / routed_input * 100 if routed_input else 0.0
        if r["model"] != _norm(candidate_model) and any(
                r["model"] == w or r["model"].startswith(w + "-") for w in watch):
            flags.append({"model": r["model"], "routed_input_share_pct": share,
                          "reason": "routed traffic lands on a watched (older) pool model"})
        if catalog and r["model"] not in catalog:
            flags.append({"model": r["model"], "routed_input_share_pct": share,
                          "reason": "no PTU pricing in models.json: a PTU cannot absorb this load"})

    return {
        "router_deployments": sorted(routers),
        "has_router_metrics": has_router_metrics,
        "deployments": sorted(deployments.values(), key=lambda d: (not d["is_router"], d["deployment"], d["model"])),
        "served_models": per_model,
        "routed_input_tokens": routed_input,
        "routed_cached_tokens": routed_cached,
        "flags": flags,
    }


def router_fee(summary: dict[str, Any], fee_per_m: float, window_months: float,
               exclude_cached: bool = False) -> dict[str, float]:
    """Router fee for the window and per month. Whether cached input is exempt is
    not documented, so all input is charged unless `exclude_cached` is set."""
    tokens = summary["routed_input_tokens"]
    if exclude_cached:
        tokens = max(tokens - summary["routed_cached_tokens"], 0.0)
    window_cost = tokens / 1_000_000 * fee_per_m
    monthly = window_cost / window_months if window_months > 0 else 0.0
    return {"fee_per_m": fee_per_m, "fee_tokens": tokens, "window_cost": window_cost, "monthly_cost": monthly}


def minute_series(rows: list[dict[str, Any]], model: str, include_routed: bool = True,
                  router_deployments: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Per-minute usage for one served model across ALL deployments, in the
    analyzer's CSV schema. With `include_routed=False`, router-originated load
    (router-managed plus routed-on-own, from the ModelRouter* metrics) is
    removed, giving the direct-only baseline. Cached tokens come from
    `ModelRouterCachedTokens` (routed only); direct cached input is not in
    these metrics and counts as non-cached, which over- rather than
    under-sizes PTU."""
    target = _norm(model)
    routers = router_deployment_names(rows, router_deployments)
    by_min: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        minute = row["minute"]
        bucket = by_min[minute]
        if row["model"] != target:
            continue
        m, dep, v = row["metric"], row["deployment"], row["value"]
        if m == "InputTokens":
            bucket["in"] += v
            if dep in routers:
                bucket["managed_in"] += v
        elif m == "OutputTokens":
            bucket["out"] += v
            if dep in routers:
                bucket["managed_out"] += v
        elif m == "ModelRouterInputTokens":
            bucket["r_in"] += v
        elif m == "ModelRouterOutputTokens":
            bucket["r_out"] += v
        elif m == "ModelRouterCachedTokens":
            bucket["r_cached"] += v
    out = []
    for minute in sorted(by_min):
        b = by_min[minute]
        inp, outp = b["in"], b["out"]
        cached = min(b["r_cached"], inp)
        if not include_routed:
            own_in, own_out = inp - b["managed_in"], outp - b["managed_out"]
            routed_in = b["managed_in"] + min(max(b["r_in"] - b["managed_in"], 0.0), own_in)
            routed_out = b["managed_out"] + min(max(b["r_out"] - b["managed_out"], 0.0), own_out)
            inp = max(inp - routed_in, 0.0)
            outp = max(outp - routed_out, 0.0)
            cached = 0.0
        out.append({
            "minute_bin": minute,
            "input_tokens_sum": int(round(inp)),
            "cached_tokens_sum": int(round(cached)),
            "output_tokens_sum": int(round(outp)),
        })
    return out


def render_markdown(summary: dict[str, Any], fee: dict[str, float] | None,
                    whatif: dict[str, Any] | None = None) -> str:
    """Markdown section appended to report.md."""
    def n(x: float) -> str:
        return f"{x:,.0f}"

    lines = [
        "## Router-aware load",
        "",
        f"Router deployments: **{', '.join(summary['router_deployments']) or 'none detected'}**. "
        "Source: Azure Monitor platform metrics split by `ModelDeploymentName` x `ModelName`.",
        "",
        "### Load per deployment and served model",
        "",
        "| Deployment | Served model | Router | Requests | Input tokens | Output tokens |",
        "|---|---|---|---:|---:|---:|",
    ]
    for d in summary["deployments"]:
        lines.append(f"| {d['deployment']} | {d['model']} | {'yes' if d['is_router'] else 'no'} | "
                     f"{n(d['requests'])} | {n(d['input_tokens'])} | {n(d['output_tokens'])} |")
    lines += [
        "",
        "### Router-originated tokens per served model",
        "",
        "| Served model | Routed input | of which on your deployments | Routed output | Direct input | Total input |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in summary["served_models"]:
        lines.append(f"| {r['model']} | {n(r['routed_input_tokens'])} | {n(r['routed_on_own_input_tokens'])} | "
                     f"{n(r['routed_output_tokens'])} | {n(r['direct_input_tokens'])} | {n(r['total_input_tokens'])} |")
    if not summary["has_router_metrics"]:
        lines += ["", "> ModelRouter* metrics were not in the input: routed load served by your own "
                      "deployments cannot be separated from direct traffic."]
    if fee:
        lines += [
            "",
            "### Router fee",
            "",
            f"- Fee: **${fee['fee_per_m']:.3f} per 1M input tokens** on {n(fee['fee_tokens'])} routed input tokens",
            f"- Window: **${fee['window_cost']:,.2f}**; per month: **${fee['monthly_cost']:,.2f}**",
            f"- Fee source: {fee.get('source', 'input')}. Billed fee: Cost Management, meters "
            "`Model Routers GL/DZ 1M Tokens`, tag **Deployment** = router deployment.",
            "- The fee is paid on every routed request, including requests a PTU deployment serves.",
        ]
    if whatif:
        lines += [
            "",
            f"### PTU what-if: router absorbs into PTU ({whatif['model']})",
            "",
            f"| Load | p{whatif['percentile']} PTU-billable TPM | PTUs | PAYGO monthly | PTU + spillover monthly |",
            "|---|---:|---:|---:|---:|",
        ]
        for label in ("direct_only", "with_routed"):
            w = whatif[label]
            lines.append(f"| {w['label']} | {n(w['billable_tpm'])} | {n(w['ptus'])} | "
                         f"${w['paygo_monthly']:,.2f} | ${w['total_monthly']:,.2f} |")
        if fee:
            lines.append(f"\nWith routed load, add the router fee (${fee['monthly_cost']:,.2f}/month) to the PTU total.")
    if summary["flags"]:
        lines += ["", "### Sizing risk flags", ""]
        for f in summary["flags"]:
            lines.append(f"- **{f['model']}** ({f['routed_input_share_pct']:.1f}% of routed input): {f['reason']}")
    lines.append("")
    return "\n".join(lines)


def fetch_metrics(resource_id: str, timespan: str, credential: Any = None, timeout: float = 60.0) -> dict[str, Any]:
    """GET the metrics REST API for one Foundry resource (Monitoring Reader or Reader needed).

    `timespan` is ISO 8601 `start/end`. Equivalent CLI:
    `az monitor metrics list --resource <id> --metrics ... --aggregation Total --interval PT1M
    --filter "ModelDeploymentName eq '*' and ModelName eq '*'" -o json`.
    """
    if credential is None:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
    token = credential.get_token(ARM_SCOPE).token
    query = urllib.parse.urlencode({
        "api-version": METRICS_API_VERSION,
        "metricnames": ",".join(ALL_METRICS),
        "aggregation": "Total",
        "interval": "PT1M",
        "timespan": timespan,
        "$filter": "ModelDeploymentName eq '*' and ModelName eq '*'",
        "top": "1000",
    })
    url = f"https://management.azure.com{resource_id.rstrip('/')}/providers/Microsoft.Insights/metrics?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed ARM host
        return json.load(resp)


def fetch_router_fee(region: str, tier: str = "global", timeout: float = 20.0) -> float:
    """Router fee per 1M input tokens from the public Azure Retail Prices API."""
    meter = ROUTER_FEE_METERS[tier]
    flt = f"armRegionName eq '{region}' and type eq 'Consumption' and meterName eq '{meter}'"
    url = RETAIL_URL + "?" + urllib.parse.urlencode({"$filter": flt})
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed public host
        items = json.load(resp).get("Items", [])
    for item in items:
        if item.get("meterName") == meter and item.get("unitOfMeasure") == "1M":
            return float(item["retailPrice"])
    raise RuntimeError(f"Meter '{meter}' not found in region '{region}'; pass --router-fee-per-m")
