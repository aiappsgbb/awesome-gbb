"""Canonical model router cost/quality measurement for the Responses API.

Source of truth for the prose example in `../../SKILL.md § Measure the router on your workload`.

Runs the same graded task mix through model router arms (Auto or a model
router deployment, optionally with per-request routing modes) and through
fixed single-model baseline deployments. For every arm it reports quality,
estimated $ per 1k tasks, the routing fee share and the distribution of the
models that actually answered (the response ``model`` field).

Prices are fetched from the public Azure Retail Prices API with a finite
timeout (never hard-coded). Costs are estimates (usage x list price + routing
fee), not billed amounts; use Cost Management for billed costs.

Prints counts, case ids and pass/fail only. It never logs prompts or outputs.

Usage (Entra ID; the identity needs Foundry User on the resource or project):

    python measure_router.py --endpoint https://<resource>.services.ai.azure.com \
        --router <model-router-deployment|auto> --modes deployment,cost,quality \
        --baseline <small-model-deployment> [--baseline ...] \
        --cases router_cases.jsonl [--repeats 2] --region swedencentral \
        [--zone global|datazone] [--fee-excludes-cached] [--tenant <tenant-id>]

    python measure_router.py --prices-only --models gpt-5.4-mini,gpt-6-luna

Exit codes: 0 = every arm completed and was priced; 1 = completed but some
answering model had no retail price (cost is a lower bound); 2 = configuration,
price lookup or API error.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SCOPE = "https://ai.azure.com/.default"
RETAIL_URL = "https://prices.azure.com/api/retail/prices"
ROUTER_HEADER = {"Foundry-Features": "ModelRouterControls=V1Preview"}
ROUTER_FEE_METERS = {"global": "Model Routers GL 1M Tokens", "datazone": "Model Routers DZ 1M Tokens"}
ROUTER_MODES = ("deployment", "balanced", "cost", "quality")

# Strict meter vocabulary: a meter is used only if every token after the model
# name is one of these. Batch, provisioned (pp), Flex, long context, fine-tuning
# and cache-write meters contain other tokens and are therefore never matched.
_KIND_TOKENS = {
    "inp": "input", "inpt": "input", "input": "input",
    "cd": "cached", "cchd": "cached", "cached": "cached",
    "opt": "output", "outpt": "output", "output": "output", "outp": "output",
}
_ZONE_TOKENS = {"gl": "global", "glbl": "global", "global": "global", "glb": "global",
                "dz": "datazone", "dzone": "datazone", "datazone": "datazone"}
_NEUTRAL_TOKENS = {"std", "shortco", "1m", "1k", "tokens", "token", "txt", "text"}


def openai_base_url(endpoint: str) -> str:
    """Accept a resource endpoint or a Foundry project endpoint; return the /openai/v1/ base."""
    endpoint = endpoint.strip().rstrip("/")
    if "/api/projects/" in endpoint:
        endpoint = endpoint.split("/api/projects/")[0]
    if endpoint.endswith("/openai/v1"):
        return endpoint + "/"
    return endpoint + "/openai/v1/"


def base_model(name: str) -> str:
    """'gpt-5.6-luna-2026-07-09' -> 'gpt-5.6-luna'."""
    return re.sub(r"-\d{4}-\d{2}-\d{2}$", "", name.strip().lower())


def _norm(text: str) -> str:
    text = text.lower().replace("data zone", "datazone")
    text = re.sub(r"[-_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[4:] if text.startswith("gpt ") else text


def classify_meter(meter_name: str, model: str) -> tuple[str, str] | None:
    """Return (kind, zone) if the meter is the standard-tier price of exactly this model."""
    meter, prefix = _norm(meter_name), _norm(base_model(model))
    if not meter.startswith(prefix + " "):
        return None
    kinds, zones = set(), set()
    for token in meter[len(prefix) + 1:].split():
        if token in _KIND_TOKENS:
            kinds.add(_KIND_TOKENS[token])
        elif token in _ZONE_TOKENS:
            zones.add(_ZONE_TOKENS[token])
        elif token not in _NEUTRAL_TOKENS:
            return None
    if "cached" in kinds:
        kinds.discard("input")
    if len(kinds) != 1 or len(zones) != 1:
        return None
    return kinds.pop(), zones.pop()


def _per_million(item: dict[str, Any]) -> float | None:
    unit = str(item.get("unitOfMeasure", "")).replace(" ", "").upper()
    scale = {"1M": 1.0, "1K": 1000.0}.get(unit)
    return None if scale is None else float(item["retailPrice"]) * scale


def model_prices(items: list[dict[str, Any]], model: str, zone: str) -> dict[str, float] | None:
    """USD per 1M tokens for input/cached/output, or None if not unambiguously priced."""
    found: dict[str, set[float]] = collections.defaultdict(set)
    for item in items:
        if item.get("type") not in (None, "Consumption"):
            continue
        hit = classify_meter(item.get("meterName", ""), model)
        price = _per_million(item)
        if hit and hit[1] == zone and price is not None:
            found[hit[0]].add(round(price, 8))
    if not {"input", "output"} <= found.keys() or any(len(v) != 1 for v in found.values()):
        return None
    prices = {kind: next(iter(values)) for kind, values in found.items()}
    prices.setdefault("cached", prices["input"])
    return prices


def router_fee(items: list[dict[str, Any]], zone: str) -> float | None:
    for item in items:
        if item.get("meterName") == ROUTER_FEE_METERS[zone] and item.get("type") == "Consumption":
            return _per_million(item)
    return None


def _get_json(url: str, timeout: float, attempts: int = 4) -> dict[str, Any]:
    """GET with a finite timeout; bounded backoff on HTTP 429 (the public API throttles bursts)."""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed public HTTPS host
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            time.sleep(min(float(retry_after) if retry_after.isdigit() else 5.0 * (attempt + 1), 30.0))
    raise RuntimeError("unreachable")


def fetch_retail_items(region: str, timeout: float = 20.0, max_pages: int = 60) -> list[dict[str, Any]]:
    """Consumption meters for Foundry Models and Foundry Tools (router fee) in one region."""
    flt = (f"armRegionName eq '{region}' and type eq 'Consumption' and "
           "(serviceName eq 'Foundry Models' or serviceName eq 'Foundry Tools')")
    url: str | None = RETAIL_URL + "?" + urllib.parse.urlencode({"$filter": flt})
    items: list[dict[str, Any]] = []
    for _ in range(max_pages):
        if not url:
            return items
        page = _get_json(url, timeout)
        items.extend(page.get("Items", []))
        url = page.get("NextPageLink")
    raise RuntimeError(f"Retail Prices API returned more than {max_pages} pages; narrow the filter")


def response_cost(usage: dict[str, int], prices: dict[str, float] | None, fee: float,
                  fee_excludes_cached: bool = False) -> tuple[float | None, float]:
    """(model USD or None if unpriced, routing-fee USD) for one response."""
    inp, cached, out = usage["input_tokens"], usage["cached_tokens"], usage["output_tokens"]
    fee_tokens = inp - cached if fee_excludes_cached else inp
    fee_usd = fee * fee_tokens / 1e6
    if prices is None:
        return None, fee_usd
    model_usd = ((inp - cached) * prices["input"] + cached * prices["cached"] + out * prices["output"]) / 1e6
    return model_usd, fee_usd


def fee_share_table(fee: float, prices_by_model: dict[str, dict[str, float] | None]) -> dict[str, Any]:
    """Routing fee as a percentage of each answering model's input and cached-input price."""
    table = {}
    for model, prices in sorted(prices_by_model.items()):
        if prices:
            table[model] = {
                "input_usd_per_1m": prices["input"],
                "fee_pct_of_input": round(100 * fee / prices["input"], 1),
                "fee_pct_of_cached": round(100 * fee / prices["cached"], 1) if prices["cached"] else None,
            }
        else:
            table[model] = "unpriced"
    return table


