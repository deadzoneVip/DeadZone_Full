from __future__ import annotations

from pathlib import Path
from typing import Any

DANGEROUS_FLAGS = ("fastboot -w", "--disable-verity", "--disable-verification")


def generate_fastboot_scripts(manifest: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    images = _image_map(manifest)
    upgrade = _upgrade_script(images)
    wipe = _wipe_script(images)
    upgrade_path = output_dir / "flash_upgrade.bat"
    wipe_path = output_dir / "flash_wipe.bat"
    upgrade_path.write_text(upgrade, encoding="utf-8")
    wipe_path.write_text(wipe, encoding="utf-8")
    return {"upgrade": str(upgrade_path), "wipe": str(wipe_path)}


def _image_map(manifest: dict[str, Any]) -> dict[str, str]:
    entries = manifest.get("super", {}).get("physical_images", [])
    mapping: dict[str, str] = {}
    for entry in entries:
        name = Path(entry).name
        if name.endswith(".img"):
            mapping[name[:-4]] = f"images\\{name}"
    return mapping


def _upgrade_script(images: dict[str, str]) -> str:
    lines = ["@echo off", "setlocal", "fastboot devices"]
    for partition in sorted(images):
        lines.append(f"fastboot flash {partition} {images[partition]}")
    lines.extend(["fastboot reboot", "endlocal", ""])
    script = "\r\n".join(lines)
    _assert_safe(script)
    return script


def _wipe_script(images: dict[str, str]) -> str:
    lines = ["@echo off", "setlocal", "fastboot devices", "fastboot erase metadata", "fastboot erase userdata"]
    for partition in sorted(images):
        lines.append(f"fastboot flash {partition} {images[partition]}")
    lines.extend(["fastboot reboot", "endlocal", ""])
    script = "\r\n".join(lines)
    _assert_safe(script)
    return script


def _assert_safe(script: str) -> None:
    lowered = script.lower()
    for flag in DANGEROUS_FLAGS:
        if flag in lowered:
            raise ValueError(f"dangerous fastboot flag generated: {flag}")
