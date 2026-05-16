from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_latest_updates(path: str) -> dict[str, Any]:
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    updates = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            updates.append({"key": key.strip(), "value": value.strip().strip('"')})
    if source.suffix.lower() == ".json":
        try:
            return {"source": str(source), "updates": json.loads(text)}
        except json.JSONDecodeError:
            pass
    return {"source": str(source), "updates": updates}
