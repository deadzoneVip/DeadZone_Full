from __future__ import annotations

from typing import Any

from dzfactory.devices.device_sets import all_devices, find_device, load_device_set


def list_devices(set_name: str) -> dict[str, Any]:
    return {"set": set_name, "devices": load_device_set(set_name)}


def show_device(codename: str) -> dict[str, Any]:
    device = find_device(codename)
    return device or {"codename": codename, "errors": ["device not found"]}


def known_device(codename: str) -> bool:
    return find_device(codename) is not None


def import_report() -> dict[str, Any]:
    return {"devices": all_devices(), "count": len(all_devices()), "source": "configs/device_sets"}
