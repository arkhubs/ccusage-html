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
uv run python .\scripts\generate_ccusage_report.py --agent codex --serve --port 8765
```

Then open:

```text
http://127.0.0.1:8765/ccusage-report-*.html
```

## Examples

```powershell
uv run python .\scripts\generate_ccusage_report.py --agent codex --since 2026-06-01 --until 2026-06-30 --output .\ccusage-report.html
uv run python .\scripts\generate_ccusage_report.py --agent codex --timezone Asia/Shanghai --speed auto
uv run python .\scripts\generate_ccusage_report.py --agent claude --offline --no-transcript
```

## Notes

Transcript enrichment is currently strongest for Codex because `ccusage codex session --json` maps to local `~/.codex/sessions/**.jsonl` files. Generated reports may embed private snippets, so treat output HTML files as local/private unless intentionally shared.
