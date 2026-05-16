from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import read_json, write_json
from dzfactory.common.paths import repo_root

LOCK_SOURCES = {"fastboot_super_img_lpdump", "fastboot_super_empty_img_lpdump"}


def lock_path_for(device: str, rom_version: str, brand: str = "xiaomi") -> Path:
    return repo_root() / "db" / "known_builds" / brand / device / f"{_safe_name(rom_version)}.lock.json"


def create_lock(manifest: dict[str, Any], device: str, allow_incomplete: bool = False) -> tuple[Path | None, list[str]]:
    errors = _lock_create_errors(manifest, device, allow_incomplete)
    if errors:
        return None, errors
    lock_path = lock_path_for(device, manifest["rom"]["version"], manifest.get("device", {}).get("brand") or "xiaomi")
    write_json(
        lock_path,
        {
            "schema_version": 1,
            "device": manifest.get("device", {}),
            "rom": manifest.get("rom", {}),
            "super": manifest.get("super", {}),
            "safety": manifest.get("safety", {}),
        },
    )
    return lock_path, []


def compare_lock(manifest: dict[str, Any], device: str) -> dict[str, Any]:
    rom_version = manifest.get("rom", {}).get("version", "")
    brand = manifest.get("device", {}).get("brand") or "xiaomi"
    path = lock_path_for(device, rom_version, brand)
    if not path.exists():
        return {"exists": False, "path": str(path), "matches": False, "errors": [f"missing layout lock: {path}"], "warnings": []}

    lock = read_json(path)
    errors: list[str] = []
    warnings: list[str] = []
    current_super = manifest.get("super", {})
    locked_super = lock.get("super", {})

    for key in ("super_size", "metadata_slots", "slot_mode"):
        if current_super.get(key) != locked_super.get(key):
            errors.append(f"lock mismatch {key}: manifest={current_super.get(key)} lock={locked_super.get(key)}")

    current_parts = {_base_partition_name(part.get("name", "")) for part in current_super.get("dynamic_partitions", [])}
    locked_parts = {_base_partition_name(part.get("name", "")) for part in locked_super.get("dynamic_partitions", [])}
    missing = sorted(locked_parts - current_parts)
    extra = sorted(current_parts - locked_parts)
    errors.extend([f"missing dynamic partition from lock: {name}" for name in missing if name])
    warnings.extend([f"extra dynamic partition not in lock: {name}" for name in extra if name])

    return {"exists": True, "path": str(path), "matches": not errors, "errors": errors, "warnings": warnings}


def lock_exists_for_manifest(manifest: dict[str, Any]) -> bool:
    device = manifest.get("device", {}).get("codename", "")
    version = manifest.get("rom", {}).get("version", "")
    brand = manifest.get("device", {}).get("brand") or "xiaomi"
    return bool(device and version and lock_path_for(device, version, brand).exists())


def _lock_create_errors(manifest: dict[str, Any], device: str, allow_incomplete: bool) -> list[str]:
    super_cfg = manifest.get("super", {})
    safety = manifest.get("safety", {})
    errors: list[str] = []
    if device != manifest.get("device", {}).get("codename"):
        errors.append("lock device does not match manifest device")
    if device != "zircon":
        errors.append("layout lock creation is currently zircon-first")
    if not manifest.get("rom", {}).get("version"):
        errors.append("rom version is required for layout lock")
    if super_cfg.get("layout_source") not in LOCK_SOURCES:
        errors.append("layout lock requires lpdump from super.img or super_empty.img")
    if not super_cfg.get("dynamic_partitions"):
        errors.append("layout lock requires dynamic_partitions")
    if not safety.get("layout_complete") and not allow_incomplete:
        errors.append("layout incomplete; pass --allow-incomplete to force a diagnostic lock")
    return errors


def _base_partition_name(name: str) -> str:
    return re.sub(r"_[ab]$", "", name)


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "unknown"
