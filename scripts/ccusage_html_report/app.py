from __future__ import annotations

import functools
from html import escape
import http.server
import json
import socket
import threading
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


class ReportHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def display_host(host: str) -> str:
    if host in ("", "0.0.0.0", "::"):
        return "127.0.0.1"
    if ":" in host and not (host.startswith("[") and host.endswith("]")):
        return f"[{host}]"
    return host


def report_url(output: Path, host: str, port: int) -> str:
    return f"http://{display_host(host)}:{port}/{quote(output.name, safe='')}"


def build_report_server(
    directory: Path,
    host: str,
    requested_port: int,
    strict_port: bool = False,
) -> tuple[ReportHTTPServer, int]:
    handler = functools.partial(QuietHTTPRequestHandler, directory=str(directory))
    try:
        httpd = ReportHTTPServer((host, requested_port), handler)
    except OSError as exc:
        if requested_port == 0 or strict_port:
            raise
        print(
            f"Port {requested_port} is unavailable ({exc}); using a free port instead.",
            flush=True,
        )
        httpd = ReportHTTPServer((host, 0), handler)
    return httpd, int(httpd.server_address[1])


def loading_html(url: str) -> str:
    escaped_url = escape(url, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="2">
  <title>Generating ccusage report</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, Segoe UI, sans-serif; }}
    body {{ min-height: 100vh; margin: 0; display: grid; place-items: center; background: #f7f7f2; color: #202124; }}
    main {{ width: min(620px, calc(100vw - 40px)); padding: 28px; border: 1px solid #d8d7cf; border-radius: 8px; background: #fffefa; box-shadow: 0 18px 44px rgba(30, 36, 28, .08); }}
    h1 {{ margin: 0 0 10px; font-size: 24px; line-height: 1.2; }}
    p {{ margin: 0 0 14px; line-height: 1.6; color: #55584f; }}
    a {{ color: #0b6bcb; word-break: break-all; }}
    .bar {{ height: 6px; overflow: hidden; border-radius: 999px; background: #e4e2d8; }}
    .bar::before {{ content: ""; display: block; width: 40%; height: 100%; border-radius: inherit; background: #23966f; animation: slide 1.2s ease-in-out infinite alternate; }}
    @keyframes slide {{ from {{ transform: translateX(0); }} to {{ transform: translateX(150%); }} }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #161712; color: #f2f1e8; }}
      main {{ background: #20221b; border-color: #3d4035; box-shadow: none; }}
      p {{ color: #c9cabf; }}
      .bar {{ background: #3d4035; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Generating ccusage report</h1>
    <p>The local server is already running. This page refreshes automatically while token data is collected.</p>
    <p><a href="{escaped_url}">{escaped_url}</a></p>
    <div class="bar" aria-hidden="true"></div>
  </main>
</body>
</html>
"""


def start_report_server(httpd: http.server.ThreadingHTTPServer, url: str) -> threading.Thread:
    thread = threading.Thread(target=httpd.serve_forever, name="ccusage-report-server", daemon=True)
    thread.start()
    print(f"Serving report at: {url}", flush=True)
    return thread


def wait_for_report_server(httpd: http.server.ThreadingHTTPServer, thread: threading.Thread) -> None:
    try:
        while thread.is_alive():
            thread.join(1)
    except KeyboardInterrupt:
        print("\nStopped ccusage report server.", flush=True)
    finally:
        if thread.is_alive():
            httpd.shutdown()
            thread.join(3)
        httpd.server_close()


def main() -> None:
    args = parse_args()
    reports_root = Path(args.reports_dir).expanduser() if args.reports_dir else default_reports_root()
    archive_dir = unique_archive_dir(reports_root)
    archive_html = archive_dir / "ccusage-report.html"
    output = Path(args.output).expanduser() if args.output else archive_html
    if not output.is_absolute():
        output = Path.cwd() / output
    output.parent.mkdir(parents=True, exist_ok=True)

    httpd: http.server.ThreadingHTTPServer | None = None
    server_thread: threading.Thread | None = None
    actual_port: int | None = None
    url = ""
    if args.serve:
        httpd, actual_port = build_report_server(output.parent, args.host, args.port, args.strict_port)
        url = report_url(output, args.host, actual_port)
        output.write_text(loading_html(url), encoding="utf-8")
        print(f"Report URL: {url}", flush=True)
        print("Report status: generating data...", flush=True)
        server_thread = start_report_server(httpd, url)

    payloads = collect_ccusage_payloads(args)
    data = build_report_data_from_payloads(args, payloads)

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
        print(f"Report ready: {url}", flush=True)
    else:
        print("Report URL: start with --serve to expose a local URL", flush=True)
    print(f"Report HTML: {output.resolve()}", flush=True)
    if output.resolve() != archive_html.resolve():
        print(f"Archive HTML: {archive_html.resolve()}", flush=True)
    print(f"Archive directory: {archive_dir.resolve()}", flush=True)
    print(f"Report data: {report_data_path.resolve()}", flush=True)
    print(f"Raw data: {raw_dir.resolve()}", flush=True)

    if httpd and server_thread:
        wait_for_report_server(httpd, server_thread)
