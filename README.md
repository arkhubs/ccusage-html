# ccusage-html

Generate a polished, interactive HTML dashboard from local `ccusage` token usage data.

This project contains a Codex skill plus a standalone Python generator. The report includes:

- Daily, weekly, and monthly token bar charts.
- Grouped model bars plus a total series, including `all` mode model breakdowns.
- Usage-first model mix cards with per-model token and cost totals.
- Best-effort current model prices for input, output, cache hit, and cache write when models.dev or LiteLLM has a match.
- Total cost metric alongside token metrics.
- Clickable legend chips and bar-based session filtering.
- Usage curve chart.
- Icon-only dark/light theme toggle with persisted browser preference.
- Session card/list views with a right-side detail drawer for token type, model breakdown, cost, context token, and local transcript details for Codex and Gemini sessions when available.
- Persistent `reports/<timestamp>/` archives containing the HTML, normalized report data, raw ccusage JSON payloads, session records, and a manifest.
- Console output that exposes the local URL immediately, then generated file/archive paths when ready.
- Optional local HTTP serving with `--serve`.

## Quick Start

```powershell
uv run python .\scripts\generate_ccusage_report.py all --serve --port 0
```

The command starts the local HTTP server first, prints the URL immediately, and shows a loading page until data generation finishes. It then prints the generated HTML and archive paths, for example:

```text
Report URL: http://127.0.0.1:49231/ccusage-report.html
Report status: generating data...
Serving report at: http://127.0.0.1:49231/ccusage-report.html
Report ready: http://127.0.0.1:49231/ccusage-report.html
Report HTML: E:\Projects\Active\ccusage-html\reports\20260612-151530\ccusage-report.html
Archive directory: E:\Projects\Active\ccusage-html\reports\20260612-151530
```

By default, reports are kept under `reports/<timestamp>/` instead of a temporary directory.
The local URL is available only while the `--serve` process is running. If the process is stopped or killed by a tool timeout, open the generated `Report HTML` file directly or start the server again.

## Examples

```powershell
uv run python .\scripts\generate_ccusage_report.py codex --since 2026-06-01 --until 2026-06-30 --output .\ccusage-report.html
uv run python .\scripts\generate_ccusage_report.py codex --timezone Asia/Shanghai --speed auto
uv run python .\scripts\generate_ccusage_report.py cc --offline --no-transcript
uv run python .\scripts\generate_ccusage_report.py gemini
uv run python .\scripts\generate_ccusage_report.py --agent codex --serve
uv run python .\scripts\generate_ccusage_report.py all --reports-dir .\reports-archive
```

For the fastest interactive preview, use `--serve --port 0`; add `--no-transcript` when the session conversation drawer is not needed. If you must use a fixed port, add `--strict-port` to fail instead of falling back to a free port when the requested port is busy. Use `--no-price-fetch` only when you intentionally want to skip report-side current price lookup and cost estimates.

Agent selection mirrors `ccusage`: omit the selector or use `all` for all detected agents, or put an agent command such as `codex`, `claude`, `cc`, `gemini`, `opencode`, or `qwen` before the other options. The older `--agent` option still works.

## Wiki

Project documentation lives in [`docs/wiki/v0.0.1.md`](docs/wiki/v0.0.1.md).

Latest v0.0.12 notes live in [`docs/wiki/v0.0.12.md`](docs/wiki/v0.0.12.md).

v0.0.11 notes live in [`docs/wiki/v0.0.11.md`](docs/wiki/v0.0.11.md).

v0.0.10 notes live in [`docs/wiki/v0.0.10.md`](docs/wiki/v0.0.10.md).

v0.0.9 notes live in [`docs/wiki/v0.0.9.md`](docs/wiki/v0.0.9.md).

v0.0.8 notes live in [`docs/wiki/v0.0.8.md`](docs/wiki/v0.0.8.md).

v0.0.7 notes live in [`docs/wiki/v0.0.7.md`](docs/wiki/v0.0.7.md).

v0.0.6 notes live in [`docs/wiki/v0.0.6.md`](docs/wiki/v0.0.6.md).

v0.0.5 notes live in [`docs/wiki/v0.0.5.md`](docs/wiki/v0.0.5.md).

v0.0.4 notes live in [`docs/wiki/v0.0.4.md`](docs/wiki/v0.0.4.md).

v0.0.3 notes live in [`docs/wiki/v0.0.3.md`](docs/wiki/v0.0.3.md).

v0.0.2 notes live in [`docs/wiki/v0.0.2.md`](docs/wiki/v0.0.2.md).

## Code Layout

- `scripts/generate_ccusage_report.py` is the compatibility CLI entrypoint.
- `scripts/ccusage_html_report/app.py` coordinates generation, output paths, and local serving.
- `scripts/ccusage_html_report/cli.py` handles argument parsing.
- `scripts/ccusage_html_report/ccusage.py` handles agent aliases, command building, and JSON execution.
- `scripts/ccusage_html_report/report.py` coordinates report data assembly.
- `scripts/ccusage_html_report/metrics.py` normalizes token/cost fields, model breakdowns, periods, and totals.
- `scripts/ccusage_html_report/pricing.py` fetches and applies best-effort model price metadata.
- `scripts/ccusage_html_report/sessions.py` normalizes ccusage session rows, titles, and sorting fields.
- `scripts/ccusage_html_report/transcripts.py` provides the shared transcript provider registry plus Codex and Gemini local transcript parsers.
- `scripts/ccusage_html_report/dates.py` centralizes date parsing and week labels.
- `scripts/ccusage_html_report/html.py` renders the standalone HTML document from resources in `scripts/ccusage_html_report/assets/`.

## Notes

Transcript enrichment reads local Codex `~/.codex/sessions/**.jsonl` files and Gemini `~/.gemini/tmp/**/chats/session-*.json*` files when they can be matched to `ccusage session --json` IDs. Conversation drawers may include user/assistant turns plus compact tool-call and command-output context, so treat output HTML files as local/private unless intentionally shared.
