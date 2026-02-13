#!/usr/bin/env python3

# <xbar.title>Claude Code Token Monitor</xbar.title>
# <xbar.version>v1.0</xbar.version>
# <xbar.desc>Shows Claude Code token usage and reset countdown in the macOS menu bar</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
# <xbar.var>string(CONFIG_PATH=~/.claude/dashboard/config.json): Path to config file</xbar.var>

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"
RESET_SCRIPT = DASHBOARD_DIR / "reset-usage.py"


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


def format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def make_progress_bar(pct, width=20):
    filled = int(width * min(pct, 100) / 100)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def main():
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

    window = usage.get("currentWindow", {})
    start_str = window.get("startTime", datetime.now().isoformat())
    start = datetime.fromisoformat(start_str)
    reset_hours = config.get("resetIntervalHours", 5)
    reset_time = start + timedelta(hours=reset_hours)
    now = datetime.now()

    # Auto-reset if window expired
    if now > reset_time:
        usage = {
            "currentWindow": {
                "startTime": now.isoformat(),
                "tokensUsed": 0,
                "interactionCount": 0,
            },
            "sessionSizes": {},
        }
        save_json(USAGE_FILE, usage)
        window = usage["currentWindow"]
        start = now
        reset_time = start + timedelta(hours=reset_hours)

    tokens_used = window.get("tokensUsed", 0)
    token_limit = config.get("tokenLimit", 45000)
    interactions = window.get("interactionCount", 0)
    remaining_tokens = max(0, token_limit - tokens_used)

    remaining_time = reset_time - now
    if remaining_time.total_seconds() < 0:
        remaining_time = timedelta(0)
    hours = int(remaining_time.total_seconds() // 3600)
    minutes = int((remaining_time.total_seconds() % 3600) // 60)

    pct = (tokens_used / token_limit * 100) if token_limit > 0 else 0

    # Icon & color
    if pct >= 90:
        icon = "\u26a0\ufe0f"
        color = "#FF4444"
    elif pct >= 70:
        icon = "\u26a1"
        color = "#FFAA00"
    else:
        icon = "\u26a1"
        color = "#44FF44"

    used_fmt = format_tokens(tokens_used)
    total_fmt = format_tokens(token_limit)

    # ── Menu Bar ──
    print(f"{icon} {used_fmt}/{total_fmt} \u00b7 \u23f1 {hours}h{minutes:02d}m | size=13")

    # ── Dropdown ──
    print("---")
    print("Claude Code Token Monitor | size=13 color=#888888")
    print("---")

    # Progress bar
    bar = make_progress_bar(pct)
    print(f"{bar} {pct:.0f}% | font=Menlo size=11")
    print("---")

    print(f"Used:        {tokens_used:>10,} tokens | font=Menlo size=12")
    print(f"Remaining:   {remaining_tokens:>10,} tokens | font=Menlo size=12 color={color}")
    print(f"Limit:       {token_limit:>10,} tokens | font=Menlo size=12")
    print(f"Interactions:{interactions:>10} | font=Menlo size=12")
    print("---")

    print(f"\u23f1  Reset in {hours}h {minutes:02d}m | color=#66CCFF")
    print(f"   Window: {start.strftime('%H:%M')} ~ {reset_time.strftime('%H:%M')} | size=11 color=#888888")
    print("---")

    # Action buttons
    print(
        f"\U0001f504 Reset Counter"
        f" | bash={RESET_SCRIPT} terminal=false refresh=true"
    )
    print(
        f"\u2699\ufe0f  Edit Config"
        f" | bash=/usr/bin/open param1={CONFIG_FILE} terminal=false"
    )
    print("\U0001f503 Refresh | refresh=true")


if __name__ == "__main__":
    main()
