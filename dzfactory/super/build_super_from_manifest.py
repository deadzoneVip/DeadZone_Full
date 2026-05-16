from __future__ import annotations

from pathlib import Path
from typing import Any


def lpmake_preview(manifest: dict[str, Any]) -> str:
    super_cfg = manifest.get("super", {})
    args = ["lpmake"]
    if super_cfg.get("metadata_size"):
        args += ["--metadata-size", str(super_cfg["metadata_size"])]
    if super_cfg.get("metadata_slots"):
        args += ["--metadata-slots", str(super_cfg["metadata_slots"])]
    if super_cfg.get("super_size"):
        args += ["--device", f"super:{super_cfg['super_size']}"]
    for group in super_cfg.get("groups", []):
        if group.get("name") and group.get("maximum_size") is not None:
            args += ["--group", f"{group['name']}:{group['maximum_size']}"]
    for part in super_cfg.get("dynamic_partitions", []):
        name = part.get("name")
        group = part.get("group", "")
        size = part.get("size") or 0
        if name:
            args += ["--partition", f"{name}:readonly:{size}:{group}", "--image", f"{name}=output/images/{name}.img"]
    if super_cfg.get("output_format") == "sparse":
        args.append("--sparse")
    args += ["--output", "output/images/super.img"]
    return " \\\n  ".join(args) + "\n"


def write_lpmake_preview(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lpmake_preview(manifest), encoding="utf-8")
