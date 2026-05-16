from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from dzfactory.build.build_gate import validate_fastboot_build_gate
from dzfactory.build.build_manifest import make_fastboot_manifest
from dzfactory.common.jsonio import write_json
from dzfactory.common.paths import final_dir, images_dir, logs_dir, manifest_dir, output_dir
from dzfactory.devices.device_database import show_device
from dzfactory.fastboot.image_collector import collect_physical_images, extract_image
from dzfactory.fastboot.package_inspector import inspect_package
from dzfactory.fastboot.script_generator import generate_windows_scripts
from dzfactory.fastboot.zip_packager import package_fastboot_zip
from dzfactory.fastboot.zip_validator import validate_fastboot_zip
from dzfactory.probe.fingerprint_device import fingerprint_device as legacy_fingerprint
from dzfactory.sources.input_resolver import resolve_input
from dzfactory.super.read_super_layout import read_super_layout
from dzfactory.super.rebuild_super import rebuild_super
from dzfactory.super.unpack_super import unpack_super
from dzfactory.super.validate_super_roundtrip import validate_super_roundtrip


def fingerprint_from_probe(probe: dict[str, Any], device_hint: str = "") -> dict[str, Any]:
    filename = probe.get("filename", "")
    codename = device_hint if device_hint and device_hint != "auto" else _codename_from_filename(filename)
    db = show_device(codename) if codename else {}
    legacy = legacy_fingerprint(codename, {"metadata": {"codename": codename}})
    version = _version(filename)
    rom_family = "hyperos" if version.startswith("OS") else "miui" if version.startswith("V") else "unknown"
    major_match = re.match(r"(?:OS|V)(\d+)", version)
    build_code = version.split(".")[-1] if version else ""
    region_code = build_code[3:5] if len(build_code) >= 5 else ""
    region = {"CN": "china", "MI": "global", "EU": "europe", "IN": "india", "ID": "indonesia", "RU": "russia", "TR": "turkey", "TW": "taiwan"}.get(region_code, region_code.lower())
    soc_vendor = db.get("soc_vendor") or legacy.get("soc_vendor") or "unknown"
    if codename == "zircon":
        soc_vendor = "mtk"
    if codename == "garnet":
        soc_vendor = "qcom"
    confidence = "high" if db and version else "medium" if codename else "low"
    return {
        "codename": codename,
        "display_name": db.get("display_name") or legacy.get("display_name", ""),
        "brand": "xiaomi",
        "soc_vendor": soc_vendor,
        "soc_name": db.get("soc_name", ""),
        "rom_family": rom_family,
        "rom_major": int(major_match.group(1)) if major_match else None,
        "android_version": _android_version(filename),
        "region": region,
        "version": version,
        "source_confidence": confidence,
        "warnings": [] if soc_vendor != "unknown" else ["soc_vendor unknown"],
        "errors": [],
    }


def run_fastboot_build(rom: str, device: str, profile: str, output: str, allow_unknown_device: bool = False) -> dict[str, Any]:
    resolved = resolve_input(rom)
    write_json(manifest_dir() / "input_resolved.json", resolved)
    if resolved["errors"]:
        gate = {"status": "fail", "errors": resolved["errors"], "warnings": []}
        write_json(logs_dir() / "build_gate.json", gate)
        return {"status": "fail", "gate": gate}
    probe = inspect_package(resolved["local_path"], device)
    write_json(manifest_dir() / "rom_probe.json", probe)
    fingerprint = fingerprint_from_probe(probe, device)
    write_json(manifest_dir() / "device_fingerprint.json", fingerprint)
    super_src = extract_image(resolved["local_path"], "super.img", output_dir() / "probe" / "super.img")
    if not super_src:
        gate = {"status": "fail", "errors": ["super.img not found"], "warnings": []}
        write_json(logs_dir() / "build_gate.json", gate)
        return {"status": "fail", "gate": gate}
    layout = read_super_layout(str(super_src))
    unpack_report = unpack_super(str(super_src))
    rebuild_report = rebuild_super(str(manifest_dir() / "super_layout.json"), str(manifest_dir() / "unpacked_super_images.json"))
    roundtrip = validate_super_roundtrip(str(super_src), rebuild_report["output"])
    physical_entries = list(probe.get("physical_images", []))
    collected = collect_physical_images(resolved["local_path"], physical_entries, output_dir() / "fastboot_images")
    rebuilt_super = Path(rebuild_report["output"])
    if rebuilt_super.exists():
        super_copy = images_dir() / "super.img"
        if rebuilt_super.resolve() != super_copy.resolve():
            shutil.copyfile(rebuilt_super, super_copy)
        collected = [item for item in collected if item["partition"] != "super"]
        collected.insert(0, {"partition": "super", "path": str(super_copy), "size": super_copy.stat().st_size, "sha256": ""})
    manifest = make_fastboot_manifest(resolved, probe, fingerprint, layout, collected)
    write_json(manifest_dir() / "build_manifest.json", manifest)
    scripts_dir = output_dir() / "fastboot_scripts"
    scripts = generate_windows_scripts(collected, scripts_dir)
    gate = validate_fastboot_build_gate(manifest, roundtrip, scripts, allow_unknown_device=allow_unknown_device)
    write_json(logs_dir() / "build_gate.json", gate)
    if gate["status"] != "pass":
        return {"status": "fail", "gate": gate}
    version = fingerprint.get("version") or "unknown"
    codename = fingerprint.get("codename") or "unknown"
    out_zip = Path(output) / f"DeadZone_{codename}_{version}_fastboot.zip"
    package_fastboot_zip(collected, scripts_dir, out_zip, Path("bin") / "windows")
    zip_report = validate_fastboot_zip(out_zip)
    gate = validate_fastboot_build_gate(manifest, roundtrip, scripts, zip_report, allow_unknown_device=allow_unknown_device)
    write_json(logs_dir() / "build_gate.json", gate)
    if gate["status"] != "pass":
        out_zip.unlink(missing_ok=True)
        return {"status": "fail", "gate": gate}
    return {"status": "pass", "zip": str(out_zip), "gate": gate}


def _codename_from_filename(filename: str) -> str:
    match = re.search(r"(^|[-_])([a-z0-9]+)[-_](?:images|global|eea|ota|fastboot)", filename, re.I)
    return match.group(2).lower() if match else ""


def _version(filename: str) -> str:
    match = re.search(r"(OS\d+(?:\.\d+){2,}\.[A-Z0-9]+|V\d+(?:\.\d+){2,}\.[A-Z0-9]+)", filename, re.I)
    return match.group(1).upper() if match else ""


def _android_version(filename: str) -> str:
    match = re.search(r"user[-_](\d+(?:\.\d+)*)", filename, re.I)
    return match.group(1) if match else ""
