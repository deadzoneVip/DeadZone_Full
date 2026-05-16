from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import write_json
from dzfactory.common.paths import logs_dir

DANGEROUS = ("fastboot -w", "--disable-verity", "--disable-verification")


def generate_windows_scripts(images: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    image_names = sorted({Path(item["path"]).name for item in images if Path(item["path"]).suffix == ".img"})
    upgrade = _script(image_names, format_data=False, format_only=False)
    install_format = _script(image_names, format_data=True, format_only=False)
    format_only = _script([], format_data=True, format_only=True)
    scripts = {
        "windows_install_upgrade.bat": upgrade,
        "windows_install_and_format_data.bat": install_format,
        "windows_format_data_only.bat": format_only,
    }
    errors: list[str] = []
    written = []
    for name, text in scripts.items():
        errors.extend(_safety_errors(text))
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(str(path))
    report = {"status": "pass" if not errors else "fail", "scripts": written, "images": image_names, "errors": errors, "warnings": []}
    write_json(logs_dir() / "generated_scripts_manifest.json", report)
    return report


def _script(image_names: list[str], format_data: bool, format_only: bool) -> str:
    lines = ["@echo off", "setlocal", "fastboot devices"]
    if not format_only:
        ordered = ["super.img"] + [name for name in image_names if name != "super.img"]
        for name in ordered:
            if name in image_names:
                lines.append(f"fastboot flash {name[:-4]} images\\{name}")
    if format_data:
        lines.append("fastboot erase metadata")
        lines.append("fastboot erase userdata")
    if not format_only:
        lines.append("fastboot reboot")
    lines.append("endlocal")
    return "\n".join(lines) + "\n"


def _safety_errors(text: str) -> list[str]:
    lowered = text.lower()
    return [f"dangerous fastboot token: {token}" for token in DANGEROUS if token in lowered]
