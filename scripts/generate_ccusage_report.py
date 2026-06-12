#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
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
    "cacheReadTokens": "Cache read",
    "cacheCreationTokens": "Cache creation",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a polished standalone HTML dashboard from ccusage JSON output."
    )
    parser.add_argument("--agent", default="codex", help="ccusage agent: codex, claude, all, etc.")
    parser.add_argument("--since", help="Start date accepted by ccusage, e.g. 2026-06-01.")
    parser.add_argument("--until", help="End date accepted by ccusage, e.g. 2026-06-30.")
    parser.add_argument("--timezone", help="IANA timezone passed through to ccusage.")
    parser.add_argument("--output", help="Output HTML path. Defaults to ~/.codex/tmp.")
    parser.add_argument("--ccusage-bin", default="ccusage", help="ccusage executable name or path.")
    parser.add_argument("--offline", action="store_true", help="Use ccusage cached pricing data where supported.")
    parser.add_argument("--no-cost", action="store_true", help="Hide cost data in ccusage output.")
    parser.add_argument(
        "--speed",
        default="auto",
        choices=("auto", "standard", "fast"),
        help="Codex cost speed tier passed to ccusage codex commands.",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Do not enrich sessions with local chat snippets.",
    )
    parser.add_argument(
        "--codex-sessions-dir",
        help="Override the Codex sessions directory. Defaults to ~/.codex/sessions.",
    )
    parser.add_argument(
        "--max-snippets-per-session",
        type=int,
        default=6,
        help="Maximum chat snippets embedded per session.",
    )
    parser.add_argument(
        "--max-snippet-chars",
        type=int,
        default=420,
        help="Maximum characters per embedded chat snippet.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="After generating the HTML, serve its directory over a local HTTP backend.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for --serve.")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for --serve. Use 0 to choose a free port.",
    )
    return parser.parse_args()


def wrap_executable(executable: str, rest: list[str]) -> list[str]:
    resolved = shutil.which(executable) or executable
    if os.name == "nt" and str(resolved).lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved, *rest]
    return [resolved, *rest]


def ccusage_command(args: argparse.Namespace, scope: str) -> list[str]:
    rest: list[str]
    if args.agent.lower() in ("all", "auto"):
        rest = [scope]
    else:
        rest = [args.agent, scope]

    rest.append("--json")
    if args.since:
        rest.extend(["--since", args.since])
    if args.until:
        rest.extend(["--until", args.until])
    if args.timezone:
        rest.extend(["--timezone", args.timezone])
    if args.offline:
        rest.append("--offline")
    if args.no_cost:
        rest.append("--no-cost")
    if args.agent.lower() == "codex" and scope in ("daily", "monthly", "session"):
        rest.extend(["--speed", args.speed])
    return wrap_executable(args.ccusage_bin, rest)


def run_ccusage(args: argparse.Namespace, scope: str, required: bool = True) -> dict[str, Any]:
    cmd = ccusage_command(args, scope)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        if required:
            joined = " ".join(cmd)
            raise SystemExit(f"ccusage failed for {scope}: {joined}\n{proc.stderr.strip()}")
        return {}

    stdout = proc.stdout.strip()
    if not stdout:
        return {}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        if required:
            preview = stdout[:400].replace("\n", " ")
            raise SystemExit(f"ccusage {scope} did not return JSON. Preview: {preview}")
        return {}


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


def add_token_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in TOKEN_FIELDS:
        target[field] = number(target.get(field)) + number(source.get(field))
    if "costUSD" in source or "costUSD" in target:
        target["costUSD"] = number(target.get("costUSD")) + number(source.get("costUSD"))


