from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .ccusage import normalize_agent_selector
from .dates import datetime_sort_value, parse_datetime_from_text
from .metrics import (
    TOKEN_FIELDS,
    add_derived_fields,
    cost_number,
    has_cost,
    metadata_value,
    normalize_item_models,
    number,
    usage_number,
)
from .transcripts import TranscriptEnrichmentRegistry, set_session_datetime_fields, trim_text


def session_datetime(item: dict[str, Any]) -> datetime | None:
    candidates = (
        item.get("lastActivity"),
        metadata_value(item, "lastActivity"),
        item.get("timestamp"),
        metadata_value(item, "timestamp"),
        item.get("date"),
        item.get("period"),
        item.get("sessionId"),
        item.get("directory"),
        item.get("sessionFile"),
    )
    for candidate in candidates:
        parsed = parse_datetime_from_text(candidate)
        if parsed:
            return parsed
    return None


def sort_sessions_recent_first(sessions: list[dict[str, Any]]) -> None:
    sessions.sort(
        key=lambda session: (
            -number(session.get("sortTime")),
            str(session.get("title") or session.get("reportSessionId") or "").lower(),
        )
    )


def session_agent_name(item: dict[str, Any], selected_agent: str) -> str:
    for key in ("agent", "source", "provider", "cli"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_agent_selector(value)
    return normalize_agent_selector(selected_agent)


def normalize_session(
    item: dict[str, Any],
    agent: str,
    transcript_registry: TranscriptEnrichmentRegistry | None,
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

    set_session_datetime_fields(session, session_datetime(item))

    if include_transcript and transcript_registry and transcript_registry.enrich(
        session,
        item_agent,
        max_snippets,
        max_chars,
    ):
        return session

    session.setdefault("title", str(item.get("sessionFile") or item.get("sessionId") or "Untitled session"))
    session.setdefault("snippets", [])
    session.setdefault("conversation", [])
    session.setdefault("transcriptPath", "")
    return session
