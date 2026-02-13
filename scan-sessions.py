#!/usr/bin/env python3
"""Scan existing Claude Code sessions to populate the initial token log.

Reads all session JSONL files and extracts assistant message usage data
from the last N hours (matching the configured rolling window).
"""

import json
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


def parse_timestamp(ts_str):
    """Parse ISO timestamp, handling both UTC 'Z' suffix and local times."""
    if ts_str.endswith("Z"):
        utc_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return utc_dt.astimezone().replace(tzinfo=None)  # convert to local
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def scan_all_sessions(window_hours):
    """Scan all session files and return token log entries within the window."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return [], {}

    cutoff = datetime.now() - timedelta(hours=window_hours)
    entries = []
    session_lines = {}

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for session_file in project_dir.glob("*.jsonl"):
            session_id = session_file.stem
            line_count = -1

            try:
                with open(session_file) as f:
                    for line_num, line in enumerate(f):
                        line_count = line_num
                        try:
                            d = json.loads(line)
                            if d.get("type") != "assistant":
                                continue
                            msg = d.get("message", {})
                            usage = msg.get("usage", {})
                            ts_str = d.get("timestamp")
                            if not usage or not ts_str:
                                continue

                            ts = parse_timestamp(ts_str)
                            if ts is None or ts < cutoff:
                                continue

                            tokens = (
                                usage.get("input_tokens", 0)
                                + usage.get("output_tokens", 0)
                                + usage.get("cache_creation_input_tokens", 0)
                            )
                            if tokens > 0:
                                entries.append({
                                    "timestamp": ts.isoformat(),
                                    "tokens": tokens,
                                })
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except OSError:
                continue

            session_lines[session_id] = line_count

    entries.sort(key=lambda e: e["timestamp"])
    return entries, session_lines


def main():
    config = load_json(CONFIG_FILE, {"plan": "pro"})
    plan_key = config.get("plan", "pro")
    preset = PLAN_PRESETS.get(plan_key, PLAN_PRESETS["pro"])
    window_hours = config.get("windowHours", preset["windowHours"])

    print(f"  Scanning sessions (last {window_hours}h)...")
    entries, session_lines = scan_all_sessions(window_hours)

    total_tokens = sum(e["tokens"] for e in entries)

    usage = {
        "tokenLog": entries,
        "sessionLines": session_lines,
    }
    save_json(USAGE_FILE, usage)

    print(f"  Found {len(entries)} interactions, {total_tokens:,} tokens")


if __name__ == "__main__":
    main()
