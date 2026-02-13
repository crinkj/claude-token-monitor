#!/bin/bash
set -e

# ─── Claude Code Token Monitor v3 ─── Installer ───

DASHBOARD_DIR="$HOME/.claude/dashboard"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo ""
echo "  ⚡ Claude Code Token Monitor — Installer"
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
    read -p "  Install SwiftBar via Homebrew? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install --cask swiftbar
        echo "  ✅ SwiftBar installed"
    else
        echo "  ⚠️  Skipping SwiftBar install. You'll need to install it manually."
    fi
else
    echo "  ✅ SwiftBar found"
fi

# ── 3. Select plan ──
echo ""
echo "  Select your Claude plan:"
echo ""
echo "    1) Pro"
echo "    2) Max 5x"
echo "    3) Max 20x"
echo ""
read -p "  Enter choice (1-3): " plan_choice

case $plan_choice in
    2) PLAN="max_5x" ; PLAN_NAME="Max 5x" ;;
    3) PLAN="max_20x" ; PLAN_NAME="Max 20x" ;;
    *) PLAN="pro" ; PLAN_NAME="Pro" ;;
esac
echo "  ✅ Plan: $PLAN_NAME"

# ── 4. Create dashboard directory ──
mkdir -p "$DASHBOARD_DIR"

# ── 5. Copy scripts ──
cp "$SCRIPT_DIR/claude-tokens.1s.py" "$DASHBOARD_DIR/"
cp "$SCRIPT_DIR/track-usage.py" "$DASHBOARD_DIR/"
cp "$SCRIPT_DIR/reset-usage.py" "$DASHBOARD_DIR/"
cp "$SCRIPT_DIR/scan-sessions.py" "$DASHBOARD_DIR/"
chmod +x "$DASHBOARD_DIR/claude-tokens.1s.py"
chmod +x "$DASHBOARD_DIR/track-usage.py"
chmod +x "$DASHBOARD_DIR/reset-usage.py"
chmod +x "$DASHBOARD_DIR/scan-sessions.py"
echo "  ✅ Scripts copied"

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
        ln -sf "$DASHBOARD_DIR/claude-tokens.1s.py" "$SWIFTBAR_DIR/claude-tokens.1s.py"
        echo "  ✅ Plugin linked to SwiftBar: $SWIFTBAR_DIR"
    else
        echo "  ✅ Plugin in SwiftBar directory"
    fi
fi

# ── Done ──
echo ""
echo "  ──────────────────────────────────────────"
echo "  ✅ Installation complete!"
echo ""
echo "  Next steps:"
echo "  1. Open SwiftBar (or restart it)"
echo "  2. Token usage will be tracked automatically"
echo ""
echo "  Config: $DASHBOARD_DIR/config.json"
echo "  Adjust tokenLimit or windowHours if needed."
echo ""
