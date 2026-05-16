from __future__ import annotations

from typing import Any


def make_fastboot_manifest(input_resolved: dict[str, Any], rom_probe: dict[str, Any], fingerprint: dict[str, Any], super_layout: dict[str, Any], images: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "input": input_resolved,
        "rom_probe": rom_probe,
        "device": fingerprint,
        "rom": {
            "package_type": rom_probe.get("package_type", ""),
            "base_source": rom_probe.get("base_source", ""),
            "version": fingerprint.get("version", ""),
            "rom_family": fingerprint.get("rom_family", "unknown"),
            "rom_major": fingerprint.get("rom_major"),
            "android_version": fingerprint.get("android_version", ""),
            "region": fingerprint.get("region", ""),
        },
        "super": super_layout,
        "images": images,
        "safety": {
            "layout_complete": super_layout.get("safety", {}).get("layout_complete", False),
            "warnings": super_layout.get("safety", {}).get("warnings", []),
            "errors": super_layout.get("safety", {}).get("errors", []),
        },
    }
