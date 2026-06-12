from __future__ import annotations

import argparse

from .ccusage import normalize_agent_selector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a polished standalone HTML dashboard from ccusage JSON output."
    )
    parser.add_argument(
        "agent_selector",
        nargs="?",
        help="ccusage agent selector placed first: all, codex, cc/claude, gemini, etc. Defaults to all.",
    )
    parser.add_argument(
        "--agent",
        dest="agent_option",
        help="ccusage agent selector. Kept for compatibility; overrides the positional selector.",
    )
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
    args = parser.parse_args()
    args.agent_input = args.agent_option or args.agent_selector or "all"
    args.agent = normalize_agent_selector(args.agent_input)
    return args
