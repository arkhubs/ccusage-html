from __future__ import annotations

from typing import Any


TOKEN_FIELDS = (
    "inputTokens",
    "outputTokens",
    "reasoningOutputTokens",
    "cacheCreationTokens",
    "cacheReadTokens",
    "totalTokens",
)


METRIC_LABELS = {
    "totalTokens": "Total tokens",
    "inputTokens": "Input",
    "outputTokens": "Output",
    "reasoningOutputTokens": "Reasoning",
    "costUSD": "Cost",
    "cacheReadTokens": "Cache read",
    "cacheCreationTokens": "Cache creation",
}


COST_FIELDS = ("costUSD", "totalCost", "cost")


def add_derived_fields(entry: dict[str, Any]) -> None:
    entry["contextTokens"] = (
        number(entry.get("inputTokens"))
        + number(entry.get("cacheCreationTokens"))
        + number(entry.get("cacheReadTokens"))
    )
    entry["generationTokens"] = number(entry.get("outputTokens")) + number(entry.get("reasoningOutputTokens"))


def list_from_payload(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for value in payload.values():
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
    return []


def number(value: Any) -> float:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return 0
    return 0


def optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def metadata_value(source: dict[str, Any], key: str) -> Any:
    metadata = source.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def usage_number(source: dict[str, Any], field: str) -> float:
    if field in source:
        return number(source.get(field))
    if field == "reasoningOutputTokens":
        return number(metadata_value(source, field))
    return 0


def has_usage_field(source: dict[str, Any], field: str) -> bool:
    if field in source:
        return True
    return field == "reasoningOutputTokens" and metadata_value(source, field) is not None


def has_cost(source: dict[str, Any]) -> bool:
    return any(field in source for field in COST_FIELDS)


def cost_number(source: dict[str, Any]) -> float:
    for field in COST_FIELDS:
        if field in source:
            return number(source.get(field))
    return 0


def has_billable_usage(source: dict[str, Any]) -> bool:
    return any(
        usage_number(source, field) > 0
        for field in ("inputTokens", "outputTokens", "cacheCreationTokens", "cacheReadTokens")
    )


def zero_cost_looks_missing(source: dict[str, Any]) -> bool:
    return has_cost(source) and cost_number(source) == 0 and has_billable_usage(source)


def fill_total_tokens(entry: dict[str, Any]) -> None:
    if number(entry.get("totalTokens")):
        return
    entry["totalTokens"] = sum(
        number(entry.get(field))
        for field in TOKEN_FIELDS
        if field != "totalTokens"
    )


def add_token_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in TOKEN_FIELDS:
        target[field] = number(target.get(field)) + usage_number(source, field)
    if has_cost(source) or has_cost(target):
        target["costUSD"] = cost_number(target) + cost_number(source)


def normalize_models(models: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(models, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for model, values in models.items():
        if isinstance(values, dict):
            entry = {field: usage_number(values, field) for field in TOKEN_FIELDS}
            if has_cost(values):
                if zero_cost_looks_missing(values):
                    entry["reportedCostUSD"] = 0
                else:
                    entry["costUSD"] = cost_number(values)
            fill_total_tokens(entry)
            add_derived_fields(entry)
            entry["isFallback"] = bool(values.get("isFallback", False))
            normalized[str(model)] = entry
    return normalized


def normalize_model_breakdowns(model_breakdowns: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(model_breakdowns, list):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for values in model_breakdowns:
        if not isinstance(values, dict):
            continue
        model = values.get("modelName") or values.get("model") or values.get("name")
        if not model:
            continue
        entry = normalized.setdefault(str(model), {})
        for field in TOKEN_FIELDS:
            if field == "totalTokens" and not has_usage_field(values, field):
                continue
            entry[field] = number(entry.get(field)) + usage_number(values, field)
        if has_cost(values) or has_cost(entry):
            if zero_cost_looks_missing(values):
                entry["reportedCostUSD"] = number(entry.get("reportedCostUSD")) + cost_number(values)
            else:
                entry["costUSD"] = cost_number(entry) + cost_number(values)
    for entry in normalized.values():
        fill_total_tokens(entry)
        add_derived_fields(entry)
    return normalized


def normalize_item_models(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    models = normalize_models(item.get("models"))
    if models:
        return models
    return normalize_model_breakdowns(item.get("modelBreakdowns"))


def period_label(item: dict[str, Any], period: str) -> str:
    if period == "daily":
        return str(item.get("date") or item.get("day") or item.get("period") or item.get("label") or "Unknown")
    if period == "monthly":
        return str(item.get("month") or item.get("period") or item.get("date") or item.get("label") or "Unknown")
    return str(item.get("week") or item.get("period") or item.get("date") or item.get("label") or "Unknown")


def normalize_bucket(item: dict[str, Any], period: str) -> dict[str, Any]:
    bucket = {"label": period_label(item, period), "models": normalize_item_models(item)}
    for field in TOKEN_FIELDS:
        bucket[field] = usage_number(item, field)
    if has_cost(item):
        bucket["costUSD"] = cost_number(item)
    add_derived_fields(bucket)
    return bucket


def discover_models(*collections: list[dict[str, Any]]) -> list[str]:
    models: set[str] = set()
    for collection in collections:
        for item in collection:
            for model in item.get("models", {}).keys():
                models.add(model)
    return sorted(models)


def aggregate_totals(collection: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {}
    for item in collection:
        add_token_fields(totals, item)
    return totals
