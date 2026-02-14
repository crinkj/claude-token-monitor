#!/usr/bin/env python3
"""Claude Code hook — tracks token usage and cost to a rolling log.

Called on the 'Stop' event. Reads the session JSONL to extract real
usage numbers from every new assistant message since the last invocation.
Calculates USD cost per model using Anthropic pricing.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"

WINDOW_HOURS = 5

# Pricing per million tokens (USD) — from Anthropic pricing page
MODEL_PRICING = {
    "opus": {
        "input": 15.0,
        "output": 75.0,
        "cache_creation": 18.75,
        "cache_read": 1.5,
    },
    "sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_creation": 3.75,
        "cache_read": 0.3,
    },
    "haiku": {
        "input": 0.25,
        "output": 1.25,
        "cache_creation": 0.3,
        "cache_read": 0.03,
    },
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
    """Parse ISO timestamp, handling UTC 'Z' suffix."""
    if not ts_str:
        return None
    if ts_str.endswith("Z"):
        utc_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return utc_dt.astimezone().replace(tzinfo=None)
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def get_model_tier(model_name):
    """Map model name to pricing tier (opus/sonnet/haiku)."""
    if not model_name:
        return "sonnet"
    m = model_name.lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "sonnet"


def extract_model(data):
    """Extract model name from message data (checks multiple paths)."""
    msg = data.get("message", {})
    if isinstance(msg, dict):
        model = msg.get("model")
        if model:
            return model
    for key in ("model", "Model"):
        if data.get(key):
            return data[key]
    usage = data.get("usage", {})
    if isinstance(usage, dict) and usage.get("model"):
        return usage["model"]
    return "unknown"


def calculate_cost(model, input_tokens, output_tokens, cache_creation, cache_read):
    """Calculate USD cost based on model pricing."""
    tier = get_model_tier(model)
    pricing = MODEL_PRICING.get(tier, MODEL_PRICING["sonnet"])
    cost = (
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"]
        + (cache_creation / 1_000_000) * pricing["cache_creation"]
        + (cache_read / 1_000_000) * pricing["cache_read"]
    )
    return round(cost, 6)


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
    """Read new assistant messages and return list of usage entries."""
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
                            ts = parse_timestamp(ts_str)
                            if ts is None:
                                current_line += 1
                                continue

                            input_tokens = usage.get("input_tokens", 0)
                            output_tokens = usage.get("output_tokens", 0)
                            cache_creation = usage.get(
                                "cache_creation_input_tokens", 0
                            )
                            cache_read = usage.get(
                                "cache_read_input_tokens", 0
                            )

                            total = (
                                input_tokens
                                + output_tokens
                                + cache_creation
                                + cache_read
                            )

                            if total > 0:
                                model = extract_model(d)
                                cost = calculate_cost(
                                    model,
                                    input_tokens,
                                    output_tokens,
                                    cache_creation,
                                    cache_read,
                                )
                                entries.append(
                                    {
                                        "timestamp": ts.isoformat(),
                                        "input_tokens": input_tokens,
                                        "output_tokens": output_tokens,
                                        "cache_creation_tokens": cache_creation,
                                        "cache_read_tokens": cache_read,
                                        "total_tokens": total,
                                        "model": model,
                                        "cost_usd": cost,
                                    }
                                )
                except (json.JSONDecodeError, KeyError):
                    pass
                current_line += 1
    except OSError:
        return [], last_line

    return entries, current_line - 1


def cleanup_old_entries(token_log, window_hours):
    """Remove entries older than 2x the window to keep the file small."""
    cutoff = datetime.now() - timedelta(hours=window_hours * 2)
    result = []
    for e in token_log:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
            if ts > cutoff:
                result.append(e)
        except (KeyError, ValueError):
            continue
    return result


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

    window_hours = config.get("windowHours", WINDOW_HOURS)

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
