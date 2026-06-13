---
name: ccusage-html-report
description: Generate polished standalone HTML dashboards from ccusage token data, with daily/weekly/monthly model bar charts, usage curves, and session list/card views enriched with local Codex/Gemini chat snippets. Use when the user asks to visualize, summarize, audit, present, or browse ccusage, Claude Code, Codex, Gemini, or coding-agent token usage in a modern chart report.
---

# ccusage HTML Report

Use this skill to turn local `ccusage` data into a polished, interactive, single-file HTML dashboard. Prefer the bundled script instead of hand-building charts.

## Quick Start

Run the generator with the Python environment available on the machine:

```powershell
uv run python C:\Users\XuanFL\.codex\skills\ccusage-html-report\scripts\generate_ccusage_report.py all --serve --port 0
```

Useful options:

```powershell
uv run python C:\Users\XuanFL\.codex\skills\ccusage-html-report\scripts\generate_ccusage_report.py codex --since 2026-06-01 --until 2026-06-30 --output C:\Users\XuanFL\Desktop\ccusage-report.html
uv run python C:\Users\XuanFL\.codex\skills\ccusage-html-report\scripts\generate_ccusage_report.py codex --timezone Asia/Shanghai --speed auto
uv run python C:\Users\XuanFL\.codex\skills\ccusage-html-report\scripts\generate_ccusage_report.py cc --offline --no-transcript
uv run python C:\Users\XuanFL\.codex\skills\ccusage-html-report\scripts\generate_ccusage_report.py gemini
uv run python C:\Users\XuanFL\.codex\skills\ccusage-html-report\scripts\generate_ccusage_report.py --agent codex --serve --port 8765
```

Agent selection mirrors `ccusage`: omit the selector or use `all` for all detected agents, or put a supported agent command such as `codex`, `claude`, `cc`, `gemini`, `opencode`, or `qwen` before the other options.

By default, each run creates a persistent `reports/<timestamp>/` archive beside the script project. The archive contains `ccusage-report.html`, `report-data.json`, `sessions.json`, `manifest.json`, and raw `ccusage` JSON payloads under `raw/`. Use `--reports-dir` to choose a different archive root.

With `--serve`, the local HTTP server starts before ccusage data collection. The command prints `Report URL` immediately, serves a loading page, and replaces it with the final dashboard when generation completes. Use `--port 0` to avoid port collisions, or `--strict-port` when a fixed port must fail loudly. Use `--no-price-fetch` only when report-side current price lookup and cost estimates should be skipped.

The URL works only while the serving process is alive. If Codex or another tool runs the command with a timeout and kills the process, use the printed `Report HTML` path or start `--serve` again in a persistent/background process.

## Workflow

1. Confirm `ccusage --version` works if the user has not already confirmed it.
2. Generate the report with `scripts/generate_ccusage_report.py`.
3. Prefer `--serve --port 0` when the user wants to view or interact with the report; give the printed `http://127.0.0.1:PORT/...` URL as soon as it appears.
4. Also give the printed absolute `Report HTML`, `Archive directory`, `Report data`, and `Raw data` paths so the user has an entry point after viewing.

## Report Features

The generated dashboard includes:

- Daily, weekly, and monthly token bar charts.
- Grouped model bars plus a total bar for each period bucket.
- `all` mode model breakdowns normalized from `ccusage` `modelBreakdowns`.
- A top-level total cost stat and a cost metric switch alongside token totals.
- Best-effort current model price display from models.dev or LiteLLM, including input, output, cache hit, and cache write when available.
- Per-model cost estimates when `ccusage` provides token-level model breakdowns but omits model-level cost.
- Usage and Sessions tabs. Model mix cards are merged into the top of Usage.
- Clickable legend chips to show/hide model bars and the total series.
- Clickable bars that filter the session browser by date/week/month and, when applicable, by model.
- A usage curve chart for the selected period and metric.
- Metric switching for total, input, output, reasoning, cost, cache read, and cache creation.
- Session card/list toggle with search, sorting, title extraction, token/cost summaries, context token estimates, per-model details, and a right-side drawer with local Codex/Gemini full-conversation views.
- Persistent timestamped archives with normalized data, raw payloads, session records, and manifest metadata.
- Terminal output and in-report footer metadata exposing the local URL and file locations.
- Fast serve startup with an auto-refreshing loading page before the final report is ready.

## Transcript Notes

Transcript enrichment supports Codex sessions via `~/.codex/sessions/**.jsonl` and Gemini sessions via `~/.gemini/tmp/**/chats/session-*.json*` when `ccusage session --json` IDs can be matched. The script skips large context/system messages, keeps short user/assistant snippets for cards, and embeds local conversation turns plus compact tool-call context in the session detail drawer. For unsupported agents, use `--no-transcript` unless local transcript support is added.

Agent-specific transcript support lives behind the provider registry in `scripts/ccusage_html_report/transcripts.py`; add new agent formats there instead of expanding `sessions.py`.

The HTML embeds selected snippets and local conversation text, so treat the output as private usage data unless the user explicitly wants it shared.
