from __future__ import annotations

from typing import Any


def validate_manifest(manifest: dict[str, Any], require_complete_layout: bool = False) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "rom", "device", "super", "profile", "safety"):
        if key not in manifest:
            errors.append(f"missing required key: {key}")
    if manifest.get("schema_version") != 1:
        errors.append("unsupported schema_version")
    safety = manifest.get("safety", {})
    if require_complete_layout and not safety.get("layout_complete"):
        errors.append("layout_complete=false; refusing Factory v2 build")
    errors.extend(safety.get("errors", []))
    return errors
