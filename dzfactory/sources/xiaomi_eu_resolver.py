from __future__ import annotations

from typing import Any

from dzfactory.fastboot.package_inspector import inspect_package
from dzfactory.sources.input_resolver import resolve_input


def inspect_xiaomi_eu(rom: str) -> dict[str, Any]:
    resolved = resolve_input(rom)
    if resolved["errors"]:
        return {"input": resolved, "package_type": "unknown", "warnings": [], "errors": resolved["errors"]}
    probe = inspect_package(resolved["local_path"])
    probe["input"] = resolved
    if probe["package_type"] != "xiaomi_eu_hybrid":
        probe.setdefault("warnings", []).append("package does not look like Xiaomi.eu hybrid ROM")
    return probe
