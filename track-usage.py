#!/usr/bin/env python3
"""Claude Code hook — appends exact token usage to a rolling log.

Called on the 'Stop' event.  Reads the session JSONL to extract real
usage numbers from every new assistant message since the last invocation.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"

PLAN_PRESETS = {
    "pro": {"windowHours": 5},
    "max_5x": {"windowHours": 5},
    "max_20x": {"windowHours": 5},
}


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


def parse_new_messages(session_id, last_line):
    """Read new assistant messages and return list of {timestamp, tokens}."""
    session_file = find_session_file(session_id)
    if not session_file:
        return [], last_line

    entries = []
    current_line = 0

    try:
        with open(session_file) as f:
            for line in f:
                if current_line <= last_line:
                    current_line += 1
                    continue
                try:
                    d = json.loads(line)
                    if d.get("type") == "assistant":
                        msg = d.get("message", {})
                        usage = msg.get("usage", {})
                        ts_str = d.get("timestamp")
                        if usage and ts_str:
                            # Convert UTC 'Z' timestamps to local
                            if ts_str.endswith("Z"):
                                ts_local = datetime.fromisoformat(
                                    ts_str.replace("Z", "+00:00")
                                ).astimezone().replace(tzinfo=None)
                                ts_iso = ts_local.isoformat()
                            else:
                                ts_iso = ts_str
                            # Count input + output + cache_creation
                            # (cache_read is near-free and likely not rate-limited)
                            tokens = (
                                usage.get("input_tokens", 0)
                                + usage.get("output_tokens", 0)
                                + usage.get("cache_creation_input_tokens", 0)
                            )
                            if tokens > 0:
                                entries.append({
                                    "timestamp": ts_iso,
                                    "tokens": tokens,
                                })
                except (json.JSONDecodeError, KeyError):
                    pass
                current_line += 1
    except OSError:
        return [], last_line

    return entries, current_line - 1


def cleanup_old_entries(token_log, window_hours):
    """Remove entries older than 2× the window to keep the file small."""
    cutoff = datetime.now() - timedelta(hours=window_hours * 2)
    return [
        e for e in token_log
        if datetime.fromisoformat(e["timestamp"]) > cutoff
    ]


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    session_id = hook_input.get("session_id", "")
    if not session_id:
        return

    config = load_json(CONFIG_FILE, {"plan": "pro"})
    usage = load_json(USAGE_FILE, {"tokenLog": [], "sessionLines": {}})

    plan_key = config.get("plan", "pro")
    preset = PLAN_PRESETS.get(plan_key, PLAN_PRESETS["pro"])
    window_hours = config.get("windowHours", preset["windowHours"])

    session_lines = usage.get("sessionLines", {})
    last_line = session_lines.get(session_id, -1)

    new_entries, new_last_line = parse_new_messages(session_id, last_line)

    if new_entries or new_last_line != last_line:
        session_lines[session_id] = new_last_line

        token_log = usage.get("tokenLog", [])
        token_log.extend(new_entries)
        token_log = cleanup_old_entries(token_log, window_hours)

        usage["tokenLog"] = token_log
        usage["sessionLines"] = session_lines
        save_json(USAGE_FILE, usage)


if __name__ == "__main__":
    main()
