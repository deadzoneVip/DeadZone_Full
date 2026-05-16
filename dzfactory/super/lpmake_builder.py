from __future__ import annotations

from pathlib import Path
from typing import Any


def build_lpmake_command(layout: dict[str, Any], images_report: dict[str, Any], output_super: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    image_map = {item["partition"]: item["path"] for item in images_report.get("images", [])}
    cmd = ["lpmake", "--metadata-slots", str(layout["metadata_slots"]), "--device", f"super:{layout['super_size']}"]
    if layout.get("metadata_size"):
        cmd += ["--metadata-size", str(layout["metadata_size"])]
    for group in layout.get("groups", []):
        cmd += ["--group", f"{group['name']}:{group['size']}"]
    for part in layout.get("dynamic_partitions", []):
        name = part["name"]
        size = int(part.get("size") or 0)
        group = part.get("group", "")
        cmd += ["--partition", f"{name}:readonly:{size}:{group}"]
        if size > 0:
            image_path = image_map.get(name)
            if not image_path:
                errors.append(f"missing image for partition: {name}")
            else:
                cmd += ["--image", f"{name}={image_path}"]
    cmd += ["--sparse", "--output", str(output_super)]
    return cmd, errors
