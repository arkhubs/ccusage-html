from __future__ import annotations

import functools
import http.server
import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from . import __version__
from .cli import parse_args
from .html import html_document
from .report import build_report_data_from_payloads, collect_ccusage_payloads


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_reports_root() -> Path:
    return project_root() / "reports"


def unique_archive_dir(reports_root: Path) -> Path:
    reports_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = reports_root / stamp
    suffix = 2
    while candidate.exists():
        candidate = reports_root / f"{stamp}-{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return


def choose_port(host: str, requested_port: int) -> int:
    if requested_port != 0:
        return requested_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def report_url(output: Path, host: str, port: int) -> str:
    return f"http://{host}:{port}/{quote(output.name)}"


def serve_report(output: Path, host: str, port: int, url: str) -> None:
    handler = functools.partial(QuietHTTPRequestHandler, directory=str(output.parent))
    with http.server.ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"Serving report at: {url}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped ccusage report server.", flush=True)


def main() -> None:
    args = parse_args()
    payloads = collect_ccusage_payloads(args)
    data = build_report_data_from_payloads(args, payloads)

    reports_root = Path(args.reports_dir).expanduser() if args.reports_dir else default_reports_root()
    archive_dir = unique_archive_dir(reports_root)
    archive_html = archive_dir / "ccusage-report.html"
    output = Path(args.output).expanduser() if args.output else archive_html
    if not output.is_absolute():
        output = Path.cwd() / output
    output.parent.mkdir(parents=True, exist_ok=True)

    actual_port = choose_port(args.host, args.port) if args.serve else None
    url = report_url(output, args.host, actual_port) if actual_port is not None else ""

    raw_dir = archive_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    report_data_path = archive_dir / "report-data.json"
    sessions_path = archive_dir / "sessions.json"
    manifest_path = archive_dir / "manifest.json"
    raw_paths = {scope: raw_dir / f"{scope}.json" for scope in sorted(payloads)}

    archive = {
        "version": __version__,
        "directory": str(archive_dir.resolve()),
        "htmlPath": str(output.resolve()),
        "archiveHtmlPath": str(archive_html.resolve()),
        "reportDataPath": str(report_data_path.resolve()),
        "sessionRecordsPath": str(sessions_path.resolve()),
        "manifestPath": str(manifest_path.resolve()),
        "rawPayloadPaths": {scope: str(path.resolve()) for scope, path in raw_paths.items()},
        "url": url,
    }
    data["archive"] = archive

    html = html_document(data)
    output.write_text(html, encoding="utf-8")
    if output.resolve() != archive_html.resolve():
        archive_html.write_text(html, encoding="utf-8")

    for scope, payload in payloads.items():
        write_json(raw_paths[scope], payload)
    write_json(report_data_path, data)
    write_json(sessions_path, data.get("sessions", []))
    write_json(
        manifest_path,
        {
            **archive,
            "generatedAt": data.get("generatedAt"),
            "agent": data.get("agent"),
            "agentInput": data.get("agentInput"),
            "filters": data.get("filters"),
            "source": data.get("source"),
        },
    )

    if url:
        print(f"Report URL: {url}", flush=True)
    else:
        print("Report URL: start with --serve to expose a local URL", flush=True)
    print(f"Report HTML: {output.resolve()}", flush=True)
    if output.resolve() != archive_html.resolve():
        print(f"Archive HTML: {archive_html.resolve()}", flush=True)
    print(f"Archive directory: {archive_dir.resolve()}", flush=True)
    print(f"Report data: {report_data_path.resolve()}", flush=True)
    print(f"Raw data: {raw_dir.resolve()}", flush=True)

    if args.serve:
        serve_report(output, args.host, actual_port or args.port, url)
