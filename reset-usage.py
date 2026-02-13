#!/usr/bin/env python3
"""Reset the token usage log."""

import json
from pathlib import Path

USAGE_FILE = Path.home() / ".claude" / "dashboard" / "usage.json"

usage = {"tokenLog": [], "sessionLines": {}}

USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(USAGE_FILE, "w") as f:
    json.dump(usage, f, indent=2)
