from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.common.paths import logs_dir, probe_dir
from dzfactory.common.shell import run_capture, which
from dzfactory.layout.parse_dynamic_op_list import parse_dynamic_op_list
from dzfactory.layout.parse_lpdump import parse_lpdump_text


IMAGE_DYNAMIC_NAMES = {
    "system",
    "system_ext",
    "product",
    "vendor",
    "vendor_dlkm",
    "odm",
    "odm_dlkm",
    "mi_ext",
    "my_product",
    "system_dlkm",
}


def detect_super_layout(rom_probe: dict[str, Any], device_fp: dict[str, Any]) -> dict[str, Any]:
    warnings = list(rom_probe.get("warnings", []))
    errors = list(rom_probe.get("errors", []))
    groups: list[dict[str, Any]] = []
    partitions: list[dict[str, Any]] = []
    source = "none"
    super_image_format = "unknown"
    super_size = None
    metadata_size = None
    metadata_slots = None
    slot_mode = ""
    active_slot = "a"

    image_names = rom_probe.get("image_names", [])
    dynamic_names = sorted(
        {
            Path(name).stem
            for name in image_names
            if Path(name).suffix.lower() == ".img" and Path(name).stem in IMAGE_DYNAMIC_NAMES
        }
    )
    if dynamic_names:
        source = "image_names"
        partitions = [{"name": name, "group": "", "size": None} for name in dynamic_names]
        warnings.append("layout was inferred from image names only; group sizes are incomplete")

    contains = rom_probe.get("contains", {})
    op_list_text = rom_probe.get("dynamic_partitions_op_list", "")
    local_paths = rom_probe.get("local_paths", {})
    lpdump_result = _try_lpdump(local_paths.get("super.img") or "", "super", warnings)
    if lpdump_result.get("parsed"):
        source = "fastboot_super_img_lpdump"
        super_image_format = lpdump_result.get("image_format", "unknown")
        groups = lpdump_result.get("groups", [])
        partitions = lpdump_result.get("dynamic_partitions", [])
        super_size = lpdump_result.get("super_size")
        metadata_size = lpdump_result.get("metadata_size")
        metadata_slots = lpdump_result.get("metadata_slots")
        slot_mode = lpdump_result.get("slot_mode", "")
        active_slot = lpdump_result.get("active_slot", "a")
    elif contains.get("super.img"):
        source = "fastboot_super_img"
        if not local_paths.get("super.img"):
            warnings.append("super.img detected but was not available for lpdump extraction")

    if source != "fastboot_super_img_lpdump":
        empty_lpdump_result = _try_lpdump(local_paths.get("super_empty.img") or "", "super_empty", warnings)
        if empty_lpdump_result.get("parsed"):
            lpdump_result = empty_lpdump_result
            source = "fastboot_super_empty_img_lpdump"
            super_image_format = lpdump_result.get("image_format", "unknown")
            groups = lpdump_result.get("groups", [])
            partitions = lpdump_result.get("dynamic_partitions", [])
            super_size = lpdump_result.get("super_size")
            metadata_size = lpdump_result.get("metadata_size")
            metadata_slots = lpdump_result.get("metadata_slots")
            slot_mode = lpdump_result.get("slot_mode", "")
            active_slot = lpdump_result.get("active_slot", "a")
    if source not in {"fastboot_super_img_lpdump", "fastboot_super_empty_img_lpdump", "fastboot_super_img"} and contains.get("super_empty.img"):
        source = "fastboot_super_empty_img"
        if not local_paths.get("super_empty.img"):
            warnings.append("super_empty.img detected but was not available for lpdump extraction")
    elif not source.startswith("fastboot_super") and op_list_text:
        parsed = parse_dynamic_op_list(op_list_text)
        source = "dynamic_partitions_op_list"
        groups = parsed.get("groups", [])
        partitions = parsed.get("dynamic_partitions", [])
        slot_mode = _detect_slot_mode(partitions, metadata_slots)[0]
    elif not source.startswith("fastboot_super") and contains.get("dynamic_partitions_op_list"):
        source = "dynamic_partitions_op_list"
        warnings.append("dynamic_partitions_op_list detected but not extracted in detect-only package probe")
    elif not source.startswith("fastboot_super") and contains.get("payload.bin"):
        source = "payload_manifest_metadata"
        warnings.append("payload.bin detected; payload manifest parsing is a future Factory v2 step")

    names = {part["name"] for part in partitions}
    for required in ("odm", "mi_ext"):
        if f"{required}.img" in image_names and required not in names:
            errors.append(f"{required}.img exists but {required} is missing from dynamic_partitions")

    group_names = {group.get("name") for group in groups}
    soc_vendor = device_fp.get("soc_vendor", "")
    if device_fp.get("codename") == "zircon" and soc_vendor != "mtk":
        errors.append("zircon must resolve as soc_vendor=mtk")
    if soc_vendor == "mtk" and "qti_dynamic_partitions" in group_names and source not in {"fastboot_super_img_lpdump", "fastboot_super_empty_img_lpdump", "dynamic_partitions_op_list"}:
        errors.append("MTK device has qti_dynamic_partitions without lpdump/op_list confirmation")

    missing = []
    if not super_size:
        missing.append("missing super_size")
    if not metadata_slots:
        missing.append("missing metadata_slots")
    if not groups:
        missing.append("missing groups")
    if not partitions:
        missing.append("missing dynamic_partitions")
    errors.extend(missing)
    layout_complete = not missing

    return {
        "layout_source": source,
        "super_image_format": super_image_format,
        "super_size": super_size,
        "metadata_size": metadata_size,
        "metadata_slots": metadata_slots,
        "slot_mode": slot_mode,
        "active_slot": active_slot,
        "output_format": "sparse",
        "groups": groups,
        "dynamic_partitions": partitions,
        "physical_images": rom_probe.get("physical_images", []),
        "safety": {
            "layout_complete": layout_complete,
            "warnings": warnings,
            "errors": errors,
        },
    }


