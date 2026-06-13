from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .metrics import (
    TOKEN_FIELDS,
    cost_number,
    has_cost,
    number,
    optional_number,
)


PRICE_UNIT_SCALE = 1_000_000


PRICING_TIMEOUT_SECONDS = 5


MODELS_DEV_URL = "https://models.dev/api.json"


LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"


MODEL_COST_RATE_FIELDS = (
    ("inputTokens", "input"),
    ("outputTokens", "output"),
    ("cacheCreationTokens", "cacheCreation"),
    ("cacheReadTokens", "cacheRead"),
)


def fetch_json(url: str, timeout: int = PRICING_TIMEOUT_SECONDS) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "ccusage-html-report/0.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def normalize_price_entry(
    *,
    model: str,
    source: str,
    source_url: str,
    input_per_million: float | None,
    output_per_million: float | None,
    cache_creation_per_million: float | None,
    cache_read_per_million: float | None,
    max_input_tokens: float | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "matchedModel": model,
        "source": source,
        "sourceUrl": source_url,
        "unit": "USD per 1M tokens",
    }
    if input_per_million is not None:
        entry["input"] = input_per_million
    if output_per_million is not None:
        entry["output"] = output_per_million
    if cache_creation_per_million is not None:
        entry["cacheCreation"] = cache_creation_per_million
    if cache_read_per_million is not None:
        entry["cacheRead"] = cache_read_per_million
    if max_input_tokens is not None:
        entry["maxInputTokens"] = max_input_tokens
    return entry


def models_dev_prices(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    prices: dict[str, dict[str, Any]] = {}
    for provider in payload.values():
        if not isinstance(provider, dict):
            continue
        models = provider.get("models")
        if not isinstance(models, dict):
            continue
        for model, model_data in models.items():
            if not isinstance(model_data, dict):
                continue
            cost = model_data.get("cost")
            if not isinstance(cost, dict):
                continue
            limits = model_data.get("limit") if isinstance(model_data.get("limit"), dict) else {}
            entry = normalize_price_entry(
                model=str(model),
                source="models.dev",
                source_url=MODELS_DEV_URL,
                input_per_million=optional_number(cost.get("input")),
                output_per_million=optional_number(cost.get("output")),
                cache_creation_per_million=optional_number(cost.get("cache_write")),
                cache_read_per_million=optional_number(cost.get("cache_read")),
                max_input_tokens=optional_number(limits.get("context") if isinstance(limits, dict) else None),
            )
            if any(key in entry for key in ("input", "output", "cacheCreation", "cacheRead")):
                prices[str(model)] = entry
    return prices


def litellm_prices(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    prices: dict[str, dict[str, Any]] = {}
    for model, values in payload.items():
        if not isinstance(values, dict):
            continue
        entry = normalize_price_entry(
            model=str(model),
            source="LiteLLM",
            source_url=LITELLM_PRICING_URL,
            input_per_million=scale_token_price(values.get("input_cost_per_token")),
            output_per_million=scale_token_price(values.get("output_cost_per_token")),
            cache_creation_per_million=scale_token_price(values.get("cache_creation_input_token_cost")),
            cache_read_per_million=scale_token_price(values.get("cache_read_input_token_cost")),
            max_input_tokens=optional_number(values.get("max_input_tokens")),
        )
        if any(key in entry for key in ("input", "output", "cacheCreation", "cacheRead")):
            prices[str(model)] = entry
    return prices


def scale_token_price(value: Any) -> float | None:
    price = optional_number(value)
    return price * PRICE_UNIT_SCALE if price is not None else None


def find_pricing(model: str, price_map: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if model in price_map:
        return price_map[model]
    wanted = model.strip().lower()
    lower_map = {key.lower(): value for key, value in price_map.items()}
    if wanted in lower_map:
        return lower_map[wanted]
    suffix_matches = [
        value
        for key, value in lower_map.items()
        if key.rsplit("/", 1)[-1] == wanted
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    return None


def collect_model_pricing(models: list[str], disabled: bool = False, disable_reason: str = "") -> dict[str, Any]:
    if disabled:
        return {
            "models": {},
            "unit": "USD per 1M tokens",
            "sources": [{"name": "pricing", "status": "disabled", "reason": disable_reason or "price fetch disabled"}],
        }
    if not models:
        return {"models": {}, "unit": "USD per 1M tokens", "sources": []}

    sources: list[dict[str, str]] = []
    matched: dict[str, dict[str, Any]] = {}
    source_loaders = (
        ("models.dev", MODELS_DEV_URL, models_dev_prices),
        ("LiteLLM", LITELLM_PRICING_URL, litellm_prices),
    )
    for name, url, parser in source_loaders:
        try:
            price_map = parser(fetch_json(url))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            sources.append({"name": name, "url": url, "status": "unavailable", "reason": str(exc)})
            continue
        sources.append({"name": name, "url": url, "status": "ok"})
        for model in models:
            if model in matched:
                continue
            price = find_pricing(model, price_map)
            if price:
                matched[model] = price
        if len(matched) == len(models):
            break

    for model in models:
        matched.setdefault(model, {"source": "unavailable", "unit": "USD per 1M tokens"})
    return {"models": matched, "unit": "USD per 1M tokens", "sources": sources}


def estimate_cost_usd(usage: dict[str, Any], price: dict[str, Any] | None) -> float | None:
    if not isinstance(price, dict) or price.get("source") in ("unavailable", "disabled"):
        return None

    total = 0.0
    has_priced_tokens = False
    for token_field, price_field in MODEL_COST_RATE_FIELDS:
        tokens = number(usage.get(token_field))
        if not tokens:
            continue
        rate = optional_number(price.get(price_field))
        if rate is None:
            return None
        total += tokens * rate / PRICE_UNIT_SCALE
        has_priced_tokens = True
    return total if has_priced_tokens else 0.0


def model_cost_should_be_estimated(usage: dict[str, Any], estimated: float | None) -> bool:
    if estimated is None or estimated <= 0:
        return False
    if not has_cost(usage):
        return True
    return cost_number(usage) == 0 and any(number(usage.get(field)) > 0 for field in TOKEN_FIELDS)


def apply_model_cost_estimates(collection: list[dict[str, Any]], pricing: dict[str, Any]) -> None:
    price_models = pricing.get("models")
    if not isinstance(price_models, dict):
        return

    for item in collection:
        models = item.get("models")
        if not isinstance(models, dict) or not models:
            continue

        model_cost_total = 0.0
        all_models_have_cost = True
        for model, usage in models.items():
            if not isinstance(usage, dict):
                all_models_have_cost = False
                continue
            estimated = estimate_cost_usd(usage, price_models.get(model))
            if model_cost_should_be_estimated(usage, estimated):
                if has_cost(usage):
                    usage["reportedCostUSD"] = cost_number(usage)
                usage["costUSD"] = estimated
                usage["costSource"] = "estimatedFromModelPrice"
            elif not has_cost(usage):
                all_models_have_cost = False
            if has_cost(usage):
                model_cost_total += cost_number(usage)
            else:
                all_models_have_cost = False

        if all_models_have_cost and not has_cost(item):
            item["costUSD"] = model_cost_total
            item["costSource"] = "estimatedFromModelPrice"
