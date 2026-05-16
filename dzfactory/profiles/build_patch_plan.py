from __future__ import annotations

from typing import Any


PATCH_SETS = [
    {
        "id": "hyperos3_mtk_zircon_performance_props",
        "description": "Performance property patch set for zircon MTK HyperOS 3 dry-run planning.",
        "profiles": ["DeadZone_Gaming", "DeadZone_Legend", "DeadZone_EPiC"],
        "variants": ["performance", "extreme"],
        "device": ["zircon"],
        "soc_vendor": ["mtk"],
        "rom_family": ["hyperos"],
        "rom_major": [3],
        "actions": [
            {"type": "property_overlay", "target": "system", "key": "persist.deadzone.profile", "value": "performance"}
        ],
    },
    {
        "id": "hyperos_balanced_baseline",
        "description": "Balanced declarative baseline for HyperOS builds.",
        "profiles": ["DeadZone_Gaming", "DeadZone_Legend", "DeadZone_EPiC"],
        "variants": ["lite", "balanced", "performance", "extreme", "clean"],
        "device": ["*"],
        "soc_vendor": ["mtk", "qcom"],
        "rom_family": ["hyperos"],
        "rom_major": ["*"],
        "actions": [
            {"type": "metadata_note", "target": "manifest", "key": "deadzone.profile.enabled", "value": "true"}
        ],
    },
]


def build_patch_plan(profile: dict[str, Any], manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or {}
    selected = [_strip_matchers(item) for item in PATCH_SETS if _matches(item, profile, manifest)]
    return {
        "schema_version": 1,
        "profile": profile.get("name", ""),
        "variant": profile.get("variant", "balanced"),
        "patch_level": profile.get("patch_level", ""),
        "mode": "dry_run",
        "selected_patch_sets": selected,
        "actions": [action for patch_set in selected for action in patch_set.get("actions", [])],
        "status": "dry_run_only",
        "notes": ["Factory v2 profiles are declarative and do not modify ROM images yet"],
    }


def _matches(patch_set: dict[str, Any], profile: dict[str, Any], manifest: dict[str, Any]) -> bool:
    rom = manifest.get("rom", {})
    device = manifest.get("device", {})
    checks = {
        "profiles": profile.get("name", ""),
        "variants": profile.get("variant", "balanced"),
        "device": device.get("codename", ""),
        "soc_vendor": device.get("soc_vendor", ""),
        "rom_family": rom.get("rom_family", ""),
        "rom_major": rom.get("rom_major"),
    }
    return all(_value_matches(patch_set.get(key, ["*"]), value) for key, value in checks.items())


def _value_matches(allowed: list[Any], value: Any) -> bool:
    return "*" in allowed or value in allowed


def _strip_matchers(patch_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": patch_set["id"],
        "description": patch_set["description"],
        "actions": patch_set.get("actions", []),
    }
