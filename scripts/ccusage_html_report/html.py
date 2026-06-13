from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ASSETS_DIR = Path(__file__).with_name("assets")
SCRIPT_ASSETS = (
    "report-state.js",
    "report-utils.js",
    "report-filters.js",
    "report-charts.js",
    "report-sessions.js",
    "report-summary.js",
    "report-init.js",
)


@lru_cache(maxsize=None)
def asset_text(name: str) -> str:
    return (ASSETS_DIR / name).read_text(encoding="utf-8").rstrip("\n")


def report_data_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def report_script() -> str:
    return "\n\n".join(asset_text(name) for name in SCRIPT_ASSETS)


def html_document(data: dict[str, Any]) -> str:
    return (
        asset_text("report.html")
        .replace("__REPORT_CSS__", asset_text("report.css"))
        .replace("__REPORT_JS__", report_script())
        .replace("__REPORT_DATA_JSON__", report_data_json(data))
    )
