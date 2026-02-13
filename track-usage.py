#!/usr/bin/env python3
"""Claude Code hook script — tracks exact token usage.

Called on the 'Stop' event via Claude Code hooks.
Reads actual usage data from session JSONL files (assistant message 'usage' field).
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def find_session_file(session_id):
    """Find the session JSONL file across all project directories."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        session_file = project_dir / f"{session_id}.jsonl"
        if session_file.exists():
            return session_file
    return None


def get_tokens_from_session(session_id, last_counted_line):
    """Parse actual token usage from assistant messages in session JSONL.

    Reads only lines after last_counted_line to get delta tokens.
    Returns (new_tokens, new_last_line).
    """
    session_file = find_session_file(session_id)
    if not session_file:
        return 0, last_counted_line

    new_tokens = 0
    current_line = 0

    try:
        with open(session_file) as f:
            for line in f:
                if current_line <= last_counted_line:
                    current_line += 1
                    continue
                try:
                    d = json.loads(line)
                    if d.get("type") == "assistant":
                        usage = d.get("message", {}).get("usage", {})
                        if usage:
                            new_tokens += usage.get("input_tokens", 0)
                            new_tokens += usage.get("output_tokens", 0)
                            new_tokens += usage.get("cache_creation_input_tokens", 0)
                            new_tokens += usage.get("cache_read_input_tokens", 0)
                except (json.JSONDecodeError, KeyError):
                    pass
                current_line += 1
    except OSError:
        return 0, last_counted_line

    return new_tokens, current_line - 1


def main():
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    session_id = hook_input.get("session_id", "")

    config = load_json(CONFIG_FILE, {
        "tokenLimit": 45000,
        "resetIntervalHours": 5,
    })

    usage = load_json(USAGE_FILE, {
        "currentWindow": {
            "startTime": datetime.now().isoformat(),
            "tokensUsed": 0,
            "interactionCount": 0,
        },
        "sessionLines": {},
    })

    # Check if window expired → auto-reset
    window = usage.get("currentWindow", {})
    start = datetime.fromisoformat(
        window.get("startTime", datetime.now().isoformat())
    )
    reset_hours = config.get("resetIntervalHours", 5)

    if datetime.now() > start + timedelta(hours=reset_hours):
        usage = {
            "currentWindow": {
                "startTime": datetime.now().isoformat(),
                "tokensUsed": 0,
                "interactionCount": 0,
            },
            "sessionLines": {},
        }

    session_lines = usage.get("sessionLines", {})
    last_line = session_lines.get(session_id, -1)

    new_tokens, new_last_line = get_tokens_from_session(session_id, last_line)
    session_lines[session_id] = new_last_line

    window = usage["currentWindow"]
    window["tokensUsed"] = window.get("tokensUsed", 0) + new_tokens
    window["interactionCount"] = window.get("interactionCount", 0) + 1
    usage["currentWindow"] = window
    usage["sessionLines"] = session_lines

    save_json(USAGE_FILE, usage)


if __name__ == "__main__":
    main()
