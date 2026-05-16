from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.devices.device_database import known_device


def validate_fastboot_build_gate(manifest: dict[str, Any], roundtrip_report: dict[str, Any], scripts_report: dict[str, Any], zip_report: dict[str, Any] | None = None, allow_unknown_device: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rom_probe = manifest.get("rom_probe", {})
    device = manifest.get("device", {})
    package_type = rom_probe.get("package_type")
    if package_type not in {"official_fastboot_rom", "xiaomi_eu_hybrid"}:
        errors.append("package_type must be official_fastboot_rom or xiaomi_eu_hybrid with super.img")
    if not rom_probe.get("has_super_img"):
        errors.append("package must expose images/super.img")
    if not manifest.get("safety", {}).get("layout_complete"):
        errors.append("super layout is incomplete")
    if roundtrip_report.get("status") != "pass":
        errors.append("super roundtrip validation did not pass")
    codename = device.get("codename", "")
    if not allow_unknown_device and not known_device(codename):
        errors.append(f"unknown device: {codename}")
    if device.get("soc_vendor") == "unknown":
        errors.append("soc_vendor is unknown")
    if scripts_report.get("status") != "pass":
        errors.extend(scripts_report.get("errors", []))
    if zip_report and zip_report.get("status") != "pass":
        errors.extend(zip_report.get("errors", []))
    return {"status": "pass" if not errors else "fail", "errors": errors, "warnings": warnings}
