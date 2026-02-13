#!/usr/bin/env python3
"""Reset the token usage counter."""

import json
from datetime import datetime
from pathlib import Path

USAGE_FILE = Path.home() / ".claude" / "dashboard" / "usage.json"

usage = {
    "currentWindow": {
        "startTime": datetime.now().isoformat(),
        "tokensUsed": 0,
        "interactionCount": 0,
    },
    "sessionSizes": {},
}

USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(USAGE_FILE, "w") as f:
    json.dump(usage, f, indent=2, default=str)
