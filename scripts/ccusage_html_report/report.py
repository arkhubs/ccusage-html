from __future__ import annotations

import argparse
import json
import re
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

    if path and path.exists():
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if len(snippets) >= max_snippets and title:
                        break
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
                    compact = trim_text(text, max_chars)
                    if role == "user" and not title:
                        title = trim_text(re.sub(r"^[#>\-\s]+", "", compact), 96)
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
        session.setdefault("transcriptPath", "")
    return session


def build_report_data(args: argparse.Namespace) -> dict[str, Any]:
    daily_payload = run_ccusage(args, "daily")
    monthly_payload = run_ccusage(args, "monthly")
    session_payload = run_ccusage(args, "session")

    daily = [normalize_bucket(item, "daily") for item in list_from_payload(daily_payload, "daily", "days")]
    monthly = [normalize_bucket(item, "monthly") for item in list_from_payload(monthly_payload, "monthly", "months")]

    weekly_payload = {}
    if args.agent != "codex":
        weekly_payload = run_ccusage(args, "weekly", required=False)
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
    totals = dict(daily_payload.get("totals") or session_payload.get("totals") or {})
    fallback_totals = aggregate_totals(daily or sessions)
    for field in TOKEN_FIELDS:
        if has_usage_field(totals, field):
            totals[field] = usage_number(totals, field)
        else:
            totals[field] = usage_number(fallback_totals, field)
    if has_cost(totals) or has_cost(fallback_totals):
        totals["costUSD"] = cost_number(totals) if has_cost(totals) else cost_number(fallback_totals)

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent": args.agent,
        "agentInput": args.agent_input,
        "filters": {"since": args.since or "", "until": args.until or "", "timezone": args.timezone or ""},
        "models": models,
        "metricLabels": METRIC_LABELS,
        "periods": {"daily": daily, "weekly": weekly, "monthly": monthly},
        "sessions": sessions,
        "totals": totals,
        "source": {"ccusageBin": args.ccusage_bin, "transcripts": not args.no_transcript, "agentSelector": args.agent_input},
    }
