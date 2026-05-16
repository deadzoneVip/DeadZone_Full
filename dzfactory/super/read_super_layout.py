from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import write_json
from dzfactory.common.paths import logs_dir, manifest_dir, probe_dir
from dzfactory.common.shell import run_capture, which


def read_super_layout(super_path: str, write_manifest: bool = True) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    image = Path(super_path)
    text = ""
    if not image.exists():
        errors.append(f"super image does not exist: {image}")
    elif not which("lpdump"):
        errors.append("lpdump not available")
    else:
        rc, stdout, stderr = run_capture(["lpdump", str(image)], timeout=180)
        text = stdout
        if rc != 0 or not stdout.strip():
            if _looks_sparse(image) and which("simg2img"):
                raw = probe_dir() / "super.raw.img"
                conv_rc, _, conv_err = run_capture(["simg2img", str(image), str(raw)], timeout=600)
                if conv_rc == 0:
                    rc, stdout, stderr = run_capture(["lpdump", str(raw)], timeout=180)
                    text = stdout
                else:
                    errors.append(f"simg2img failed: {conv_err.strip()}")
            if rc != 0 or not stdout.strip():
                errors.append(f"lpdump failed: {stderr.strip()}")
        (logs_dir() / "lpdump_original_super.txt").write_text((stdout or "") + (stderr or ""), encoding="utf-8", errors="replace")
    layout = parse_lpdump_layout(text)
    layout["safety"]["warnings"].extend(warnings)
    layout["safety"]["errors"].extend(errors)
    _finalize_safety(layout)
    if write_manifest:
        write_json(manifest_dir() / "super_layout.json", layout)
    return layout


def parse_lpdump_layout(text: str) -> dict[str, Any]:
    super_size = None
    metadata_size = None
    metadata_slots = None
    groups: dict[str, dict[str, Any]] = {}
    partitions: list[dict[str, Any]] = []
    section = ""
    current_group = ""
    current_part: dict[str, Any] | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("metadata max size") or lower.startswith("metadata size"):
            metadata_size = _first_int(line)
        elif lower.startswith("metadata slot count") or lower.startswith("metadata slots"):
            metadata_slots = _first_int(line)
        elif lower.startswith("super partition size") or lower.startswith("super size"):
            super_size = _first_int(line)
        elif lower.startswith("block device table"):
            section = "block"
        elif lower.startswith("group table"):
            section = "group"
        elif lower.startswith("partition table"):
            section = "partition"
        elif set(line) <= {"-"}:
            continue
        elif section == "block" and lower.startswith("size:"):
            super_size = _first_int(line)
        elif section == "group" and lower.startswith("name:"):
            current_group = line.split(":", 1)[1].strip()
            groups[current_group] = {"name": current_group, "size": 0, "partitions": []}
        elif section == "group" and lower.startswith(("maximum size:", "max size:", "size:")) and current_group:
            groups[current_group]["size"] = _first_int(line) or 0
        elif section == "partition" and lower.startswith("name:"):
            if current_part:
                partitions.append(current_part)
            name = line.split(":", 1)[1].strip()
            current_part = {"name": name, "base_name": _base_name(name), "size": 0, "group": "", "attributes": []}
        elif section == "partition" and current_part and lower.startswith("group:"):
            current_part["group"] = line.split(":", 1)[1].strip()
        elif section == "partition" and current_part and lower.startswith("size:"):
            current_part["size"] = _first_int(line) or 0
        elif section == "partition" and current_part and lower.startswith("attributes:"):
            attrs = line.split(":", 1)[1].replace(",", " ").split()
            current_part["attributes"] = attrs
    if current_part:
        partitions.append(current_part)
    for part in partitions:
        group = groups.setdefault(part["group"], {"name": part["group"], "size": 0, "partitions": []})
        group["partitions"].append(part)
    slot_mode, active_slot = _slot_mode([part["name"] for part in partitions])
    layout = {
        "layout_source": "lpdump_super_img",
        "super_size": super_size,
        "metadata_size": metadata_size,
        "metadata_slots": metadata_slots,
        "slot_mode": slot_mode,
        "active_slot": active_slot,
        "output_format": "sparse",
        "groups": list(groups.values()),
        "dynamic_partitions": partitions,
        "safety": {"layout_complete": False, "warnings": [], "errors": []},
    }
    _finalize_safety(layout)
    return layout


def _finalize_safety(layout: dict[str, Any]) -> None:
    errors = layout["safety"]["errors"]
    if not layout.get("super_size"):
        errors.append("missing super_size")
    if not layout.get("metadata_slots"):
        errors.append("missing metadata_slots")
    if not layout.get("groups"):
        errors.append("missing groups")
    for group in layout.get("groups", []):
        if not group.get("name"):
            errors.append("missing group name")
        if not group.get("size"):
            errors.append(f"missing group size: {group.get('name', '')}")
    if not layout.get("dynamic_partitions"):
        errors.append("missing dynamic_partitions")
    layout["safety"]["errors"] = sorted(set(errors))
    layout["safety"]["layout_complete"] = not layout["safety"]["errors"]


def _looks_sparse(path: Path) -> bool:
    try:
        return path.read_bytes()[:4] == b"\x3a\xff\x26\xed"
    except OSError:
        return False


def _first_int(line: str) -> int | None:
    match = re.search(r"(\d+)", line)
    return int(match.group(1)) if match else None


def _base_name(name: str) -> str:
    return re.sub(r"_[ab]$", "", name)


def _slot_mode(names: list[str]) -> tuple[str, str]:
    has_a = any(name.endswith("_a") for name in names)
    has_b = any(name.endswith("_b") for name in names)
    if has_a or has_b:
        return ("vab" if has_a and has_b else "ab", "a" if has_a else "b")
    return "single", "a"
