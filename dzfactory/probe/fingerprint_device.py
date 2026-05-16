from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.common.paths import config_dir


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key:
            data.setdefault(current_key, []).append(stripped[2:].strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current_key = key.strip()
            value = value.strip().strip('"').strip("'")
            data[current_key] = value if value else []
    return data


def load_device_config(codename: str) -> dict[str, Any]:
    if not codename:
        return {}
    for path in (config_dir() / "devices").glob(f"**/{codename}.yml"):
        return _parse_simple_yaml(path)
    return {}


def fingerprint_device(device_hint: str | None, rom_probe: dict[str, Any]) -> dict[str, Any]:
    metadata = rom_probe.get("metadata", {})
    codename = device_hint or metadata.get("codename") or ""
    cfg = load_device_config(codename)
    return {
        "codename": codename,
        "brand": cfg.get("brand", ""),
        "display_name": cfg.get("display_name", ""),
        "soc_vendor": cfg.get("soc_vendor", ""),
        "family_hint": cfg.get("family_hint", ""),
        "layout_policy": cfg.get("layout_policy", "detect") if cfg else "detect",
        "safety": cfg.get("safety", []),
        "config_found": bool(cfg),
    }
