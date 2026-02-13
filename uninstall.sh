#!/bin/bash
set -e

echo ""
echo "  ⚡ Claude Code Token Monitor — Uninstaller"
echo "  ──────────────────────────────────────────"
echo ""

DASHBOARD_DIR="$HOME/.claude/dashboard"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Remove hook from Claude Code settings
if [ -f "$SETTINGS_FILE" ]; then
    python3 << 'PYEOF'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
dashboard_dir = str(Path.home() / ".claude" / "dashboard")

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

hooks = settings.get("hooks", {})
stop_hooks = hooks.get("Stop", [])

# Filter out our hook
new_stop = []
for entry in stop_hooks:
    new_hooks = [
        h for h in entry.get("hooks", [])
        if dashboard_dir not in h.get("command", "")
    ]
    if new_hooks:
        entry["hooks"] = new_hooks
        new_stop.append(entry)

if new_stop:
    hooks["Stop"] = new_stop
else:
    hooks.pop("Stop", None)

if hooks:
    settings["hooks"] = hooks
else:
    settings.pop("hooks", None)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
PYEOF
    echo "  ✅ Hook removed from Claude Code settings"
fi

# Remove SwiftBar symlink
SWIFTBAR_DIR=$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || echo "")
if [ -n "$SWIFTBAR_DIR" ]; then
    SWIFTBAR_DIR=$(eval echo "$SWIFTBAR_DIR")
    rm -f "$SWIFTBAR_DIR/claude-tokens.30s.py"
    echo "  ✅ SwiftBar plugin removed"
fi

# Remove dashboard directory
rm -rf "$DASHBOARD_DIR"
echo "  ✅ Dashboard directory removed"

echo ""
echo "  ✅ Uninstall complete!"
echo ""
