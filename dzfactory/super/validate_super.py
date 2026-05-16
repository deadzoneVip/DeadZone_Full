from __future__ import annotations

from typing import Any


def has_enough_super_data(manifest: dict[str, Any]) -> bool:
    super_cfg = manifest.get("super", {})
    return bool(
        super_cfg.get("super_size")
        and super_cfg.get("metadata_size")
        and super_cfg.get("metadata_slots")
        and super_cfg.get("groups")
        and super_cfg.get("dynamic_partitions")
    )
