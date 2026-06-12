from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from typing import Any


AGENT_ALIASES = {
    "": "all",
    "*": "all",
    "all": "all",
    "auto": "all",
    "everything": "all",
    "cc": "claude",
    "claude code": "claude",
    "claude-code": "claude",
    "claude_code": "claude",
    "gemini cli": "gemini",
    "gemijni": "gemini",
    "gemni": "gemini",
}


def normalize_agent_selector(value: str | None) -> str:
    raw = str(value or "all").strip()
    key = raw.lower()
    return AGENT_ALIASES.get(key, key)


def agent_is_all(agent: str) -> bool:
    return normalize_agent_selector(agent) == "all"


def wrap_executable(executable: str, rest: list[str]) -> list[str]:
    resolved = shutil.which(executable) or executable
    if os.name == "nt" and str(resolved).lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved, *rest]
    return [resolved, *rest]


def ccusage_command(args: argparse.Namespace, scope: str) -> list[str]:
    rest: list[str]
    if agent_is_all(args.agent):
        rest = [scope]
    else:
        rest = [args.agent, scope]

    rest.append("--json")
    if args.since:
        rest.extend(["--since", args.since])
    if args.until:
        rest.extend(["--until", args.until])
    if args.timezone:
        rest.extend(["--timezone", args.timezone])
    if args.offline:
        rest.append("--offline")
    if args.no_cost:
        rest.append("--no-cost")
    if args.agent == "codex" and scope in ("daily", "monthly", "session"):
        rest.extend(["--speed", args.speed])
    return wrap_executable(args.ccusage_bin, rest)


def run_ccusage(args: argparse.Namespace, scope: str, required: bool = True) -> dict[str, Any]:
    cmd = ccusage_command(args, scope)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        if required:
            joined = " ".join(cmd)
            raise SystemExit(f"ccusage failed for {scope}: {joined}\n{proc.stderr.strip()}")
        return {}

    stdout = proc.stdout.strip()
    if not stdout:
        return {}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        if required:
            preview = stdout[:400].replace("\n", " ")
            raise SystemExit(f"ccusage {scope} did not return JSON. Preview: {preview}")
        return {}
