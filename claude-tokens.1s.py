#!/usr/bin/env python3

# <xbar.title>Claude Code Token Monitor</xbar.title>
# <xbar.version>v4.1</xbar.version>
# <xbar.desc>Accurate token tracker with per-second countdown</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DASHBOARD_DIR = Path.home() / ".claude" / "dashboard"
CONFIG_FILE = DASHBOARD_DIR / "config.json"
USAGE_FILE = DASHBOARD_DIR / "usage.json"
RESET_SCRIPT = DASHBOARD_DIR / "reset-usage.py"

# Plan limits — cost limit is the real rate-limit basis.
# Token limit is dynamically calculated from cost limit + actual model mix.
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

# Default cost per token (Sonnet pricing) used when no usage data yet
# Sonnet: $3/M input, $15/M output — blended ~$5/M assuming 4:1 ratio
DEFAULT_COST_PER_TOKEN = 5.0 / 1_000_000


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

    cost_limit = config.get("costLimit", preset["costLimit"])
    message_limit = config.get("messageLimit", preset["messageLimit"])
    window_hours = config.get("windowHours", preset["windowHours"])

    now = datetime.now()
    window_start = now - timedelta(hours=window_hours)

    # ── Rolling window ──
    token_log = usage.get("tokenLog", [])

    active = []
    for entry in token_log:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts > window_start:
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

    # ── Dynamic token limit from cost limit + actual model mix ──
    if tokens_used > 0 and cost_used > 0:
        cost_per_token = cost_used / tokens_used
    else:
        cost_per_token = DEFAULT_COST_PER_TOKEN

    token_limit = int(cost_limit / cost_per_token)
    remaining_tokens = max(0, token_limit - tokens_used)

    pct_tokens = (tokens_used / token_limit * 100) if token_limit > 0 else 0
    pct_cost = (cost_used / cost_limit * 100) if cost_limit > 0 else 0
    pct_messages = (
        (messages_used / message_limit * 100) if message_limit > 0 else 0
    )

    pct_max = max(pct_tokens, pct_cost, pct_messages)

    # ── Next recharge ──
    if active:
        active_sorted = sorted(active, key=lambda e: e["ts"])
        oldest_ts = active_sorted[0]["ts"]
        next_recharge_at = oldest_ts + timedelta(hours=window_hours)
        recharge_seconds = max(
            0, int((next_recharge_at - now).total_seconds())
        )
        recharge_tokens = active_sorted[0]["total_tokens"]
    else:
        recharge_seconds = 0
        recharge_tokens = 0

    # ── Full window clear ──
    if active:
        newest_ts = max(e["ts"] for e in active)
        full_clear_at = newest_ts + timedelta(hours=window_hours)
        full_clear_seconds = max(
            0, int((full_clear_at - now).total_seconds())
        )
    else:
        full_clear_seconds = 0

    # ── Icon & color ──
    if pct_max >= 90:
        icon = "\u26a0\ufe0f"
        color = "#FF4444"
    elif pct_max >= 70:
        icon = "\u26a1"
        color = "#FFAA00"
    else:
        icon = "\u26a1"
        color = "#44FF44"

    used_fmt = format_tokens(tokens_used)
    limit_fmt = format_tokens(token_limit)

    # ── Menu Bar: tokens ──
    if recharge_seconds > 0:
        countdown = fmt_countdown_short(recharge_seconds)
        print(
            f"{icon} {used_fmt}/{limit_fmt} "
            f"\u00b7 \u23f1 {countdown} | size=13"
        )
    else:
        print(f"{icon} {used_fmt}/{limit_fmt} | size=13")

    # ── Dropdown ──
    print("---")
    plan_name = preset["name"]
    print(
        f"Claude Code Monitor \u00b7 {plan_name} "
        f"| size=13 color=#888888"
    )
    print("---")

    bar = make_progress_bar(pct_tokens)
    print(f"{bar} {pct_tokens:.1f}% | font=Menlo size=11")
    print("---")

    # Token stats
    tok_color = (
        "#FF4444"
        if pct_tokens >= 90
        else ("#FFAA00" if pct_tokens >= 70 else "#44FF44")
    )
    print(
        f"Tokens:   {used_fmt:>8} / {limit_fmt:<8} "
        f"({pct_tokens:.1f}%) | font=Menlo size=12 color={tok_color}"
    )

    # Cost stats
    cost_color = (
        "#FF4444"
        if pct_cost >= 90
        else ("#FFAA00" if pct_cost >= 70 else "#44FF44")
    )
    print(
        f"Cost:     {format_cost(cost_used):>8} / {format_cost(cost_limit):<8} "
        f"({pct_cost:.1f}%) | font=Menlo size=12 color={cost_color}"
    )

    # Message stats
    msg_color = (
        "#FF4444"
        if pct_messages >= 90
        else ("#FFAA00" if pct_messages >= 70 else "#44FF44")
    )
    print(
        f"Messages: {messages_used:>8} / {message_limit:<8} "
        f"({pct_messages:.1f}%) | font=Menlo size=12 color={msg_color}"
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
            f"\u23f1  Next +{format_tokens(recharge_tokens)} in "
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

    print(f"   Rolling window: {window_hours}h | size=11 color=#888888")
    print("---")

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
