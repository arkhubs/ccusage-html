from __future__ import annotations

import re
from datetime import datetime
from typing import Any


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


def parse_datetime_from_text(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    direct = parse_iso_datetime(value)
    if direct:
        return direct

    cleaned = value.strip()
    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})[T_](\d{2})[-:](\d{2})(?:[-:](\d{2}))?",
        cleaned,
    )
    if match:
        year, month, day, hour, minute, second = match.groups(default="0")
        try:
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute),
                int(second),
            )
        except ValueError:
            return None

    match = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", cleaned)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError:
            return None
    return None


def datetime_sort_value(value: datetime | None) -> float:
    if not value:
        return 0
    try:
        return value.timestamp()
    except (OSError, ValueError):
        return 0


def iso_week_label_from_date(date_text: str) -> str:
    try:
        day = datetime.fromisoformat(date_text[:10]).date()
    except ValueError:
        return "Unknown"
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"
