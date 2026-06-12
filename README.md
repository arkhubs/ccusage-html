# ccusage-html

Generate a polished, interactive HTML dashboard from local `ccusage` token usage data.

This project contains a Codex skill plus a standalone Python generator. The report includes:

- Daily, weekly, and monthly token bar charts.
- Grouped model bars plus a total series.
- Clickable legend chips and bar-based session filtering.
- Usage curve chart.
- Session card/list views with Codex chat snippets when local transcripts are available.
- Optional local HTTP serving with `--serve`.

## Quick Start

```powershell
uv run python .\scripts\generate_ccusage_report.py all --serve --port 8765
```

Then open:

```text
http://127.0.0.1:8765/ccusage-report-*.html
```

## Examples

```powershell
uv run python .\scripts\generate_ccusage_report.py codex --since 2026-06-01 --until 2026-06-30 --output .\ccusage-report.html
uv run python .\scripts\generate_ccusage_report.py codex --timezone Asia/Shanghai --speed auto
uv run python .\scripts\generate_ccusage_report.py cc --offline --no-transcript
uv run python .\scripts\generate_ccusage_report.py gemini --no-transcript
uv run python .\scripts\generate_ccusage_report.py --agent codex --serve
```

Agent selection mirrors `ccusage`: omit the selector or use `all` for all detected agents, or put an agent command such as `codex`, `claude`, `cc`, `gemini`, `opencode`, or `qwen` before the other options. The older `--agent` option still works.

## Wiki

Project documentation lives in [`docs/wiki/v0.0.1.md`](docs/wiki/v0.0.1.md).

## Code Layout

- `scripts/generate_ccusage_report.py` is the compatibility CLI entrypoint.
- `scripts/ccusage_html_report/app.py` coordinates generation, output paths, and local serving.
- `scripts/ccusage_html_report/cli.py` handles argument parsing.
- `scripts/ccusage_html_report/ccusage.py` handles agent aliases, command building, and JSON execution.
- `scripts/ccusage_html_report/report.py` normalizes usage data, sessions, totals, and Codex snippets.
- `scripts/ccusage_html_report/html.py` renders the standalone HTML document.

## Notes

Transcript enrichment is currently strongest for Codex because `ccusage codex session --json` maps to local `~/.codex/sessions/**.jsonl` files. Generated reports may embed private snippets, so treat output HTML files as local/private unless intentionally shared.