def load_cases(path: str) -> list[dict[str, Any]]:
    cases = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            case = json.loads(line)
            if not {"id", "prompt", "expect"} <= case.keys():
                raise ValueError(f"{path}:{n}: each case needs id, prompt and expect")
            re.compile(case["expect"])
            case.setdefault("tier", "easy")
            cases.append(case)
    if not cases:
        raise ValueError(f"{path}: no cases")
    return cases


def grade(text: str, expect: str) -> bool:
    return re.search(expect, text or "", re.IGNORECASE | re.DOTALL) is not None


def _usage(response: Any) -> dict[str, int]:
    u = response.usage
    details = getattr(u, "input_tokens_details", None)
    return {
        "input_tokens": u.input_tokens or 0,
        "cached_tokens": (getattr(details, "cached_tokens", 0) or 0) if details else 0,
        "output_tokens": u.output_tokens or 0,
    }


def run_arm(client: Any, arm: dict[str, Any], cases: list[dict[str, Any]], repeats: int,
            max_output_tokens: int) -> list[dict[str, Any]]:
    """One record per case x repeat: case id, tier, pass, answering model, usage."""
    records = []
    for rep in range(repeats):
        for case in cases:
            kwargs: dict[str, Any] = {"model": arm["model"], "input": case["prompt"],
                                      "max_output_tokens": max_output_tokens, "store": False}
            if case.get("reasoning_effort"):
                kwargs["reasoning"] = {"effort": case["reasoning_effort"]}
            if arm["mode"] not in (None, "deployment"):
                kwargs["extra_headers"] = ROUTER_HEADER
                kwargs["extra_body"] = {"routing_config": {"mode": arm["mode"]}}
            started = time.monotonic()
            try:
                response = client.responses.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 - record and continue; summarized per arm
                records.append({"case": case["id"], "tier": case["tier"], "repeat": rep,
                                "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                continue
            records.append({
                "case": case["id"], "tier": case["tier"], "repeat": rep,
                "passed": grade(response.output_text, case["expect"]),
                "model": base_model(response.model or "unknown"),
                "usage": _usage(response),
                "elapsed_s": round(time.monotonic() - started, 2),
            })
    return records


def summarize(arm: dict[str, Any], records: list[dict[str, Any]], prices: dict[str, dict[str, float] | None],
              fee: float, fee_excludes_cached: bool) -> dict[str, Any]:
    ok = [r for r in records if "error" not in r]
    model_usd = fee_usd = 0.0
    unpriced = set()
    for r in ok:
        m_usd, f_usd = response_cost(r["usage"], prices.get(r["model"]), fee, fee_excludes_cached)
        if m_usd is None:
            unpriced.add(r["model"])
        else:
            model_usd += m_usd
        if arm["router"]:
            fee_usd += f_usd
    total = model_usd + fee_usd
    counts = collections.Counter(r["model"] for r in ok)
    top_model, top_n = counts.most_common(1)[0] if counts else (None, 0)
    by_tier = {}
    for tier in sorted({r["tier"] for r in records}):
        tier_ok = [r for r in ok if r["tier"] == tier]
        by_tier[tier] = {"passed": sum(r["passed"] for r in tier_ok),
                         "graded": len(tier_ok)}
    summary = {
        "arm": arm["name"],
        "tasks": len(records),
        "errors": len(records) - len(ok),
        "passed": sum(r["passed"] for r in ok),
        "quality_pct": round(100 * sum(r["passed"] for r in ok) / len(ok), 1) if ok else None,
        "by_tier": by_tier,
        "usd_model": round(model_usd, 6),
        "usd_routing_fee": round(fee_usd, 6),
        "usd_per_1k_tasks": round(1000 * total / len(ok), 4) if ok else None,
        "fee_share_pct": round(100 * fee_usd / total, 1) if total else None,
        "tokens": {k: sum(r["usage"][k] for r in ok) for k in ("input_tokens", "cached_tokens", "output_tokens")},
        "models": {m: {"count": n, "share_pct": round(100 * n / len(ok), 1)} for m, n in counts.most_common()},
        "unpriced_models": sorted(unpriced),
        "failed_cases": sorted({r["case"] for r in ok if not r["passed"]}),
        "error_samples": [r["error"] for r in records if "error" in r][:3],
    }
    if arm["router"] and ok and top_n / len(ok) >= 0.9:
        summary["advice"] = (f"{round(100 * top_n / len(ok))}% of requests went to {top_model}: "
                             "compare with calling that model directly (you pay its usage plus the fee).")
    return summary


def make_client(endpoint: str, tenant: str | None, timeout: float) -> Any:
    from azure.identity import AzureCliCredential, DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    credential = AzureCliCredential(tenant_id=tenant) if tenant else DefaultAzureCredential()
    return OpenAI(base_url=openai_base_url(endpoint), api_key=get_bearer_token_provider(credential, SCOPE),
                  timeout=timeout, max_retries=2)


def build_arms(router: str | None, modes: list[str], baselines: list[str]) -> list[dict[str, Any]]:
    arms = []
    if router:
        for mode in modes:
            if mode not in ROUTER_MODES:
                raise ValueError(f"unknown mode {mode!r}; use {', '.join(ROUTER_MODES)}")
            arms.append({"name": f"router:{router}:{mode}", "model": router, "mode": mode, "router": True})
    for b in baselines:
        arms.append({"name": f"fixed:{b}", "model": b, "mode": None, "router": False})
    return arms


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--endpoint", help="Foundry resource or project endpoint")
    p.add_argument("--tenant", help="Use AzureCliCredential for this tenant instead of DefaultAzureCredential")
    p.add_argument("--router", help="Model router deployment name, or 'auto'")
    p.add_argument("--modes", default="deployment",
                   help="Comma list of router arms: deployment (no override), balanced, cost, quality")
    p.add_argument("--baseline", action="append", default=[], help="Fixed-model deployment (repeatable)")
    p.add_argument("--cases", help="JSON Lines: {id, tier, prompt, expect (regex), reasoning_effort?}")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--max-output-tokens", type=int, default=4000)
    p.add_argument("--region", default="swedencentral", help="Retail price region (armRegionName)")
    p.add_argument("--zone", choices=("global", "datazone"), default="global",
                   help="Deployment type to price: Global Standard or Data Zone Standard")
    p.add_argument("--fee-excludes-cached", action="store_true",
                   help="Sensitivity: charge the fee on uncached input only (undocumented; default charges all input)")
    p.add_argument("--price-file", help="JSON {model: {input, cached, output}} USD per 1M; overrides retail lookup")
    p.add_argument("--price-timeout", type=float, default=20.0, help="Seconds per Retail Prices API page")
    p.add_argument("--timeout", type=float, default=180.0, help="Seconds per inference request")
    p.add_argument("--prices-only", action="store_true", help="Only print router fee and prices for --models")
    p.add_argument("--models", default="", help="Comma list of models for --prices-only")
    args = p.parse_args(argv)

    try:
        items = fetch_retail_items(args.region, timeout=args.price_timeout)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "price_lookup", "detail": f"{type(exc).__name__}: {exc}"}))
        return 2
    fee = router_fee(items, args.zone)
    if fee is None:
        print(json.dumps({"error": "price_lookup", "detail": f"no {ROUTER_FEE_METERS[args.zone]} meter in {args.region}"}))
        return 2
    overrides = json.load(open(args.price_file, encoding="utf-8")) if args.price_file else {}

    def price(model: str) -> dict[str, float] | None:
        return overrides.get(model) or model_prices(items, model, args.zone)

    source = {"retail_api": RETAIL_URL, "region": args.region, "zone": args.zone,
              "router_fee_meter": ROUTER_FEE_METERS[args.zone], "router_fee_usd_per_1m_input": fee,
              "fee_charged_on": "uncached input (sensitivity)" if args.fee_excludes_cached else "all input tokens"}

    if args.prices_only:
        models = [base_model(m) for m in args.models.split(",") if m.strip()]
        prices = {m: price(m) for m in models}
        print(json.dumps({"prices": source, "fee_vs_model_price": fee_share_table(fee, prices)}, indent=2))
        return 0 if all(prices.values()) else 1

    if not (args.endpoint and args.cases and (args.router or args.baseline)):
        p.error("--endpoint, --cases and --router and/or --baseline are required")
    try:
        cases = load_cases(args.cases)
        arms = build_arms(args.router, [m.strip() for m in args.modes.split(",") if m.strip()], args.baseline)
    except (OSError, ValueError, re.error) as exc:
        print(json.dumps({"error": "config", "detail": str(exc)}))
        return 2

    client = make_client(args.endpoint, args.tenant, args.timeout)
    results, seen = [], {}
    for arm in arms:
        records = run_arm(client, arm, cases, args.repeats, args.max_output_tokens)
        for r in records:
            if "model" in r and r["model"] not in seen:
                seen[r["model"]] = price(r["model"])
        results.append(summarize(arm, records, seen, fee, args.fee_excludes_cached))

    report = {"prices": source, "cases": len(cases), "repeats": args.repeats, "arms": results,
              "fee_vs_model_price": fee_share_table(fee, seen),
              "note": "Estimates from list prices; billed costs are in Cost Management."}
    print(json.dumps(report, indent=2))
    if any(r["errors"] == r["tasks"] for r in results):
        return 2
    return 1 if any(r["unpriced_models"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
