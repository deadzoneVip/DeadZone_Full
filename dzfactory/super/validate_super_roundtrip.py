from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import write_json
from dzfactory.common.paths import logs_dir
from dzfactory.super.read_super_layout import read_super_layout


def validate_super_roundtrip(original: str, rebuilt: str) -> dict[str, Any]:
    checked: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    original_layout = read_super_layout(original, write_manifest=False)
    rebuilt_layout = read_super_layout(rebuilt, write_manifest=False) if Path(rebuilt).exists() else {"groups": [], "dynamic_partitions": [], "safety": {"errors": ["rebuilt super missing"]}}
    for key in ("super_size", "metadata_slots"):
        checked.append(key)
        if original_layout.get(key) != rebuilt_layout.get(key):
            errors.append(f"{key} mismatch")
    _compare_groups(original_layout, rebuilt_layout, errors, checked)
    _compare_partitions(original_layout, rebuilt_layout, errors, checked)
    for required in ("odm", "mi_ext", "vendor_dlkm", "system_dlkm", "odm_dlkm"):
        original_has = _has_base(original_layout, required)
        rebuilt_has = _has_base(rebuilt_layout, required)
        checked.append(f"{required} presence")
        if original_has and not rebuilt_has:
            errors.append(f"missing required partition after rebuild: {required}")
    report = {"status": "pass" if not errors else "fail", "checked": checked, "warnings": warnings, "errors": errors}
    write_json(logs_dir() / "super_roundtrip_report.json", report)
    return report


def _compare_groups(a: dict[str, Any], b: dict[str, Any], errors: list[str], checked: list[str]) -> None:
    ag = {g["name"]: g.get("size") for g in a.get("groups", [])}
    bg = {g["name"]: g.get("size") for g in b.get("groups", [])}
    checked.append("group names")
    checked.append("group sizes")
    if set(ag) != set(bg):
        errors.append("group names mismatch")
    for name in set(ag) & set(bg):
        if ag[name] != bg[name]:
            errors.append(f"group size mismatch: {name}")


def _compare_partitions(a: dict[str, Any], b: dict[str, Any], errors: list[str], checked: list[str]) -> None:
    ap = {p["name"]: p.get("size") for p in a.get("dynamic_partitions", [])}
    bp = {p["name"]: p.get("size") for p in b.get("dynamic_partitions", [])}
    checked.append("partition names")
    checked.append("partition sizes")
    if set(ap) != set(bp):
        errors.append("partition names mismatch")
    for name in set(ap) & set(bp):
        if ap[name] != bp[name]:
            errors.append(f"partition size mismatch: {name}")


def _has_base(layout: dict[str, Any], base: str) -> bool:
    return any(part.get("base_name") == base or part.get("name") == base for part in layout.get("dynamic_partitions", []))
