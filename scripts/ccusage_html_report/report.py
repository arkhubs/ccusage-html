from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .ccusage import normalize_agent_selector, run_ccusage


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


def collect_model_pricing(models: list[str], disabled: bool = False) -> dict[str, Any]:
    if disabled:
        return {
            "models": {},
            "unit": "USD per 1M tokens",
            "sources": [{"name": "pricing", "status": "disabled", "reason": "--no-cost was used"}],
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
    if not isinstance(price, dict) or price.get("source") == "unavailable":
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
            if not has_cost(usage):
                estimated = estimate_cost_usd(usage, price_models.get(model))
                if estimated is None:
                    all_models_have_cost = False
                else:
                    usage["costUSD"] = estimated
                    usage["costSource"] = "estimatedFromModelPrice"
            if has_cost(usage):
                model_cost_total += cost_number(usage)
            else:
                all_models_have_cost = False

        if all_models_have_cost and not has_cost(item):
            item["costUSD"] = model_cost_total
            item["costSource"] = "estimatedFromModelPrice"


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


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def iso_week_label_from_date(date_text: str) -> str:
    try:
        day = datetime.fromisoformat(date_text[:10]).date()
    except ValueError:
        return "Unknown"
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def synthesize_weekly(daily_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in daily_items:
        label = iso_week_label_from_date(str(item.get("date") or item.get("label") or ""))
        group = groups.setdefault(label, {"label": label, "week": label, "models": {}})
        add_token_fields(group, item)
        for model, values in normalize_item_models(item).items():
            model_group = group["models"].setdefault(model, {})
            add_token_fields(model_group, values)

    def sort_key(entry: dict[str, Any]) -> str:
        return str(entry.get("label", ""))

    return sorted((normalize_bucket(group, "weekly") for group in groups.values()), key=sort_key)


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


def trim_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "..."


def extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    if isinstance(content, dict):
        for key in ("text", "content", "message"):
            if isinstance(content.get(key), str):
                return content[key]
    return ""


def looks_like_context_noise(text: str) -> bool:
    if not text.strip():
        return True
    markers = (
        "<INSTRUCTIONS>",
        "<environment_context>",
        "AGENTS.md instructions for",
        '"dynamic_tools"',
        "# Global Agent Settings",
    )
    if len(text) > 1500 and any(marker in text for marker in markers):
        return True
    if text.startswith("Knowledge cutoff:") and len(text) > 500:
        return True
    return False


def codex_session_path(session: dict[str, Any], sessions_root: Path) -> Path | None:
    session_id = str(session.get("sessionId") or "").strip()
    if session_id:
        parts = [part for part in re.split(r"[\\/]+", session_id) if part]
        if parts:
            candidate = sessions_root.joinpath(*parts[:-1], parts[-1] + ".jsonl")
            if candidate.exists():
                return candidate

    directory = str(session.get("directory") or "").strip()
    session_file = str(session.get("sessionFile") or "").strip()
    if directory and session_file:
        parts = [part for part in re.split(r"[\\/]+", directory) if part]
        candidate = sessions_root.joinpath(*parts, session_file + ".jsonl")
        if candidate.exists():
            return candidate
    return None


def enrich_codex_session(
    session: dict[str, Any],
    sessions_root: Path,
    max_snippets: int,
    max_chars: int,
) -> dict[str, Any]:
    path = codex_session_path(session, sessions_root)
    title = ""
    snippets: list[dict[str, str]] = []
    conversation: list[dict[str, Any]] = []

    if path and path.exists():
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") != "response_item":
                        continue
                    payload = event.get("payload")
                    if not isinstance(payload, dict) or payload.get("type") != "message":
                        continue
                    role = payload.get("role")
                    if role not in ("user", "assistant"):
                        continue
                    text = extract_content_text(payload.get("content"))
                    if looks_like_context_noise(text):
                        continue
                    raw_text = text.strip()
                    compact = trim_text(raw_text, max_chars)
                    if role == "user" and not title:
                        title = trim_text(re.sub(r"^[#>\-\s]+", "", compact), 96)
                    conversation.append(
                        {
                            "role": str(role),
                            "text": raw_text,
                            "time": str(event.get("timestamp") or ""),
                            "chars": len(raw_text),
                        }
                    )
                    if len(snippets) < max_snippets:
                        snippets.append(
                            {
                                "role": str(role),
                                "text": compact,
                                "time": str(event.get("timestamp") or ""),
                            }
                        )
        except OSError:
            pass

    if not title:
        title = str(session.get("sessionFile") or session.get("sessionId") or "Untitled session")
        title = trim_text(title, 96)
    session["title"] = title
    session["snippets"] = snippets
    session["conversation"] = conversation
    session["transcriptPath"] = str(path) if path else ""
    return session


def session_agent_name(item: dict[str, Any], selected_agent: str) -> str:
    for key in ("agent", "source", "provider", "cli"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_agent_selector(value)
    return normalize_agent_selector(selected_agent)


def normalize_session(
    item: dict[str, Any],
    agent: str,
    sessions_root: Path | None,
    include_transcript: bool,
    max_snippets: int,
    max_chars: int,
) -> dict[str, Any]:
    session = dict(item)
    if not session.get("sessionId") and isinstance(item.get("period"), str):
        session["sessionId"] = item["period"]
    session["reportSessionId"] = trim_text(
        str(session.get("sessionId") or session.get("sessionFile") or session.get("period") or id(item)),
        220,
    )
    item_agent = session_agent_name(item, agent)
    session["agentName"] = item_agent
    models = normalize_item_models(item)
    session["models"] = models
    model_names = sorted(models.keys())
    if not model_names and isinstance(item.get("modelsUsed"), list):
        model_names = sorted(str(model) for model in item["modelsUsed"] if model)
    session["modelNames"] = model_names
    for field in TOKEN_FIELDS:
        session[field] = usage_number(item, field)
    if has_cost(item):
        session["costUSD"] = cost_number(item)
    add_derived_fields(session)

    dt = parse_iso_datetime(item.get("lastActivity") or metadata_value(item, "lastActivity"))
    if dt:
        date_label = dt.date().isoformat()
    else:
        directory = str(item.get("directory") or item.get("period") or "").replace("\\", "/")
        match = re.search(r"(\d{4})/(\d{2})/(\d{2})", directory)
        date_label = "-".join(match.groups()) if match else "Unknown"
    session["date"] = date_label
    session["week"] = iso_week_label_from_date(date_label)
    session["month"] = date_label[:7] if re.match(r"\d{4}-\d{2}", date_label) else "Unknown"

    try_codex_transcript = include_transcript and sessions_root and (agent in ("all", "codex") or item_agent == "codex")
    if try_codex_transcript:
        session = enrich_codex_session(session, sessions_root, max_snippets, max_chars)
    else:
        session.setdefault("title", str(item.get("sessionFile") or item.get("sessionId") or "Untitled session"))
        session.setdefault("snippets", [])
        session.setdefault("conversation", [])
        session.setdefault("transcriptPath", "")
    return session


def collect_ccusage_payloads(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    payloads = {
        "daily": run_ccusage(args, "daily"),
        "monthly": run_ccusage(args, "monthly"),
        "session": run_ccusage(args, "session"),
    }
    payloads["weekly"] = {} if args.agent == "codex" else run_ccusage(args, "weekly", required=False)
    return payloads


def build_report_data_from_payloads(args: argparse.Namespace, payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    daily_payload = payloads.get("daily", {})
    monthly_payload = payloads.get("monthly", {})
    session_payload = payloads.get("session", {})

    daily = [normalize_bucket(item, "daily") for item in list_from_payload(daily_payload, "daily", "days")]
    monthly = [normalize_bucket(item, "monthly") for item in list_from_payload(monthly_payload, "monthly", "months")]

    weekly_payload = payloads.get("weekly", {})
    weekly_items = list_from_payload(weekly_payload, "weekly", "weeks")
    weekly = [normalize_bucket(item, "weekly") for item in weekly_items] if weekly_items else synthesize_weekly(daily)

    sessions_root = None
    if not args.no_transcript:
        sessions_root = Path(args.codex_sessions_dir).expanduser() if args.codex_sessions_dir else Path.home() / ".codex" / "sessions"

    raw_sessions = list_from_payload(session_payload, "sessions", "session")
    sessions = [
        normalize_session(
            item,
            args.agent,
            sessions_root,
            not args.no_transcript,
            args.max_snippets_per_session,
            args.max_snippet_chars,
        )
        for item in raw_sessions
    ]

    models = discover_models(daily, weekly, monthly, sessions)
    model_prices = collect_model_pricing(models, disabled=bool(args.no_cost))
    if not args.no_cost:
        for collection in (daily, weekly, monthly, sessions):
            apply_model_cost_estimates(collection, model_prices)

    totals = dict(daily_payload.get("totals") or session_payload.get("totals") or {})
    fallback_totals = aggregate_totals(daily or sessions)
    for field in TOKEN_FIELDS:
        if has_usage_field(totals, field):
            totals[field] = usage_number(totals, field)
        else:
            totals[field] = usage_number(fallback_totals, field)
    if has_cost(totals) or has_cost(fallback_totals):
        totals["costUSD"] = cost_number(totals) if has_cost(totals) else cost_number(fallback_totals)
    add_derived_fields(totals)

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent": args.agent,
        "agentInput": args.agent_input,
        "filters": {"since": args.since or "", "until": args.until or "", "timezone": args.timezone or ""},
        "models": models,
        "modelPrices": model_prices,
        "metricLabels": METRIC_LABELS,
        "periods": {"daily": daily, "weekly": weekly, "monthly": monthly},
        "sessions": sessions,
        "totals": totals,
        "source": {"ccusageBin": args.ccusage_bin, "transcripts": not args.no_transcript, "agentSelector": args.agent_input},
    }


def build_report_data(args: argparse.Namespace) -> dict[str, Any]:
    return build_report_data_from_payloads(args, collect_ccusage_payloads(args))
