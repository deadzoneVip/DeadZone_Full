from __future__ import annotations

from typing import Any


def build_manifest(rom_probe: dict[str, Any], device_fp: dict[str, Any], super_layout: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    meta = rom_probe.get("metadata", {})
    return {
        "schema_version": 1,
        "rom": {
            "source": rom_probe.get("source", ""),
            "package_type": rom_probe.get("package_type", ""),
            "version": meta.get("version", ""),
            "android_version": meta.get("android_version", ""),
            "region": meta.get("region", ""),
            "rom_family": meta.get("rom_family", ""),
            "rom_major": meta.get("rom_major"),
        },
        "device": {
            "codename": device_fp.get("codename", ""),
            "brand": device_fp.get("brand", ""),
            "soc_vendor": device_fp.get("soc_vendor", ""),
            "family_hint": device_fp.get("family_hint", ""),
        },
        "super": {
            "layout_source": super_layout.get("layout_source", ""),
            "super_image_format": super_layout.get("super_image_format", "unknown"),
            "super_size": super_layout.get("super_size"),
            "metadata_size": super_layout.get("metadata_size"),
            "metadata_slots": super_layout.get("metadata_slots"),
            "slot_mode": super_layout.get("slot_mode", ""),
            "active_slot": super_layout.get("active_slot", "a"),
            "output_format": super_layout.get("output_format", "sparse"),
            "groups": super_layout.get("groups", []),
            "dynamic_partitions": super_layout.get("dynamic_partitions", []),
            "physical_images": super_layout.get("physical_images", []),
        },
        "profile": {
            "name": profile.get("name", ""),
            "patch_level": profile.get("patch_level", ""),
        },
        "safety": {
            "layout_complete": bool(super_layout.get("safety", {}).get("layout_complete")),
            "warnings": super_layout.get("safety", {}).get("warnings", []),
            "errors": super_layout.get("safety", {}).get("errors", []),
        },
    }