def _try_lpdump(image_path: str, label: str, warnings: list[str]) -> dict[str, Any]:
    if not image_path:
        return {}
    if not which("lpdump"):
        warnings.append("lpdump unavailable; cannot confirm super metadata")
        return {}
    image = Path(image_path)
    image_format = _image_format(image)
    rc, stdout, stderr = run_capture(["lpdump", str(image)])
    log_path = logs_dir() / f"lpdump_{label}.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(stdout + stderr, encoding="utf-8", errors="replace")
    if rc == 0 and stdout.strip():
        parsed = parse_lpdump_text(stdout)
        parsed["parsed"] = True
        parsed["image_format"] = image_format
        return parsed

    if image_format == "sparse" and which("simg2img"):
        raw_path = probe_dir() / f"{label}.raw.img"
        raw_rc, _raw_stdout, raw_stderr = run_capture(["simg2img", str(image), str(raw_path)])
        if raw_rc == 0 and raw_path.exists():
            rc, stdout, stderr = run_capture(["lpdump", str(raw_path)])
            log_path.write_text(stdout + stderr, encoding="utf-8", errors="replace")
            if rc == 0 and stdout.strip():
                parsed = parse_lpdump_text(stdout)
                parsed["parsed"] = True
                parsed["image_format"] = "sparse"
                return parsed
        else:
            warnings.append(f"simg2img failed for {image.name}: {raw_stderr.strip()}")
    warnings.append(f"lpdump failed for {image.name}; cannot confirm super metadata")
    return {"parsed": False, "image_format": image_format}


def _image_format(path: Path) -> str:
    try:
        magic = path.read_bytes()[:4]
    except OSError:
        return "unknown"
    if magic == b"\x3a\xff\x26\xed":
        return "sparse"
    return "raw" if magic else "unknown"


def _detect_slot_mode(partitions: list[dict[str, Any]], metadata_slots: int | None) -> tuple[str, str]:
    names = [part.get("name", "") for part in partitions]
    has_a = any(name.endswith("_a") for name in names)
    has_b = any(name.endswith("_b") for name in names)
    if has_a or has_b:
        return ("vab" if metadata_slots and metadata_slots >= 3 else "ab", "a" if has_a else "b")
    return "single", "a"
