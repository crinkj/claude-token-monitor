#!/usr/bin/env python3

# <xbar.title>Claude Code Token Monitor</xbar.title>
# <xbar.version>v3.0</xbar.version>
# <xbar.desc>Rolling-window token tracker with per-second countdown</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>

import json
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"
RESET_SCRIPT = DASHBOARD_DIR / "reset-usage.py"

PLAN_PRESETS = {
    "pro": {"name": "Pro", "tokenLimit": 200_000, "windowHours": 5},
    "max_5x": {"name": "Max 5x", "tokenLimit": 1_000_000, "windowHours": 5},
    "max_20x": {"name": "Max 20x", "tokenLimit": 4_000_000, "windowHours": 5},
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


def fmt_countdown(seconds):
    """Full format: Xh XXm XXs."""
    if seconds <= 0:
        return "0s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_countdown_short(seconds):
    """Short format for menu bar."""
    if seconds <= 0:
        return "0s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    elif m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def main():
    config = load_json(CONFIG_FILE, {"plan": "pro"})
    usage = load_json(USAGE_FILE, {"tokenLog": [], "sessionLines": {}})

    plan_key = config.get("plan", "pro")
    preset = PLAN_PRESETS.get(plan_key, PLAN_PRESETS["pro"])

    # Allow config overrides
    token_limit = config.get("tokenLimit", preset["tokenLimit"])
    window_hours = config.get("windowHours", preset["windowHours"])

    now = datetime.now()
    window_start = now - timedelta(hours=window_hours)

    # ── Rolling window calculation ──
    token_log = usage.get("tokenLog", [])

    active = []
    for entry in token_log:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts > window_start:
                active.append({"ts": ts, "tokens": entry["tokens"]})
        except (KeyError, ValueError):
            continue

    tokens_used = sum(e["tokens"] for e in active)
    remaining_tokens = max(0, token_limit - tokens_used)
    pct = (tokens_used / token_limit * 100) if token_limit > 0 else 0

    # ── Next recharge: when the oldest entry in the window expires ──
    if active:
        active_sorted = sorted(active, key=lambda e: e["ts"])
        oldest_ts = active_sorted[0]["ts"]
        next_recharge_at = oldest_ts + timedelta(hours=window_hours)
        recharge_seconds = max(0, int((next_recharge_at - now).total_seconds()))
        recharge_tokens = active_sorted[0]["tokens"]
    else:
        recharge_seconds = 0
        recharge_tokens = 0
        next_recharge_at = now

    # ── Full window clear: when ALL active entries have expired ──
    if active:
        newest_ts = max(e["ts"] for e in active)
        full_clear_at = newest_ts + timedelta(hours=window_hours)
        full_clear_seconds = max(0, int((full_clear_at - now).total_seconds()))
    else:
        full_clear_seconds = 0

    # ── Icon & color ──
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
    if recharge_seconds > 0:
        countdown = fmt_countdown_short(recharge_seconds)
        print(f"{icon} {used_fmt}/{total_fmt} \u00b7 \u23f1 {countdown} | size=13")
    else:
        print(f"{icon} {used_fmt}/{total_fmt} | size=13")

    # ── Dropdown ──
    print("---")
    plan_name = preset["name"]
    print(f"Claude Code Token Monitor \u00b7 {plan_name} | size=13 color=#888888")
    print("---")

    bar = make_progress_bar(pct)
    print(f"{bar} {pct:.1f}% | font=Menlo size=11")
    print("---")

    print(f"Used:        {tokens_used:>12,} tokens | font=Menlo size=12")
    print(f"Remaining:   {remaining_tokens:>12,} tokens | font=Menlo size=12 color={color}")
    print(f"Limit:       {token_limit:>12,} tokens | font=Menlo size=12")
    print(f"Active logs: {len(active):>12} | font=Menlo size=12")
    print("---")

    if recharge_seconds > 0:
        print(
            f"\u23f1  Next +{format_tokens(recharge_tokens)} in "
            f"{fmt_countdown(recharge_seconds)} | color=#66CCFF"
        )
    else:
        print("\u2705  No active usage \u2014 fully recharged | color=#44FF44")

    if full_clear_seconds > 0:
        print(
            f"\U0001f504  Full recharge in "
            f"{fmt_countdown(full_clear_seconds)} | color=#888888 size=11"
        )

    print("---")

    # Window info
    print(
        f"   Rolling window: {window_hours}h | "
        f"size=11 color=#888888"
    )
    print("---")

    # Actions
    print(
        f"\U0001f5d1  Reset Counter"
        f" | bash={RESET_SCRIPT} terminal=false refresh=true"
    )
    print(
        f"\u2699\ufe0f  Edit Config"
        f" | bash=/usr/bin/open param1={CONFIG_FILE} terminal=false"
    )
    print("\U0001f503 Refresh | refresh=true")


if __name__ == "__main__":
    main()
