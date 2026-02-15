#!/usr/bin/env python3
"""Scan existing Claude Code sessions to populate the initial token log.

Reads all session JSONL files and extracts assistant message usage data
from the last N hours (matching the configured rolling window).
Calculates USD cost per model and deduplicates by message_id + request_id.
"""

import json
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
    """Parse ISO timestamp, handling both UTC 'Z' suffix and local times."""
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


def scan_all_sessions(window_hours):
    """Scan all session files and return token log entries within the window."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return [], {}

    cutoff = datetime.now() - timedelta(hours=window_hours)
    entries = []
    session_lines = {}
    seen_hashes = set()

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

                            # Deduplication via message_id + request_id
                            msg_id = d.get("message_id") or (
                                msg.get("id") if isinstance(msg, dict) else ""
                            )
                            req_id = d.get("request_id") or d.get(
                                "requestId", ""
                            )
                            if msg_id and req_id:
                                h = f"{msg_id}:{req_id}"
                                if h in seen_hashes:
                                    continue
                                seen_hashes.add(h)

                            ts = parse_timestamp(ts_str)
                            if ts is None or ts < cutoff:
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
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except OSError:
                continue

            session_lines[session_id] = line_count

    entries.sort(key=lambda e: e["timestamp"])
    return entries, session_lines


def main():
    config = load_json(CONFIG_FILE, {"plan": "pro"})
    window_hours = config.get("windowHours", WINDOW_HOURS)

    entries, session_lines = scan_all_sessions(window_hours)

    total_tokens = sum(e.get("total_tokens", 0) for e in entries)
    total_cost = sum(e.get("cost_usd", 0) for e in entries)

    usage = {
        "tokenLog": entries,
        "sessionLines": session_lines,
    }
    save_json(USAGE_FILE, usage)



if __name__ == "__main__":
    main()
