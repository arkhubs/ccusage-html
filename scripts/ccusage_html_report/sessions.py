from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .ccusage import normalize_agent_selector
from .dates import datetime_sort_value, iso_week_label_from_date, parse_datetime_from_text
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
    last_conversation_time: datetime | None = None

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
                    turn_time = str(event.get("timestamp") or "")
                    parsed_turn_time = parse_datetime_from_text(turn_time)
                    if parsed_turn_time and (
                        last_conversation_time is None
                        or datetime_sort_value(parsed_turn_time) > datetime_sort_value(last_conversation_time)
                    ):
                        last_conversation_time = parsed_turn_time
                    if role == "user" and not title:
                        title = trim_text(re.sub(r"^[#>\-\s]+", "", compact), 96)
                    conversation.append(
                        {
                            "role": str(role),
                            "text": raw_text,
                            "time": turn_time,
                            "chars": len(raw_text),
                        }
                    )
                    if len(snippets) < max_snippets:
                        snippets.append(
                            {
                                "role": str(role),
                                "text": compact,
                                "time": turn_time,
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
    if last_conversation_time and not session.get("sortTime"):
        session["lastActivityAt"] = last_conversation_time.isoformat()
        session["sortTime"] = datetime_sort_value(last_conversation_time)
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

    dt = session_datetime(item)
    if dt:
        date_label = dt.date().isoformat()
    else:
        date_label = "Unknown"
    session["date"] = date_label
    session["week"] = iso_week_label_from_date(date_label)
    session["month"] = date_label[:7] if re.match(r"\d{4}-\d{2}", date_label) else "Unknown"
    session["lastActivityAt"] = dt.isoformat() if dt else ""
    session["sortTime"] = datetime_sort_value(dt)

    try_codex_transcript = include_transcript and sessions_root and (agent in ("all", "codex") or item_agent == "codex")
    if try_codex_transcript:
        session = enrich_codex_session(session, sessions_root, max_snippets, max_chars)
    else:
        session.setdefault("title", str(item.get("sessionFile") or item.get("sessionId") or "Untitled session"))
        session.setdefault("snippets", [])
        session.setdefault("conversation", [])
        session.setdefault("transcriptPath", "")
    return session
