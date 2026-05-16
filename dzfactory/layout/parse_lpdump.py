from __future__ import annotations

import re
from typing import Any


def parse_lpdump_text(text: str) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    partitions: list[dict[str, Any]] = []
    current_partition: dict[str, Any] | None = None
    super_size = None
    metadata_size = None
    metadata_slots = None
    section = ""
    current_group: dict[str, Any] | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("partition table"):
            section = "partition"
            current_partition = None
            current_group = None
            continue
        if lower.startswith("group table"):
            section = "group"
            current_partition = None
            current_group = None
            continue
        if lower.startswith("block device table"):
            section = "block_device"
            current_partition = None
            current_group = None
            continue
        if set(line) <= {"-"}:
            continue
        if lower.startswith(("metadata max size:", "metadata size:")):
            metadata_size = _int_tail(line)
        elif lower.startswith(("metadata slot count:", "metadata slots:")):
            metadata_slots = _int_tail(line)
        elif lower.startswith(("super partition size:", "super size:", "block device size:")):
            super_size = _int_tail(line)
        elif lower.startswith("name:") and section == "block_device":
            continue
        elif lower.startswith("size:") and section == "block_device":
            super_size = _int_tail(line)
        elif lower.startswith("name:") and section == "group":
            name = line.split(":", 1)[1].strip()
            current_group = groups.setdefault(name, {"name": name, "maximum_size": None})
        elif lower.startswith(("maximum size:", "max size:", "size:")) and section == "group" and current_group:
            current_group["maximum_size"] = _int_tail(line)
        elif lower.startswith("name:") and section == "partition":
            if current_partition:
                partitions.append(current_partition)
            current_partition = {"name": line.split(":", 1)[1].strip(), "group": "", "size": None, "readonly": None}
        elif lower.startswith("group:"):
            name = line.split(":", 1)[1].strip()
            if section == "partition" and current_partition:
                current_partition["group"] = name
            else:
                current_group = groups.setdefault(name, {"name": name, "maximum_size": None})
        elif lower.startswith(("maximum size:", "max size:", "size:")) and groups and not current_partition:
            groups[list(groups.keys())[-1]]["maximum_size"] = _int_tail(line)
        elif lower.startswith("partition name:"):
            if current_partition:
                partitions.append(current_partition)
            current_partition = {"name": line.split(":", 1)[1].strip(), "group": "", "size": None, "readonly": None}
        elif current_partition and lower.startswith(("group name:", "group:")):
            current_partition["group"] = line.split(":", 1)[1].strip()
        elif current_partition and lower.startswith("size:"):
            current_partition["size"] = _int_tail(line)
        elif current_partition and lower.startswith(("attributes:", "attribute:")):
            current_partition["readonly"] = "readonly" in lower

    if current_partition:
        partitions.append(current_partition)
    slot_mode, active_slot = _detect_slot_mode(partitions, metadata_slots)
    return {
        "super_size": super_size,
        "metadata_size": metadata_size,
        "metadata_slots": metadata_slots,
        "slot_mode": slot_mode,
        "active_slot": active_slot,
        "groups": list(groups.values()),
        "dynamic_partitions": partitions,
    }


def _int_tail(line: str) -> int | None:
    match = re.search(r"(\d+)", line.split(":", 1)[-1])
    return int(match.group(1)) if match else None


def _detect_slot_mode(partitions: list[dict[str, Any]], metadata_slots: int | None) -> tuple[str, str]:
    names = [part.get("name", "") for part in partitions]
    has_a = any(name.endswith("_a") for name in names)
    has_b = any(name.endswith("_b") for name in names)
    if has_a or has_b:
        return ("vab" if metadata_slots and metadata_slots >= 3 else "ab", "a" if has_a else "b")
    return "single", "a"
