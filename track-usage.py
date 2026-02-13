#!/usr/bin/env python3
"""Claude Code hook script — estimates token usage per interaction.

Called on the 'Stop' event via Claude Code hooks.
Receives JSON on stdin with session_id, cwd, etc.
Estimates tokens from session JSONL file size delta.
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


def estimate_tokens(session_id, session_sizes):
    """Estimate tokens from session file size delta.

    Uses ~6 bytes per token as a rough heuristic
    (JSON overhead reduces the effective chars-per-token ratio).
    """
    if not session_id:
        return 1000  # fallback

    session_file = find_session_file(session_id)
    if not session_file:
        return 1000

    try:
        current_size = session_file.stat().st_size
    except OSError:
        return 1000

    previous_size = session_sizes.get(session_id, 0)
    delta = max(0, current_size - previous_size)

    # Store new size
    session_sizes[session_id] = current_size

    # ~6 bytes per token (accounts for JSON structure overhead)
    return max(100, delta // 6)


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
        "sessionSizes": {},
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
            "sessionSizes": {},
        }

    session_sizes = usage.get("sessionSizes", {})
    estimated = estimate_tokens(session_id, session_sizes)

    window = usage["currentWindow"]
    window["tokensUsed"] = window.get("tokensUsed", 0) + estimated
    window["interactionCount"] = window.get("interactionCount", 0) + 1
    usage["currentWindow"] = window
    usage["sessionSizes"] = session_sizes

    save_json(USAGE_FILE, usage)


if __name__ == "__main__":
    main()
