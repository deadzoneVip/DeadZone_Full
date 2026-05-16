from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.common.paths import repo_root


def load_device_set(name: str) -> list[dict[str, Any]]:
    path = repo_root() / "configs" / "device_sets" / f"{name}.yml"
    if not path.exists():
        return []
    devices: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped == "devices:":
            continue
        if stripped.startswith("- "):
            if current:
                devices.append(current)
            value = stripped[2:].strip()
            if ":" in value:
                key, item = value.split(":", 1)
                current = {key.strip(): _parse_value(item.strip())}
            else:
                current = {"codename": value}
        elif current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = _parse_value(value.strip())
    if current:
        devices.append(current)
    return devices


def all_devices() -> list[dict[str, Any]]:
    result = []
    for name in ("os3_mtk", "os3_snapdragon"):
        for item in load_device_set(name):
            item = dict(item)
            item["set"] = name
            result.append(item)
    return result


def find_device(codename: str) -> dict[str, Any] | None:
    for item in all_devices():
        if item.get("codename") == codename:
            return item
    return None


def _parse_value(value: str) -> Any:
    value = value.strip().strip('"')
    if value.isdigit():
        return int(value)
    return value