def normalize_models(models: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(models, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for model, values in models.items():
        if isinstance(values, dict):
            entry = {field: number(values.get(field)) for field in TOKEN_FIELDS}
            if "costUSD" in values:
                entry["costUSD"] = number(values.get("costUSD"))
            entry["isFallback"] = bool(values.get("isFallback", False))
            normalized[str(model)] = entry
    return normalized


def period_label(item: dict[str, Any], period: str) -> str:
    if period == "daily":
        return str(item.get("date") or item.get("day") or item.get("label") or "Unknown")
    if period == "monthly":
        return str(item.get("month") or item.get("date") or item.get("label") or "Unknown")
    return str(item.get("week") or item.get("date") or item.get("label") or "Unknown")


def normalize_bucket(item: dict[str, Any], period: str) -> dict[str, Any]:
    bucket = {"label": period_label(item, period), "models": normalize_models(item.get("models"))}
    for field in TOKEN_FIELDS:
        bucket[field] = number(item.get(field))
    if "costUSD" in item:
        bucket["costUSD"] = number(item.get("costUSD"))
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
        for model, values in normalize_models(item.get("models")).items():
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


def normalize_session(
    item: dict[str, Any],
    agent: str,
    sessions_root: Path | None,
    include_transcript: bool,
    max_snippets: int,
    max_chars: int,
) -> dict[str, Any]:
    session = dict(item)
    models = normalize_models(item.get("models"))
    session["models"] = models
    session["modelNames"] = sorted(models.keys())
    for field in TOKEN_FIELDS:
        session[field] = number(item.get(field))
    if "costUSD" in item:
        session["costUSD"] = number(item.get("costUSD"))

    dt = parse_iso_datetime(item.get("lastActivity"))
    if dt:
        date_label = dt.date().isoformat()
    else:
        directory = str(item.get("directory") or "").replace("\\", "/")
        match = re.search(r"(\d{4})/(\d{2})/(\d{2})", directory)
        date_label = "-".join(match.groups()) if match else "Unknown"
    session["date"] = date_label
    session["week"] = iso_week_label_from_date(date_label)
    session["month"] = date_label[:7] if re.match(r"\d{4}-\d{2}", date_label) else "Unknown"

    if include_transcript and agent.lower() == "codex" and sessions_root:
        session = enrich_codex_session(session, sessions_root, max_snippets, max_chars)
    else:
        session.setdefault("title", str(item.get("sessionFile") or item.get("sessionId") or "Untitled session"))
        session.setdefault("snippets", [])
        session.setdefault("transcriptPath", "")
    return session


def default_output_path() -> Path:
    out_dir = Path.home() / ".codex" / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return out_dir / f"ccusage-report-{stamp}.html"


def build_report_data(args: argparse.Namespace) -> dict[str, Any]:
    daily_payload = run_ccusage(args, "daily")
    monthly_payload = run_ccusage(args, "monthly")
    session_payload = run_ccusage(args, "session")

    daily = [normalize_bucket(item, "daily") for item in list_from_payload(daily_payload, "daily", "days")]
    monthly = [normalize_bucket(item, "monthly") for item in list_from_payload(monthly_payload, "monthly", "months")]

    weekly_payload = {}
    if args.agent.lower() != "codex":
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
    for field in TOKEN_FIELDS:
        totals[field] = number(totals.get(field))
    if "costUSD" in totals:
        totals["costUSD"] = number(totals.get("costUSD"))

    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent": args.agent,
        "filters": {"since": args.since or "", "until": args.until or "", "timezone": args.timezone or ""},
        "models": models,
        "metricLabels": METRIC_LABELS,
        "periods": {"daily": daily, "weekly": weekly, "monthly": monthly},
        "sessions": sessions,
        "totals": totals,
        "source": {"ccusageBin": args.ccusage_bin, "transcripts": not args.no_transcript},
    }


def html_document(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ccusage report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1220;
      --panel: #111827;
      --panel-2: #0f172a;
      --line: #243244;
      --text: #e5edf6;
      --muted: #8fa1b8;
      --strong: #f8fafc;
      --accent: #14b8a6;
      --accent-2: #38bdf8;
      --warn: #f59e0b;
      --shadow: 0 18px 60px rgba(0, 0, 0, .32);
      --radius: 8px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    header {{
      padding: 32px clamp(18px, 4vw, 56px) 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #0e1a2d 0%, #0b1220 100%);
    }}
    main {{ padding: 24px clamp(18px, 4vw, 56px) 48px; }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 46px); letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 19px; letter-spacing: 0; }}
    .subhead {{ margin-top: 8px; color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .stat, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .stat {{ padding: 16px; }}
    .stat .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .stat .value {{ margin-top: 6px; color: var(--strong); font-size: 26px; font-weight: 760; }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(340px, .65fr);
      gap: 18px;
      align-items: start;
    }}
    .panel {{ padding: 18px; margin-bottom: 18px; }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }}
    .tabs, .chips, .view-switch {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    button, select, input {{
      border: 1px solid var(--line);
      background: #0b1628;
      color: var(--text);
      border-radius: 7px;
      padding: 8px 10px;
      font: inherit;
    }}
    button {{ cursor: pointer; }}
    button.active, button:hover {{ border-color: var(--accent); color: #ecfeff; }}
    .chip.off {{ opacity: .42; text-decoration: line-through; }}
    .chip.total {{ border-color: #38bdf8; }}
    .chart-wrap {{ position: relative; min-height: 360px; }}
    canvas {{ width: 100%; height: 360px; display: block; }}
    .selection {{
      min-height: 28px;
      color: var(--muted);
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--text);
      background: #0b1628;
    }}
    .side-card {{
      border: 1px solid var(--line);
      background: var(--panel-2);
      border-radius: var(--radius);
      padding: 14px;
      margin-bottom: 10px;
    }}
    .side-card .name {{ font-weight: 700; }}
    .side-card .bar {{ height: 8px; border-radius: 99px; background: #1f2937; overflow: hidden; margin-top: 10px; }}
    .side-card .bar span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }}
    .session-controls {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto auto;
      gap: 8px;
      margin-bottom: 12px;
    }}
    .sessions.cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 12px;
    }}
    .session-card {{
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 14px;
      background: var(--panel-2);
    }}
    .session-card h3 {{ margin: 0 0 8px; font-size: 15px; color: var(--strong); }}
    .meta {{ color: var(--muted); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; }}
    .snippets {{ margin-top: 12px; display: grid; gap: 8px; }}
    .snippet {{
      border-left: 3px solid var(--accent);
      background: rgba(20, 184, 166, .08);
      padding: 8px 10px;
      border-radius: 6px;
      color: #dce8f5;
      font-size: 13px;
    }}
    .snippet.assistant {{ border-left-color: var(--accent-2); background: rgba(56, 189, 248, .08); }}
    .sessions.list {{ display: grid; gap: 8px; }}
    .sessions.list .session-card {{ display: grid; grid-template-columns: minmax(220px, 1fr) auto; gap: 12px; align-items: start; }}
    .sessions.list .snippets {{ grid-column: 1 / -1; }}
    .muted {{ color: var(--muted); }}
    .footer-note {{ margin-top: 18px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 960px) {{
      .grid, .summary, .session-controls {{ grid-template-columns: 1fr; }}
      canvas {{ height: 320px; }}
      .chart-wrap {{ min-height: 320px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>ccusage report</h1>
    <div class="subhead" id="reportMeta"></div>
    <section class="summary" id="summary"></section>
  </header>
  <main>
    <div class="grid">
      <section>
        <div class="panel">
          <div class="toolbar">
            <div class="tabs" id="periodTabs"></div>
            <div class="tabs" id="metricTabs"></div>
          </div>
          <div class="selection" id="selection"></div>
          <div class="chips" id="legend"></div>
          <div class="chart-wrap"><canvas id="barChart"></canvas></div>
        </div>
        <div class="panel">
          <h2>Usage curve</h2>
          <div class="chart-wrap"><canvas id="lineChart"></canvas></div>
        </div>
      </section>
      <aside>
        <div class="panel">
          <h2>Model mix</h2>
          <div id="modelMix"></div>
        </div>
        <div class="panel">
          <h2>Sessions</h2>
          <div class="session-controls">
            <input id="sessionSearch" placeholder="Search title, model, or snippet">
            <select id="sessionSort">
              <option value="recent">Recent first</option>
              <option value="tokens">Tokens high to low</option>
              <option value="cost">Cost high to low</option>
              <option value="title">Title A to Z</option>
            </select>
            <div class="view-switch">
              <button id="cardsBtn" class="active">Cards</button>
              <button id="listBtn">List</button>
            </div>
          </div>
          <div class="muted" id="sessionCount"></div>
        </div>
      </aside>
    </div>
    <section class="panel">
      <div id="sessions" class="sessions cards"></div>
      <div class="toolbar" style="margin-top:14px"><button id="loadMore">Load more</button></div>
      <div class="footer-note">Generated as a standalone local HTML file. Embedded snippets may contain private conversation data.</div>
    </section>
  </main>
  <script id="report-data" type="application/json">__REPORT_DATA_JSON__</script>
  <script>
    const DATA = JSON.parse(document.getElementById('report-data').textContent);
    const metricLabels = DATA.metricLabels;
    const state = {{
      period: 'daily',
      metric: 'totalTokens',
      selected: null,
      visible: new Set(['__total', ...(DATA.models || [])]),
      view: 'cards',
      sort: 'recent',
      query: '',
      limit: 80
    }};
    const palette = ['#38bdf8', '#14b8a6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#f97316', '#0ea5e9', '#10b981'];
    let barHits = [];

    function fmt(n) {{
      n = Number(n || 0);
      if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
      if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
      if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
      return String(Math.round(n));
    }}
    function money(n) {{
      if (n === undefined || n === null || Number.isNaN(Number(n))) return 'n/a';
      return '$' + Number(n).toFixed(2);
    }}
    function esc(s) {{
      return String(s ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
    }}
    function seriesColor(series, i) {{
      if (series === '__total') return palette[0];
      const idx = Math.max(1, DATA.models.indexOf(series) + 1);
      return palette[idx % palette.length];
    }}
    function seriesLabel(series) {{ return series === '__total' ? 'Total' : series; }}
    function bucketValue(bucket, series, metric = state.metric) {{
      if (series === '__total') return Number(bucket[metric] || 0);
      return Number(((bucket.models || {{}})[series] || {{}})[metric] || 0);
    }}
    function currentBuckets() {{ return DATA.periods[state.period] || []; }}
    function currentSeries() {{
      return ['__total', ...(DATA.models || [])].filter(s => state.visible.has(s));
    }}
    function setupCanvas(canvas) {{
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(320, rect.width) * dpr;
      canvas.height = Math.max(260, rect.height) * dpr;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return {{ctx, width: Math.max(320, rect.width), height: Math.max(260, rect.height)}};
    }}
    function drawGrid(ctx, x, y, w, h, max) {{
      ctx.strokeStyle = '#243244';
      ctx.fillStyle = '#8fa1b8';
      ctx.font = '12px system-ui';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {{
        const yy = y + h - h * (i / 4);
        ctx.beginPath();
        ctx.moveTo(x, yy);
        ctx.lineTo(x + w, yy);
        ctx.stroke();
        ctx.fillText(fmt(max * i / 4), 8, yy + 4);
      }}
    }}
    function drawBarChart() {{
      const canvas = document.getElementById('barChart');
      const {{ctx, width, height}} = setupCanvas(canvas);
      const pad = {{l: 74, r: 20, t: 24, b: 64}};
      const plotW = width - pad.l - pad.r;
      const plotH = height - pad.t - pad.b;
      const buckets = currentBuckets();
      const series = currentSeries();
      barHits = [];
      ctx.clearRect(0, 0, width, height);
      if (!buckets.length || !series.length) {{
        ctx.fillStyle = '#8fa1b8';
        ctx.fillText('No data for this period.', pad.l, pad.t + 20);
        return;
      }}
      const max = Math.max(1, ...buckets.flatMap(b => series.map(s => bucketValue(b, s))));
      drawGrid(ctx, pad.l, pad.t, plotW, plotH, max);
      const groupW = plotW / buckets.length;
      const gap = 3;
      const barW = Math.max(2, Math.min(28, (groupW * 0.72) / series.length - gap));
      buckets.forEach((bucket, i) => {{
        const totalW = series.length * barW + (series.length - 1) * gap;
        let x = pad.l + i * groupW + (groupW - totalW) / 2;
        series.forEach((s, j) => {{
          const value = bucketValue(bucket, s);
          const h = plotH * value / max;
          const y = pad.t + plotH - h;
          const selected = state.selected && state.selected.period === state.period && state.selected.label === bucket.label;
          ctx.globalAlpha = state.selected && !selected ? .34 : 1;
          ctx.fillStyle = seriesColor(s, j);
          ctx.fillRect(x, y, barW, h);
          barHits.push({{x, y, w: barW, h, label: bucket.label, series: s}});
          x += barW + gap;
        }});
        ctx.globalAlpha = 1;
        const showEvery = Math.max(1, Math.ceil(buckets.length / 12));
        if (i % showEvery === 0) {{
          ctx.save();
          ctx.translate(pad.l + i * groupW + groupW / 2, pad.t + plotH + 18);
          ctx.rotate(-Math.PI / 7);
          ctx.fillStyle = '#8fa1b8';
          ctx.font = '12px system-ui';
          ctx.textAlign = 'right';
          ctx.fillText(bucket.label, 0, 0);
          ctx.restore();
        }}
      }});
    }}
    function drawLineChart() {{
      const canvas = document.getElementById('lineChart');
      const {{ctx, width, height}} = setupCanvas(canvas);
      const pad = {{l: 74, r: 20, t: 24, b: 56}};
      const plotW = width - pad.l - pad.r;
      const plotH = height - pad.t - pad.b;
      const buckets = currentBuckets();
      const lineSeries = state.selected && state.selected.series !== '__total' ? state.selected.series : '__total';
      ctx.clearRect(0, 0, width, height);
      if (!buckets.length) {{
        ctx.fillStyle = '#8fa1b8';
        ctx.fillText('No data for this period.', pad.l, pad.t + 20);
        return;
      }}
      const values = buckets.map(b => bucketValue(b, lineSeries));
      const max = Math.max(1, ...values);
      drawGrid(ctx, pad.l, pad.t, plotW, plotH, max);
      ctx.strokeStyle = seriesColor(lineSeries, 0);
      ctx.lineWidth = 3;
      ctx.beginPath();
      values.forEach((v, i) => {{
        const x = pad.l + (buckets.length === 1 ? plotW / 2 : plotW * i / (buckets.length - 1));
        const y = pad.t + plotH - plotH * v / max;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }});
      ctx.stroke();
      values.forEach((v, i) => {{
        const x = pad.l + (buckets.length === 1 ? plotW / 2 : plotW * i / (buckets.length - 1));
        const y = pad.t + plotH - plotH * v / max;
        ctx.fillStyle = '#0b1220';
        ctx.strokeStyle = seriesColor(lineSeries, 0);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }});
      ctx.fillStyle = '#8fa1b8';
      ctx.font = '12px system-ui';
      ctx.fillText(seriesLabel(lineSeries) + ' / ' + metricLabels[state.metric], pad.l, 16);
    }}
    function renderTabs() {{
      const periodTabs = document.getElementById('periodTabs');
      periodTabs.innerHTML = ['daily', 'weekly', 'monthly'].map(p => `<button class="${state.period === p ? 'active' : ''}" data-period="${p}">${p[0].toUpperCase() + p.slice(1)}</button>`).join('');
      periodTabs.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        state.period = btn.dataset.period;
        state.selected = null;
        renderAll();
      }});
      const metricTabs = document.getElementById('metricTabs');
      metricTabs.innerHTML = Object.entries(metricLabels).map(([key, label]) => `<button class="${state.metric === key ? 'active' : ''}" data-metric="${key}">${label}</button>`).join('');
      metricTabs.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        state.metric = btn.dataset.metric;
        renderAll();
      }});
    }}
    function renderLegend() {{
      const legend = document.getElementById('legend');
      const series = ['__total', ...(DATA.models || [])];
      legend.innerHTML = series.map((s, i) => `<button class="chip ${s === '__total' ? 'total' : ''} ${state.visible.has(s) ? '' : 'off'}" data-series="${esc(s)}"><span style="color:${seriesColor(s, i)}">■</span> ${esc(seriesLabel(s))}</button>`).join('');
      legend.querySelectorAll('button').forEach(btn => btn.onclick = () => {{
        const s = btn.dataset.series;
        if (state.visible.has(s) && state.visible.size > 1) state.visible.delete(s);
        else state.visible.add(s);
        renderAll();
      }});
    }}
    function renderSelection() {{
      const el = document.getElementById('selection');
      if (!state.selected) {{
        el.innerHTML = '<span>Click a bar to filter sessions by bucket. Toggle legend chips to show or hide bars.</span>';
        return;
      }}
      el.innerHTML = `<span class="pill">${esc(state.period)}: ${esc(state.selected.label)} / ${esc(seriesLabel(state.selected.series))}</span><button id="clearSelection">Clear filter</button>`;
      document.getElementById('clearSelection').onclick = () => {{ state.selected = null; renderAll(); }};
    }}
    function bucketMatchesSession(s) {{
      if (!state.selected) return true;
      const key = state.period === 'daily' ? 'date' : state.period === 'weekly' ? 'week' : 'month';
      if (String(s[key] || '') !== state.selected.label) return false;
      if (state.selected.series !== '__total' && !(s.modelNames || []).includes(state.selected.series)) return false;
      return true;
    }}
    function filteredSessions() {{
      const q = state.query.toLowerCase();
      let sessions = (DATA.sessions || []).filter(bucketMatchesSession);
      if (q) {{
        sessions = sessions.filter(s => {{
          const hay = [s.title, s.sessionId, s.sessionFile, ...(s.modelNames || []), ...((s.snippets || []).map(x => x.text))].join(' ').toLowerCase();
          return hay.includes(q);
        }});
      }}
      sessions.sort((a, b) => {{
        if (state.sort === 'tokens') return Number(b.totalTokens || 0) - Number(a.totalTokens || 0);
        if (state.sort === 'cost') return Number(b.costUSD || 0) - Number(a.costUSD || 0);
        if (state.sort === 'title') return String(a.title || '').localeCompare(String(b.title || ''));
        return String(b.lastActivity || '').localeCompare(String(a.lastActivity || ''));
      }});
      return sessions;
    }}
    function sessionHtml(s) {{
      const snippets = (s.snippets || []).slice(0, 4).map(sn => `<div class="snippet ${sn.role === 'assistant' ? 'assistant' : ''}"><b>${esc(sn.role)}:</b> ${esc(sn.text)}</div>`).join('');
      const cost = s.costUSD !== undefined ? `<span>${money(s.costUSD)}</span>` : '';
      return `<article class="session-card">
        <div>
          <h3>${esc(s.title || s.sessionId || 'Untitled session')}</h3>
          <div class="meta">
            <span>${esc(s.date || '')}</span>
            <span>${fmt(s.totalTokens)} tokens</span>
            <span>${esc((s.modelNames || []).join(', ') || 'model n/a')}</span>
            ${cost}
          </div>
        </div>
        <div class="meta">${esc(s.sessionId || '')}</div>
        <div class="snippets">${snippets || '<span class="muted">No transcript snippets embedded.</span>'}</div>
      </article>`;
    }}
    function renderSessions() {{
      const sessions = filteredSessions();
      const count = document.getElementById('sessionCount');
      count.textContent = `${sessions.length} matching session${sessions.length === 1 ? '' : 's'}`;
      const container = document.getElementById('sessions');
      container.className = 'sessions ' + state.view;
      container.innerHTML = sessions.slice(0, state.limit).map(sessionHtml).join('');
      document.getElementById('loadMore').style.display = sessions.length > state.limit ? 'inline-flex' : 'none';
    }}
    function renderSummary() {{
      const t = DATA.totals || {{}};
      const sessions = DATA.sessions || [];
      const summary = [
        ['Total tokens', fmt(t.totalTokens)],
        ['Input / Output', `${fmt(t.inputTokens)} / ${fmt(t.outputTokens)}`],
        ['Reasoning', fmt(t.reasoningOutputTokens)],
        ['Sessions', fmt(sessions.length)]
      ];
      if (t.costUSD !== undefined) summary[3] = ['Cost', money(t.costUSD)];
      document.getElementById('summary').innerHTML = summary.map(([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`).join('');
      const filters = DATA.filters || {{}};
      const range = [filters.since, filters.until].filter(Boolean).join(' to ') || 'all available dates';
      document.getElementById('reportMeta').textContent = `${DATA.agent} usage, ${range}. Generated ${DATA.generatedAt}.`;
    }}
    function renderModelMix() {{
      const models = DATA.models || [];
      const totals = new Map(models.map(m => [m, 0]));
      (DATA.periods.daily || []).forEach(bucket => {{
        models.forEach(model => totals.set(model, totals.get(model) + bucketValue(bucket, model, 'totalTokens')));
      }});
      const max = Math.max(1, ...totals.values());
      document.getElementById('modelMix').innerHTML = models.length ? models.map(model => `
        <div class="side-card">
          <div class="name">${esc(model)}</div>
          <div class="meta">${fmt(totals.get(model))} tokens</div>
          <div class="bar"><span style="width:${Math.max(2, 100 * totals.get(model) / max)}%"></span></div>
        </div>`).join('') : '<div class="muted">No model data found.</div>';
    }}
    function renderAll() {{
      renderTabs();
      renderLegend();
      renderSelection();
      renderSummary();
      renderModelMix();
      drawBarChart();
      drawLineChart();
      renderSessions();
    }}
    document.getElementById('barChart').addEventListener('click', event => {{
      const rect = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hit = barHits.find(h => x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h);
      if (!hit) return;
      const same = state.selected && state.selected.period === state.period && state.selected.label === hit.label && state.selected.series === hit.series;
      state.selected = same ? null : {{period: state.period, label: hit.label, series: hit.series}};
      renderAll();
    }});
    document.getElementById('sessionSearch').addEventListener('input', event => {{
      state.query = event.target.value;
      state.limit = 80;
      renderSessions();
    }});
    document.getElementById('sessionSort').addEventListener('change', event => {{
      state.sort = event.target.value;
      renderSessions();
    }});
    document.getElementById('cardsBtn').onclick = () => {{
      state.view = 'cards';
      document.getElementById('cardsBtn').classList.add('active');
      document.getElementById('listBtn').classList.remove('active');
      renderSessions();
    }};
    document.getElementById('listBtn').onclick = () => {{
      state.view = 'list';
      document.getElementById('listBtn').classList.add('active');
      document.getElementById('cardsBtn').classList.remove('active');
      renderSessions();
    }};
    document.getElementById('loadMore').onclick = () => {{
      state.limit += 80;
      renderSessions();
    }};
    window.addEventListener('resize', () => {{
      window.clearTimeout(window.__ccusageResize);
      window.__ccusageResize = window.setTimeout(() => {{ drawBarChart(); drawLineChart(); }}, 120);
    }});
    renderAll();
  </script>
</body>
</html>
"""
    template = template.replace("{{", "{").replace("}}", "}")
    return template.replace("__REPORT_DATA_JSON__", data_json)


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


def choose_port(host: str, requested_port: int) -> int:
    if requested_port != 0:
        return requested_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def serve_report(output: Path, host: str, port: int) -> None:
    actual_port = choose_port(host, port)
    handler = functools.partial(QuietHTTPRequestHandler, directory=str(output.parent))
    with http.server.ThreadingHTTPServer((host, actual_port), handler) as httpd:
        url = f"http://{host}:{actual_port}/{output.name}"
        print(url, flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped ccusage report server.", flush=True)


def main() -> None:
    args = parse_args()
    data = build_report_data(args)
    output = Path(args.output).expanduser() if args.output else default_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_document(data), encoding="utf-8")
    print(output)
    if args.serve:
        serve_report(output, args.host, args.port)


if __name__ == "__main__":
    main()
