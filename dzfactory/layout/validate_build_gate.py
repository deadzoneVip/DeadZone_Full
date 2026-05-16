from __future__ import annotations

from typing import Any

from dzfactory.layout.lock_manager import LOCK_SOURCES, lock_exists_for_manifest


def validate_build_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rom = manifest.get("rom", {})
    device = manifest.get("device", {})
    super_cfg = manifest.get("super", {})
    safety = manifest.get("safety", {})

    if not safety.get("layout_complete"):
        errors.append("layout_complete=false")
    if not device.get("codename") or not device.get("brand"):
        errors.append("device known check failed")
    if not rom.get("version"):
        errors.append("rom version known check failed")
    if not super_cfg.get("dynamic_partitions"):
        errors.append("dynamic partitions complete check failed")
    if not super_cfg.get("super_size"):
        errors.append("super_size missing")
    if not super_cfg.get("groups"):
        errors.append("groups missing")
    if not super_cfg.get("metadata_slots"):
        errors.append("metadata_slots missing")
    for safety_error in safety.get("errors", []):
        errors.append(f"safety error: {safety_error}")

    package_type = rom.get("package_type", "")
    source = super_cfg.get("layout_source", "")
    has_fastboot_lpdump = package_type == "fastboot_rom" and source in LOCK_SOURCES
    has_lock = lock_exists_for_manifest(manifest)
    if package_type == "recovery_payload_ota" and not has_lock:
        errors.append("recovery_payload_ota requires an existing layout lock")
    elif not has_lock and not has_fastboot_lpdump:
        errors.append("layout lock missing and package is not fastboot_rom with lpdump layout")

    return {"allowed": not errors, "errors": errors, "warnings": warnings, "lock_exists": has_lock}
