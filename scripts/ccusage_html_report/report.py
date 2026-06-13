from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from .ccusage import run_ccusage
from .dates import (
    datetime_sort_value,
    iso_week_label_from_date,
    parse_datetime_from_text,
    parse_iso_datetime,
)
from .metrics import (
    COST_FIELDS,
    METRIC_LABELS,
    TOKEN_FIELDS,
    add_derived_fields,
    add_token_fields,
    aggregate_totals,
    cost_number,
    discover_models,
    fill_total_tokens,
    has_billable_usage,
    has_cost,
    has_usage_field,
    list_from_payload,
    metadata_value,
    normalize_bucket,
    normalize_item_models,
    normalize_model_breakdowns,
    normalize_models,
    number,
    optional_number,
    period_label,
    usage_number,
    zero_cost_looks_missing,
)
from .pricing import (
    LITELLM_PRICING_URL,
    MODEL_COST_RATE_FIELDS,
    MODELS_DEV_URL,
    PRICE_UNIT_SCALE,
    PRICING_TIMEOUT_SECONDS,
    apply_model_cost_estimates,
    collect_model_pricing,
    estimate_cost_usd,
    fetch_json,
    find_pricing,
    litellm_prices,
    model_cost_should_be_estimated,
    models_dev_prices,
    normalize_price_entry,
    scale_token_price,
)
from .sessions import normalize_session, sort_sessions_recent_first
from .transcripts import build_transcript_registry


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

    transcript_registry = None
    if not args.no_transcript:
        codex_sessions_root = Path(args.codex_sessions_dir).expanduser() if args.codex_sessions_dir else Path.home() / ".codex" / "sessions"
        gemini_sessions_dir = getattr(args, "gemini_sessions_dir", None)
        gemini_sessions_root = Path(gemini_sessions_dir).expanduser() if gemini_sessions_dir else Path.home() / ".gemini" / "tmp"
        transcript_registry = build_transcript_registry(args.agent, codex_sessions_root, gemini_sessions_root)

    raw_sessions = list_from_payload(session_payload, "sessions", "session")
    sessions = [
        normalize_session(
            item,
            args.agent,
            transcript_registry,
            not args.no_transcript,
            args.max_snippets_per_session,
            args.max_snippet_chars,
        )
        for item in raw_sessions
    ]

    models = discover_models(daily, weekly, monthly, sessions)
    price_disabled = bool(args.no_cost or getattr(args, "no_price_fetch", False))
    if args.no_cost:
        price_disable_reason = "--no-cost was used"
    elif getattr(args, "no_price_fetch", False):
        price_disable_reason = "--no-price-fetch was used"
    else:
        price_disable_reason = ""
    model_prices = collect_model_pricing(models, disabled=price_disabled, disable_reason=price_disable_reason)
    if not args.no_cost:
        for collection in (daily, weekly, monthly, sessions):
            apply_model_cost_estimates(collection, model_prices)

    sort_sessions_recent_first(sessions)

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
