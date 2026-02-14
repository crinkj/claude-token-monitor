#!/usr/bin/env python3

# <xbar.title>Claude Code Token Monitor</xbar.title>
# <xbar.version>v4.0</xbar.version>
# <xbar.desc>Accurate cost & token tracker with per-second countdown</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"
RESET_SCRIPT = DASHBOARD_DIR / "reset-usage.py"

# Plan limits — cost & message limits are the real rate-limit metrics.
# Token counts are shown as info only (no hard limit, varies by model mix).
PLAN_PRESETS = {
    "pro": {
        "name": "Pro",
        "costLimit": 18.0,
        "messageLimit": 250,
        "windowHours": 5,
    },
    "max5": {
        "name": "Max 5x",
        "costLimit": 35.0,
        "messageLimit": 1_000,
        "windowHours": 5,
    },
    "max20": {
        "name": "Max 20x",
        "costLimit": 140.0,
        "messageLimit": 2_000,
        "windowHours": 5,
    },
    # Backward compatibility aliases
    "max_5x": {
        "name": "Max 5x",
        "costLimit": 35.0,
        "messageLimit": 1_000,
        "windowHours": 5,
    },
    "max_20x": {
        "name": "Max 20x",
        "costLimit": 140.0,
        "messageLimit": 2_000,
        "windowHours": 5,
    },
}


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_cost(c):
    if c >= 100:
        return f"${c:.0f}"
    elif c >= 10:
        return f"${c:.1f}"
    return f"${c:.2f}"


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


def get_tier_name(model):
    """Map model name to display tier."""
    if not model:
        return "Sonnet"
    m = model.lower()
    if "opus" in m:
        return "Opus"
    if "haiku" in m:
        return "Haiku"
    return "Sonnet"


def main():
    config = load_json(CONFIG_FILE, {"plan": "pro"})
    usage = load_json(USAGE_FILE, {"tokenLog": [], "sessionLines": {}})

    plan_key = config.get("plan", "pro")
    preset = PLAN_PRESETS.get(plan_key, PLAN_PRESETS["pro"])

    # Allow config overrides
    cost_limit = config.get("costLimit", preset["costLimit"])
    message_limit = config.get("messageLimit", preset["messageLimit"])
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
                # Support both old format (tokens) and new format (total_tokens)
                total_tokens = entry.get(
                    "total_tokens", entry.get("tokens", 0)
                )
                cost_usd = entry.get("cost_usd", 0)
                model = entry.get("model", "unknown")
                active.append(
                    {
                        "ts": ts,
                        "total_tokens": total_tokens,
                        "cost_usd": cost_usd,
                        "model": model,
                    }
                )
        except (KeyError, ValueError):
            continue

    tokens_used = sum(e["total_tokens"] for e in active)
    cost_used = sum(e["cost_usd"] for e in active)
    messages_used = len(active)

    remaining_cost = max(0, cost_limit - cost_used)

    pct_cost = (cost_used / cost_limit * 100) if cost_limit > 0 else 0
    pct_messages = (
        (messages_used / message_limit * 100) if message_limit > 0 else 0
    )

    # Primary metric: whichever is highest percentage (cost or messages)
    pct_max = max(pct_cost, pct_messages)

    # ── Next recharge: when the oldest entry in the window expires ──
    if active:
        active_sorted = sorted(active, key=lambda e: e["ts"])
        oldest_ts = active_sorted[0]["ts"]
        next_recharge_at = oldest_ts + timedelta(hours=window_hours)
        recharge_seconds = max(
            0, int((next_recharge_at - now).total_seconds())
        )
        recharge_cost = active_sorted[0]["cost_usd"]
        recharge_tokens = active_sorted[0]["total_tokens"]
    else:
        recharge_seconds = 0
        recharge_cost = 0
        recharge_tokens = 0

    # ── Full window clear: when ALL active entries have expired ──
    if active:
        newest_ts = max(e["ts"] for e in active)
        full_clear_at = newest_ts + timedelta(hours=window_hours)
        full_clear_seconds = max(
            0, int((full_clear_at - now).total_seconds())
        )
    else:
        full_clear_seconds = 0

    # ── Icon & color based on highest usage % ──
    if pct_max >= 90:
        icon = "\u26a0\ufe0f"
        color = "#FF4444"
    elif pct_max >= 70:
        icon = "\u26a1"
        color = "#FFAA00"
    else:
        icon = "\u26a1"
        color = "#44FF44"

    cost_fmt = format_cost(cost_used)
    cost_limit_fmt = format_cost(cost_limit)

    # ── Menu Bar: show cost (most accurate metric) ──
    if recharge_seconds > 0:
        countdown = fmt_countdown_short(recharge_seconds)
        print(
            f"{icon} {cost_fmt}/{cost_limit_fmt} "
            f"\u00b7 \u23f1 {countdown} | size=13"
        )
    else:
        print(f"{icon} {cost_fmt}/{cost_limit_fmt} | size=13")

    # ── Dropdown ──
    print("---")
    plan_name = preset["name"]
    print(
        f"Claude Code Monitor v4.0 \u00b7 {plan_name} "
        f"| size=13 color=#888888"
    )
    print("---")

    bar = make_progress_bar(pct_max)
    print(f"{bar} {pct_max:.1f}% | font=Menlo size=11")
    print("---")

    # Cost stats (primary limit)
    cost_color = (
        "#FF4444"
        if pct_cost >= 90
        else ("#FFAA00" if pct_cost >= 70 else "#44FF44")
    )
    print(
        f"Cost:     {cost_fmt:>8} / {cost_limit_fmt:<8} "
        f"({pct_cost:.1f}%) | font=Menlo size=12 color={cost_color}"
    )

    # Message stats (secondary limit)
    msg_color = (
        "#FF4444"
        if pct_messages >= 90
        else ("#FFAA00" if pct_messages >= 70 else "#44FF44")
    )
    print(
        f"Messages: {messages_used:>8} / {message_limit:<8} "
        f"({pct_messages:.1f}%) | font=Menlo size=12 color={msg_color}"
    )

    # Token stats (info only — no hard limit, varies by model)
    print(
        f"Tokens:   {format_tokens(tokens_used):>8} used"
        f" | font=Menlo size=12 color=#AAAAAA"
    )

    print("---")

    # Model breakdown by tier
    tier_costs = defaultdict(float)
    tier_tokens = defaultdict(int)
    for e in active:
        tier = get_tier_name(e.get("model", ""))
        tier_costs[tier] += e["cost_usd"]
        tier_tokens[tier] += e["total_tokens"]

    if tier_costs:
        print("Model breakdown: | size=12 color=#888888")
        for tier, cost in sorted(
            tier_costs.items(), key=lambda x: -x[1]
        ):
            tok = format_tokens(tier_tokens[tier])
            print(
                f"  {tier}: {format_cost(cost)} ({tok}) "
                f"| font=Menlo size=11 color=#AAAAAA"
            )
        print("---")

    # Recharge info
    if recharge_seconds > 0:
        print(
            f"\u23f1  Next +{format_cost(recharge_cost)} "
            f"(+{format_tokens(recharge_tokens)}) in "
            f"{fmt_countdown(recharge_seconds)} | color=#66CCFF"
        )
    else:
        print(
            "\u2705  No active usage \u2014 fully recharged "
            "| color=#44FF44"
        )

    if full_clear_seconds > 0:
        print(
            f"\U0001f504  Full recharge in "
            f"{fmt_countdown(full_clear_seconds)} | color=#888888 size=11"
        )

    print("---")

    # Window info
    print(f"   Rolling window: {window_hours}h | size=11 color=#888888")
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
