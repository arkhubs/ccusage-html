from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .dates import datetime_sort_value, iso_week_label_from_date, parse_datetime_from_text


class TranscriptProvider:
    agent_name = ""

    def enrich(self, session: dict[str, Any], max_snippets: int, max_chars: int) -> dict[str, Any]:
        raise NotImplementedError


class TranscriptEnrichmentRegistry:
    def __init__(self, providers: list[TranscriptProvider] | None = None) -> None:
        self.providers = {provider.agent_name: provider for provider in providers or []}

    def enrich(
        self,
        session: dict[str, Any],
        agent_name: str,
        max_snippets: int,
        max_chars: int,
    ) -> bool:
        provider = self.providers.get(agent_name)
        if not provider:
            return False
        provider.enrich(session, max_snippets, max_chars)
        return True


def build_transcript_registry(
    selected_agent: str,
    codex_sessions_root: Path | None,
    gemini_sessions_root: Path | None,
) -> TranscriptEnrichmentRegistry:
    providers: list[TranscriptProvider] = []
    if selected_agent in ("all", "codex") and codex_sessions_root:
        providers.append(CodexTranscriptProvider(codex_sessions_root))
    if selected_agent in ("all", "gemini") and gemini_sessions_root:
        providers.append(GeminiTranscriptProvider(build_gemini_session_index(gemini_sessions_root)))
    return TranscriptEnrichmentRegistry(providers)


def set_session_datetime_fields(session: dict[str, Any], dt: datetime | None) -> None:
    if dt:
        date_label = dt.date().isoformat()
        session["lastActivityAt"] = dt.isoformat()
        session["sortTime"] = datetime_sort_value(dt)
    else:
        date_label = "Unknown"
        session["lastActivityAt"] = ""
        session["sortTime"] = 0
    session["date"] = date_label
    session["week"] = iso_week_label_from_date(date_label)
    session["month"] = date_label[:7] if re.match(r"\d{4}-\d{2}", date_label) else "Unknown"


def trim_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "..."


def trim_multiline_text(value: str, max_chars: int) -> str:
    text = value.strip()
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
                if "functionResponse" in item:
                    parts.append(extract_content_text(item.get("functionResponse")))
                else:
                    parts.append(extract_content_text(item))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    if isinstance(content, dict):
        parts: list[str] = []
        for key in ("text", "content", "message", "description", "resultDisplay", "output", "result", "response"):
            value = content.get(key)
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (dict, list)):
                nested = extract_content_text(value)
                if nested:
                    parts.append(nested)
        return "\n".join(part for part in parts if part)
    return ""


