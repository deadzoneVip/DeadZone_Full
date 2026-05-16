from __future__ import annotations

import re
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from dzfactory.common.paths import logs_dir

IMAGE_NAMES = (
    "super.img",
    "super_empty.img",
    "boot.img",
    "init_boot.img",
    "vendor_boot.img",
    "dtbo.img",
    "vbmeta.img",
    "vbmeta_system.img",
    "vbmeta_vendor.img",
    "system.img",
    "product.img",
    "system_ext.img",
    "vendor.img",
    "vendor_dlkm.img",
    "system_dlkm.img",
    "odm.img",
    "odm_dlkm.img",
    "mi_ext.img",
    "logo.img",
)
FASTBOOT_SCRIPTS = (
    "flash_all.bat",
    "flash_all.sh",
    "windows_fastboot_first_install_with_data_format.bat",
    "windows_fastboot_update_rom.bat",
    "linux_fastboot_first_install_with_data_format.sh",
    "linux_fastboot_update_rom.sh",
)
DYNAMIC_CANDIDATES = {
    "system.img",
    "product.img",
    "system_ext.img",
    "vendor.img",
    "vendor_dlkm.img",
    "system_dlkm.img",
    "odm.img",
    "odm_dlkm.img",
    "mi_ext.img",
}


def inspect_package(local_path: str, device_hint: str = "") -> dict[str, Any]:
    path = Path(local_path)
    warnings: list[str] = []
    errors: list[str] = []
    entries = _list_entries(path, warnings, errors)
    _write_entries(entries)
    keys = {_entry_key(entry) for entry in entries}
    physical = sorted([f"images/{name}" for name in IMAGE_NAMES if f"images/{name}" in keys])
    dynamic = sorted([f"images/{name}" for name in DYNAMIC_CANDIDATES if f"images/{name}" in keys])
    flash_scripts = sorted([script for script in FASTBOOT_SCRIPTS if script in keys])
    filename = path.name
    has_payload = "payload.bin" in keys
    has_fastboot = bool(flash_scripts)
    has_super = "images/super.img" in keys
    has_super_empty = "images/super_empty.img" in keys
    is_xiaomi_eu_name = bool(re.search(r"xiaomi\.eu|xiaomi_eu|hybrid", filename, re.I))
    has_xiaomi_eu_scripts = any(script.startswith(("windows_fastboot_", "linux_fastboot_")) for script in flash_scripts)

    if is_xiaomi_eu_name or has_xiaomi_eu_scripts or (has_payload and has_fastboot):
        package_type = "xiaomi_eu_hybrid"
        base_source = "xiaomi_eu"
    elif has_super and has_fastboot:
        package_type = "official_fastboot_rom"
        base_source = "official_fastboot"
    elif has_payload:
        package_type = "recovery_payload_ota"
        base_source = "official_ota"
    elif physical:
        package_type = "images_package"
        base_source = "unknown"
    else:
        package_type = "unknown"
        base_source = "unknown"

    return {
        "package_type": package_type,
        "base_source": base_source,
        "has_super_img": has_super,
        "has_super_empty_img": has_super_empty,
        "has_payload_bin": has_payload,
        "has_fastboot_scripts": has_fastboot,
        "physical_images": physical,
        "dynamic_image_candidates": dynamic,
        "flash_scripts": flash_scripts,
        "entries": entries,
        "filename": filename,
        "device_hint": device_hint,
        "warnings": warnings,
        "errors": errors,
    }


def _list_entries(path: Path, warnings: list[str], errors: list[str]) -> list[str]:
    if path.is_dir():
        return sorted(item.relative_to(path).as_posix() for item in path.rglob("*") if item.is_file())
    if not path.exists():
        errors.append(f"package path does not exist: {path}")
        return []
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                return sorted(zf.namelist())
        if tarfile.is_tarfile(path):
            with tarfile.open(path) as tf:
                return sorted(tf.getnames())
    except Exception as exc:
        errors.append(f"failed to list package entries: {exc}")
        return []
    warnings.append("unknown package format; entries unavailable")
    return []


def _entry_key(entry: str) -> str:
    lower = entry.replace("\\", "/").strip("/").lower()
    if "/images/" in lower:
        return "images/" + lower.rsplit("/images/", 1)[1]
    if lower.startswith("images/"):
        return lower
    return Path(lower).name


def _write_entries(entries: list[str]) -> None:
    logs_dir().mkdir(parents=True, exist_ok=True)
    (logs_dir() / "package_entries.txt").write_text("\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")
