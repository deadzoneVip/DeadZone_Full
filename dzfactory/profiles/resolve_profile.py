from __future__ import annotations

from typing import Any

VARIANTS = {"lite", "balanced", "performance", "extreme", "clean"}


def resolve_profile(name: str | None, variant: str | None = None) -> dict[str, Any]:
    profile_name = name or ""
    selected_variant = variant or "balanced"
    if selected_variant not in VARIANTS:
        selected_variant = "balanced"
    patch_level = "dry_run" if profile_name else "none"
    return {"name": profile_name, "variant": selected_variant, "patch_level": patch_level}
