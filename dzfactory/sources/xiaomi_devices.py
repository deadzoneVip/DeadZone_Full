from __future__ import annotations

from typing import Any


def empty_xiaomi_devices_report() -> dict[str, Any]:
    return {
        "source": "xiaomi_devices",
        "status": "not_imported",
        "devices": [],
        "warnings": ["local XiaomiFirmwareUpdater xiaomi_devices database not provided"],
        "errors": [],
    }
