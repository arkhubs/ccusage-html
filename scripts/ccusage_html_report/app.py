from __future__ import annotations

import functools
import http.server
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from .cli import parse_args
from .html import html_document
from .report import build_report_data


def default_output_path() -> Path:
    out_dir = Path.home() / ".codex" / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return out_dir / f"ccusage-report-{stamp}.html"


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