def compact_json(value: Any, max_chars: int = 1000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return trim_multiline_text(text, max_chars)


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def looks_like_context_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith("<session_context>"):
        return True
    markers = (
        "<INSTRUCTIONS>",
        "<environment_context>",
        "<session_context>",
        "AGENTS.md instructions for",
        '"dynamic_tools"',
        "# Global Agent Settings",
        "This is the Gemini CLI. We are setting up the context for our chat.",
    )
    if len(text) > 1500 and any(marker in text for marker in markers):
        return True
    if text.startswith("Knowledge cutoff:") and len(text) > 500:
        return True
    return False


def add_conversation_turn(
    conversation: list[dict[str, Any]],
    snippets: list[dict[str, str]],
    role: str,
    text: str,
    turn_time: str,
    max_snippets: int,
    max_chars: int,
    *,
    include_snippet: bool = True,
    extra: dict[str, Any] | None = None,
) -> str:
    raw_text = text.strip()
    if not raw_text or looks_like_context_noise(raw_text):
        return ""
    turn = {
        "role": role,
        "text": raw_text,
        "time": turn_time,
        "chars": len(raw_text),
    }
    if extra:
        for key, value in extra.items():
            if value not in (None, ""):
                turn[key] = value
    conversation.append(turn)
    if include_snippet and len(snippets) < max_snippets:
        snippets.append(
            {
                "role": role,
                "text": trim_text(raw_text, max_chars),
                "time": turn_time,
            }
        )
    return raw_text


def update_latest_datetime(current: datetime | None, candidate: Any) -> datetime | None:
    parsed = parse_datetime_from_text(candidate)
    if not parsed:
        return current
    if current is None or datetime_sort_value(parsed) > datetime_sort_value(current):
        return parsed
    return current


class CodexTranscriptProvider(TranscriptProvider):
    agent_name = "codex"

    def __init__(self, sessions_root: Path) -> None:
        self.sessions_root = sessions_root

    def enrich(self, session: dict[str, Any], max_snippets: int, max_chars: int) -> dict[str, Any]:
        return enrich_codex_session(session, self.sessions_root, max_snippets, max_chars)


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


def tool_call_identifier(payload: dict[str, Any]) -> str:
    for key in ("call_id", "callId", "tool_call_id", "toolCallId", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def tool_result_text_from_mapping(value: Any) -> str:
    if not isinstance(value, dict):
        return extract_content_text(value).strip()

    for key in (
        "toolResult",
        "toolResults",
        "functionResponse",
        "resultDisplay",
        "output",
        "result",
        "response",
        "content",
        "error",
    ):
        if key not in value:
            continue
        text = extract_content_text(value.get(key)).strip()
        if text:
            return text
    return ""


def attach_tool_result(turn: dict[str, Any], result: str, result_time: str) -> bool:
    result_text = result.strip()
    if not result_text:
        return False
    existing = str(turn.get("toolResult") or "").strip()
    combined = f"{existing}\n\n{result_text}" if existing else result_text
    turn["toolResult"] = combined
    turn["toolResultChars"] = len(combined)
    if result_time:
        turn["toolResultTime"] = result_time
    return True


def attach_tool_result_to_recent(
    conversation: list[dict[str, Any]],
    tool_turns_by_call_id: dict[str, dict[str, Any]],
    call_id: str,
    result: str,
    result_time: str,
) -> bool:
    turn = tool_turns_by_call_id.get(call_id) if call_id else None
    if not turn and call_id:
        for candidate in reversed(conversation):
            if candidate.get("role") == "tool" and str(candidate.get("toolCallId") or "") == call_id:
                turn = candidate
                break
    if not turn and conversation and conversation[-1].get("role") == "tool":
        turn = conversation[-1]
    return attach_tool_result(turn, result, result_time) if turn else False


def codex_tool_call_details(payload: dict[str, Any]) -> dict[str, str] | None:
    payload_type = str(payload.get("type") or "")
    if payload_type in ("function_call", "tool_call", "custom_tool_call"):
        name = str(payload.get("name") or payload.get("tool_name") or payload.get("recipient_name") or "tool")
        args = parse_json_object(payload.get("arguments") or payload.get("args") or payload.get("input"))
        lines = [f"Tool call: {name}"]
        command = args.get("command") or args.get("cmd")
        if command:
            lines.append(f"Command: {command}")
        workdir = args.get("workdir") or args.get("cwd")
        if workdir:
            lines.append(f"Workdir: {workdir}")
        remaining = {key: value for key, value in args.items() if key not in {"command", "cmd", "workdir", "cwd"}}
        if remaining:
            lines.append("Arguments:")
            lines.append(compact_json(remaining, 900))
        if not args and payload.get("arguments"):
            lines.append("Arguments:")
            lines.append(trim_multiline_text(str(payload.get("arguments")), 900))
        status = payload.get("status")
        if status:
            lines.append(f"Status: {status}")
        return {
            "summary": "\n".join(lines),
            "name": name,
            "call_id": tool_call_identifier(payload),
            "result": tool_result_text_from_mapping(payload),
        }

    return None


def codex_tool_result_details(payload: dict[str, Any]) -> dict[str, str] | None:
    payload_type = str(payload.get("type") or "")
    if payload_type not in ("function_call_output", "tool_call_output", "custom_tool_call_output"):
        return None

    result = tool_result_text_from_mapping(payload)
    if not result:
        remaining = {
            key: value
            for key, value in payload.items()
            if key not in {"type", "id", "call_id", "callId", "tool_call_id", "toolCallId"}
        }
        if remaining:
            result = compact_json(remaining, 2000)
    if not result:
        return None
    return {"call_id": tool_call_identifier(payload), "result": result}


def codex_user_tool_result_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("Output:"):
        return stripped[len("Output:") :].strip()

    match = re.search(r"(?m)^Output:\s*", stripped)
    if not match:
        return ""

    prefix = stripped[: match.start()].strip()
    if not prefix:
        return stripped[match.end() :].strip()

    allowed_prefixes = ("Current topic:", "Topic summary:", "Strategic Intent:")
    prefix_lines = [line.strip() for line in prefix.splitlines() if line.strip()]
    if prefix_lines and all(line.startswith(allowed_prefixes) for line in prefix_lines):
        return stripped[match.end() :].strip()
    return ""


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
    tool_turns_by_call_id: dict[str, dict[str, Any]] = {}
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
                    if not isinstance(payload, dict):
                        continue
                    turn_time = str(event.get("timestamp") or "")
                    last_conversation_time = update_latest_datetime(last_conversation_time, turn_time)
                    if payload.get("type") == "message":
                        role = payload.get("role")
                        if role not in ("user", "assistant"):
                            continue
                        message_text = extract_content_text(payload.get("content"))
                        if role == "user":
                            tool_result = codex_user_tool_result_text(message_text)
                            if tool_result and attach_tool_result_to_recent(
                                conversation,
                                tool_turns_by_call_id,
                                "",
                                tool_result,
                                turn_time,
                            ):
                                continue
                        raw_text = add_conversation_turn(
                            conversation,
                            snippets,
                            str(role),
                            message_text,
                            turn_time,
                            max_snippets,
                            max_chars,
                        )
                        if role == "user" and raw_text and not title:
                            title = trim_text(re.sub(r"^[#>\-\s]+", "", raw_text), 96)
                    else:
                        tool_result = codex_tool_result_details(payload)
                        if tool_result:
                            if not attach_tool_result_to_recent(
                                conversation,
                                tool_turns_by_call_id,
                                tool_result.get("call_id", ""),
                                tool_result.get("result", ""),
                                turn_time,
                            ):
                                add_conversation_turn(
                                    conversation,
                                    snippets,
                                    "tool",
                                    "Tool result",
                                    turn_time,
                                    max_snippets,
                                    max_chars,
                                    include_snippet=False,
                                    extra={
                                        "toolResult": tool_result.get("result", ""),
                                        "toolResultChars": len(tool_result.get("result", "")),
                                        "toolResultTime": turn_time,
                                    },
                                )
                            continue

                        tool_call = codex_tool_call_details(payload)
                        if tool_call:
                            add_conversation_turn(
                                conversation,
                                snippets,
                                "tool",
                                tool_call["summary"],
                                turn_time,
                                max_snippets,
                                max_chars,
                                include_snippet=False,
                                extra={
                                    "toolName": tool_call.get("name", ""),
                                    "toolCallId": tool_call.get("call_id", ""),
                                    "toolResult": tool_call.get("result", ""),
                                    "toolResultChars": len(tool_call.get("result", "")),
                                    "toolResultTime": turn_time if tool_call.get("result") else "",
                                },
                            )
                            call_id = tool_call.get("call_id", "")
                            if call_id and conversation:
                                tool_turns_by_call_id[call_id] = conversation[-1]
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
        set_session_datetime_fields(session, last_conversation_time)
    return session


class GeminiTranscriptProvider(TranscriptProvider):
    agent_name = "gemini"

    def __init__(self, session_index: dict[str, Path]) -> None:
        self.session_index = session_index

    def enrich(self, session: dict[str, Any], max_snippets: int, max_chars: int) -> dict[str, Any]:
        return enrich_gemini_session(session, self.session_index, max_snippets, max_chars)


def gemini_session_id_from_path(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(8192)
    except OSError:
        return ""
    match = re.search(r'"sessionId"\s*:\s*"([^"]+)"', head)
    return match.group(1) if match else ""


def build_gemini_session_index(root: Path | None) -> dict[str, Path]:
    if not root or not root.exists():
        return {}
    index: dict[str, Path] = {}
    try:
        paths = root.glob("**/chats/session-*.json*")
        for path in paths:
            if not path.is_file():
                continue
            session_id = gemini_session_id_from_path(path)
            if not session_id:
                continue
            existing = index.get(session_id)
            if existing is None or path.stat().st_mtime >= existing.stat().st_mtime:
                index[session_id] = path
            short_id = session_id.split("-", 1)[0]
            index.setdefault(short_id, path)
    except OSError:
        return index
    return index


def gemini_session_path(session: dict[str, Any], session_index: dict[str, Path]) -> Path | None:
    session_id = str(session.get("sessionId") or session.get("period") or "").strip()
    if not session_id:
        return None
    return session_index.get(session_id) or session_index.get(session_id.split("-", 1)[0])


def merge_gemini_message(existing: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in update.items():
        if key == "content" and not extract_content_text(value) and extract_content_text(merged.get(key)):
            continue
        if key in ("thoughts", "toolCalls") and not value and merged.get(key):
            continue
        merged[key] = value
    return merged


def read_gemini_session_file(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta: dict[str, Any] = {}
    messages_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def add_message(message: Any) -> None:
        if not isinstance(message, dict) or not message.get("type"):
            return
        key = str(message.get("id") or f"message-{len(order)}")
        if key in messages_by_id:
            messages_by_id[key] = merge_gemini_message(messages_by_id[key], message)
        else:
            messages_by_id[key] = dict(message)
            order.append(key)

    try:
        if path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict) and "sessionId" in item and "type" not in item:
                        meta.update(
                            {
                                key: item.get(key)
                                for key in ("sessionId", "projectHash", "startTime", "lastUpdated", "kind")
                                if key in item
                            }
                        )
                    if not isinstance(item, dict):
                        continue
                    update = item.get("$set")
                    if isinstance(update, dict):
                        meta.update(
                            {
                                key: update.get(key)
                                for key in ("sessionId", "startTime", "lastUpdated", "kind")
                                if key in update
                            }
                        )
                        for message in update.get("messages") or []:
                            add_message(message)
                    add_message(item)
        else:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                meta.update(
                    {
                        key: data.get(key)
                        for key in ("sessionId", "projectHash", "startTime", "lastUpdated", "kind")
                        if key in data
                    }
                )
                for message in data.get("messages") or []:
                    add_message(message)
    except (OSError, json.JSONDecodeError):
        return meta, []

    return meta, [messages_by_id[key] for key in order]


def gemini_message_role(message: dict[str, Any]) -> str:
    message_type = str(message.get("type") or "").lower()
    if message_type == "user":
        return "user"
    if message_type in ("gemini", "assistant", "model"):
        return "assistant"
    return "tool"


def gemini_message_text(message: dict[str, Any]) -> str:
    text = extract_content_text(message.get("content")).strip()
    if text:
        return text

    if str(message.get("type") or "").lower() == "gemini":
        parts: list[str] = []
        for thought in message.get("thoughts") or []:
            if not isinstance(thought, dict):
                continue
            subject = str(thought.get("subject") or "").strip()
            description = extract_content_text(thought.get("description")).strip()
            if subject and description:
                parts.append(f"{subject}\n{description}")
            elif description:
                parts.append(description)
        return "\n\n".join(parts)

    return ""


def gemini_tool_call_turns(message: dict[str, Any]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    for call in message.get("toolCalls") or []:
        if not isinstance(call, dict):
            continue
        name = str(call.get("displayName") or call.get("name") or "tool")
        lines = [f"Tool call: {name}"]
        description = str(call.get("description") or "").strip()
        if description:
            lines.append(f"Description: {description}")
        args = call.get("args")
        if args:
            lines.append("Arguments:")
            lines.append(compact_json(args, 900))
        status = call.get("status")
        if status:
            lines.append(f"Status: {status}")
        turns.append(
            {
                "summary": "\n".join(lines),
                "time": str(call.get("timestamp") or message.get("timestamp") or ""),
                "name": name,
                "result": tool_result_text_from_mapping(call),
            }
        )
    return turns


def enrich_gemini_session(
    session: dict[str, Any],
    session_index: dict[str, Path],
    max_snippets: int,
    max_chars: int,
) -> dict[str, Any]:
    path = gemini_session_path(session, session_index)
    title = ""
    snippets: list[dict[str, str]] = []
    conversation: list[dict[str, Any]] = []
    last_conversation_time: datetime | None = None

    if path and path.exists():
        meta, messages = read_gemini_session_file(path)
        last_conversation_time = update_latest_datetime(last_conversation_time, meta.get("startTime"))
        last_conversation_time = update_latest_datetime(last_conversation_time, meta.get("lastUpdated"))
        for message in messages:
            turn_time = str(message.get("timestamp") or "")
            last_conversation_time = update_latest_datetime(last_conversation_time, turn_time)
            role = gemini_message_role(message)
            raw_text = add_conversation_turn(
                conversation,
                snippets,
                role,
                gemini_message_text(message),
                turn_time,
                max_snippets,
                max_chars,
                include_snippet=role in ("user", "assistant"),
            )
            if role == "user" and raw_text and not title:
                title = trim_text(re.sub(r"^[#>\-\s]+", "", raw_text), 96)
            for tool_turn in gemini_tool_call_turns(message):
                tool_time = tool_turn.get("time", "")
                last_conversation_time = update_latest_datetime(last_conversation_time, tool_time)
                add_conversation_turn(
                    conversation,
                    snippets,
                    "tool",
                    tool_turn.get("summary", ""),
                    tool_time,
                    max_snippets,
                    max_chars,
                    include_snippet=False,
                    extra={
                        "toolName": tool_turn.get("name", ""),
                        "toolResult": tool_turn.get("result", ""),
                        "toolResultChars": len(tool_turn.get("result", "")),
                        "toolResultTime": tool_time if tool_turn.get("result") else "",
                    },
                )

    if not title:
        title = str(session.get("sessionFile") or session.get("sessionId") or "Untitled session")
        title = trim_text(title, 96)
    session["title"] = title
    session["snippets"] = snippets
    session["conversation"] = conversation
    session["transcriptPath"] = str(path) if path else ""
    if last_conversation_time:
        set_session_datetime_fields(session, last_conversation_time)
    return session
