#!/bin/bash
set -e

# ─── Claude Code Token Monitor v4 ─── Installer ───
#
# Usage:
#   curl install:  curl -fsSL https://raw.githubusercontent.com/crinkj/claude-token-monitor/main/install.sh | bash
#   with plan:     curl -fsSL ... | bash -s -- --plan pro
#   local install: ./install.sh
#   local + plan:  ./install.sh --plan max5

REPO_RAW="https://raw.githubusercontent.com/crinkj/claude-token-monitor/main"
DASHBOARD_DIR="$HOME/.claude/dashboard"
SETTINGS_FILE="$HOME/.claude/settings.json"
SCRIPT_DIR="$(cd "$(dirname "$0" 2>/dev/null)" 2>/dev/null && pwd 2>/dev/null || echo "")"
FILES="claude-tokens.1s.py track-usage.py reset-usage.py scan-sessions.py"

PLAN=""

# ── Parse arguments ──
while [[ $# -gt 0 ]]; do
    case $1 in
        --plan|-p) PLAN="$2"; shift 2 ;;
        pro)       PLAN="pro"; shift ;;
        max5)      PLAN="max5"; shift ;;
        max20)     PLAN="max20"; shift ;;
        max_5x)    PLAN="max5"; shift ;;
        max_20x)   PLAN="max20"; shift ;;
        *)         shift ;;
    esac
done

echo ""
echo "  ⚡ Claude Code Token Monitor v4 — Installer"
echo "  ──────────────────────────────────────────"
echo ""

# ── 1. Check python3 ──
if ! command -v python3 &>/dev/null; then
    echo "  ❌ python3 is required. Install it first."
    exit 1
fi
echo "  ✅ python3 found"

# ── 2. Install SwiftBar ──
if ! [ -d "/Applications/SwiftBar.app" ]; then
    echo ""
    echo "  SwiftBar is not installed."
    if command -v brew &>/dev/null; then
        read -p "  Install SwiftBar via Homebrew? (y/n) " -n 1 -r < /dev/tty
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            brew install --cask swiftbar
            echo "  ✅ SwiftBar installed"
        else
            echo "  ⚠️  Install SwiftBar manually: brew install --cask swiftbar"
        fi
    else
        echo "  ⚠️  Install SwiftBar manually: https://github.com/swiftbar/SwiftBar"
    fi
else
    echo "  ✅ SwiftBar found"
fi

# ── 3. Select plan ──
if [ -z "$PLAN" ]; then
    echo ""
    echo "  Select your Claude plan:"
    echo ""
    echo "    1) Pro      — 19K tokens / \$18 cost / 250 msgs per 5h"
    echo "    2) Max 5x   — 88K tokens / \$35 cost / 1K msgs per 5h"
    echo "    3) Max 20x  — 220K tokens / \$140 cost / 2K msgs per 5h"
    echo ""
    read -p "  Enter choice (1-3): " plan_choice < /dev/tty

    case $plan_choice in
        2) PLAN="max5" ;;
        3) PLAN="max20" ;;
        *) PLAN="pro" ;;
    esac
fi

case $PLAN in
    max5)    PLAN_NAME="Max 5x" ;;
    max20)   PLAN_NAME="Max 20x" ;;
    *)       PLAN="pro"; PLAN_NAME="Pro" ;;
esac
echo "  ✅ Plan: $PLAN_NAME"

# ── 4. Create dashboard directory ──
mkdir -p "$DASHBOARD_DIR"

# ── 5. Download or copy scripts ──
is_local() {
    [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/claude-tokens.1s.py" ]
}

if is_local; then
    for f in $FILES; do
        cp "$SCRIPT_DIR/$f" "$DASHBOARD_DIR/"
    done
    echo "  ✅ Scripts copied (local)"
else
    for f in $FILES; do
        curl -fsSL "$REPO_RAW/$f" -o "$DASHBOARD_DIR/$f"
    done
    echo "  ✅ Scripts downloaded (GitHub)"
fi
chmod +x "$DASHBOARD_DIR"/*.py

# ── 6. Create config ──
cat > "$DASHBOARD_DIR/config.json" << EOF
{
  "plan": "$PLAN"
}
EOF
echo "  ✅ Config created (plan: $PLAN_NAME)"

# ── 7. Scan existing sessions ──
echo ""
python3 "$DASHBOARD_DIR/scan-sessions.py"
echo "  ✅ Existing usage imported"

# ── 8. Set up Claude Code hooks ──
echo ""
echo "  Setting up Claude Code hooks..."

if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
fi

python3 << 'PYEOF'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
dashboard_dir = Path.home() / ".claude" / "dashboard"

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

hook_command = f"python3 {dashboard_dir}/track-usage.py"

hooks = settings.get("hooks", {})
stop_hooks = hooks.get("Stop", [])

already_installed = False
for entry in stop_hooks:
    for h in entry.get("hooks", []):
        if h.get("command", "") == hook_command:
            already_installed = True
            break

if not already_installed:
    stop_hooks.append({
        "hooks": [{
            "type": "command",
            "command": hook_command
        }]
    })
    hooks["Stop"] = stop_hooks
    settings["hooks"] = hooks

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print("  ✅ Claude Code hook registered")
else:
    print("  ✅ Hook already registered")
PYEOF

# ── 9. Link SwiftBar plugin ──
echo ""

# Remove old plugin versions
rm -f "$DASHBOARD_DIR/claude-tokens.30s.py"
rm -f "$DASHBOARD_DIR/claude-tokens.5s.py"

SWIFTBAR_DIR=$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || echo "")

if [ -z "$SWIFTBAR_DIR" ]; then
    defaults write com.ameba.SwiftBar PluginDirectory -string "$DASHBOARD_DIR"
    echo "  ✅ SwiftBar plugin directory set to: $DASHBOARD_DIR"
else
    SWIFTBAR_DIR=$(eval echo "$SWIFTBAR_DIR")
    if [ "$SWIFTBAR_DIR" != "$DASHBOARD_DIR" ]; then
        rm -f "$SWIFTBAR_DIR/claude-tokens.30s.py"
        rm -f "$SWIFTBAR_DIR/claude-tokens.5s.py"
        rm -f "$SWIFTBAR_DIR/claude-tokens.1s.py"
        ln -sf "$DASHBOARD_DIR/claude-tokens.1s.py" "$SWIFTBAR_DIR/claude-tokens.1s.py"
        echo "  ✅ Plugin linked to SwiftBar: $SWIFTBAR_DIR"
    else
        echo "  ✅ Plugin in SwiftBar directory"
    fi
fi

# ── 10. Start SwiftBar ──
if [ -d "/Applications/SwiftBar.app" ]; then
    killall SwiftBar 2>/dev/null || true
    sleep 1
    open -a SwiftBar
    echo "  ✅ SwiftBar started"
fi

# ── Done ──
echo ""
echo "  ──────────────────────────────────────────"
echo "  ✅ Installation complete!"
echo ""
echo "  Config: $DASHBOARD_DIR/config.json"
echo "  Adjust costLimit, tokenLimit, or windowHours if needed."
echo ""
