from __future__ import annotations

import re
from typing import Any


def parse_dynamic_op_list(text: str) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    partitions: dict[str, dict[str, Any]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s+", line)
        op = parts[0]
        if op in {"add_group", "resize_group"} and len(parts) >= 3:
            groups[parts[1]] = {"name": parts[1], "maximum_size": _to_int(parts[2])}
        elif op in {"add", "add_partition"} and len(parts) >= 3:
            name = parts[1]
            group = parts[2]
            partitions[name] = {"name": name, "group": group, "size": None}
        elif op == "resize" and len(parts) >= 3:
            partitions.setdefault(parts[1], {"name": parts[1], "group": "", "size": None})["size"] = _to_int(parts[2])
    return {"groups": list(groups.values()), "dynamic_partitions": list(partitions.values())}


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None
