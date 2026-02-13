#!/bin/bash
set -e

# ─── Claude Code Token Monitor ─── Installer ───

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

# ── 3. Create dashboard directory ──
mkdir -p "$DASHBOARD_DIR"
echo "  ✅ Dashboard directory: $DASHBOARD_DIR"

# ── 4. Copy scripts ──
cp "$SCRIPT_DIR/claude-tokens.30s.py" "$DASHBOARD_DIR/"
cp "$SCRIPT_DIR/track-usage.py" "$DASHBOARD_DIR/"
cp "$SCRIPT_DIR/reset-usage.py" "$DASHBOARD_DIR/"
chmod +x "$DASHBOARD_DIR/claude-tokens.30s.py"
chmod +x "$DASHBOARD_DIR/track-usage.py"
chmod +x "$DASHBOARD_DIR/reset-usage.py"
echo "  ✅ Scripts copied"

# ── 5. Create config (if not exists) ──
if [ ! -f "$DASHBOARD_DIR/config.json" ]; then
    cp "$SCRIPT_DIR/config.template.json" "$DASHBOARD_DIR/config.json"
    echo "  ✅ Config created: $DASHBOARD_DIR/config.json"
else
    echo "  ✅ Config already exists (kept)"
fi

# ── 6. Initialize usage.json (if not exists) ──
if [ ! -f "$DASHBOARD_DIR/usage.json" ]; then
    python3 -c "
import json
from datetime import datetime
data = {
    'currentWindow': {
        'startTime': datetime.now().isoformat(),
        'tokensUsed': 0,
        'interactionCount': 0
    },
    'sessionSizes': {}
}
with open('$DASHBOARD_DIR/usage.json', 'w') as f:
    json.dump(data, f, indent=2)
"
    echo "  ✅ Usage tracker initialized"
fi

# ── 7. Set up Claude Code hooks ──
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

# Check if hook already exists
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

# ── 8. Link SwiftBar plugin ──
echo ""

# Try to detect SwiftBar plugin directory
SWIFTBAR_DIR=$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || echo "")

if [ -z "$SWIFTBAR_DIR" ]; then
    SWIFTBAR_DIR="$DASHBOARD_DIR"
    echo "  ⚠️  SwiftBar plugin directory not detected."
    echo "     When you first open SwiftBar, set the plugin directory to:"
    echo ""
    echo "     📂 $DASHBOARD_DIR"
    echo ""
else
    # Symlink plugin to SwiftBar's directory
    SWIFTBAR_DIR=$(eval echo "$SWIFTBAR_DIR")
    if [ "$SWIFTBAR_DIR" != "$DASHBOARD_DIR" ]; then
        ln -sf "$DASHBOARD_DIR/claude-tokens.30s.py" "$SWIFTBAR_DIR/claude-tokens.30s.py"
        echo "  ✅ Plugin linked to SwiftBar: $SWIFTBAR_DIR"
    else
        echo "  ✅ Plugin already in SwiftBar directory"
    fi
fi

# ── Done ──
echo ""
echo "  ──────────────────────────────────────────"
echo "  ✅ Installation complete!"
echo ""
echo "  Next steps:"
echo "  1. Open SwiftBar (if not running)"
echo "  2. Edit token limits:  open $DASHBOARD_DIR/config.json"
echo "  3. Start using Claude Code — usage will be tracked automatically"
echo ""
echo "  Config options:"
echo "    tokenLimit         — your plan's token limit per window"
echo "    resetIntervalHours — hours until token limit resets"
echo ""
