from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dzfactory.common.jsonio import read_json, write_json
from dzfactory.common.logger import info
from dzfactory.common.paths import ensure_output_dirs, logs_dir, manifest_dir, updates_dir
from dzfactory.build.fastboot_build import fingerprint_from_probe, run_fastboot_build
from dzfactory.devices.device_database import import_report, list_devices, show_device
from dzfactory.fastboot.package_inspector import inspect_package
from dzfactory.layout.build_manifest import build_manifest
from dzfactory.layout.detect_super_layout import detect_super_layout
from dzfactory.layout.lock_manager import compare_lock, create_lock
from dzfactory.layout.validate_build_gate import validate_build_gate
from dzfactory.layout.validate_manifest import validate_manifest
from dzfactory.package.script_generator import generate_fastboot_scripts
from dzfactory.probe.fingerprint_device import fingerprint_device
from dzfactory.probe.package_probe import probe_package
from dzfactory.profiles.build_patch_plan import build_patch_plan
from dzfactory.profiles.resolve_profile import resolve_profile
from dzfactory.resolvers.resolve_input import resolve_rom_input
from dzfactory.sources.input_resolver import resolve_input
from dzfactory.sources.xfu_update_tracker import parse_latest_updates
from dzfactory.sources.xiaomi_eu_resolver import inspect_xiaomi_eu
from dzfactory.super.read_super_layout import read_super_layout
from dzfactory.super.rebuild_super import rebuild_super
from dzfactory.super.unpack_super import unpack_super
from dzfactory.super.validate_super_roundtrip import validate_super_roundtrip
from dzfactory.super.build_super_from_manifest import write_lpmake_preview
from dzfactory.super.validate_super import has_enough_super_data


def cmd_detect(args: argparse.Namespace) -> int:
    _run_detect_pipeline(args.rom, args.device_hint, args.profile, args.variant, download=True)
    info(f"wrote Factory v2 manifests to {manifest_dir()}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    ensure_output_dirs()
    if args.dry_run:
        if not args.rom:
            print("[dzfactory][error] build --dry-run requires --rom", file=sys.stderr)
            return 2
        manifest = _run_detect_pipeline(args.rom, args.device_hint, args.profile, args.variant, download=True)
        lock_report = _write_lock_compare_if_possible(manifest)
        gate = validate_build_gate(manifest)
        write_json(manifest_dir() / "build_gate.json", gate)
        if has_enough_super_data(manifest):
            write_lpmake_preview(manifest, logs_dir() / "lpmake_command.txt")
        else:
            (logs_dir() / "lpmake_command.txt").write_text("manifest incomplete; lpmake preview unavailable\n", encoding="utf-8")
        generate_fastboot_scripts(manifest, logs_dir() / "fastboot_scripts")
        info("dry-run generated manifests, gate report, patch plan, lpmake preview, and fastboot script previews")
        if not gate["allowed"]:
            for err in gate["errors"]:
                print(f"[dzfactory][error] {err}", file=sys.stderr)
            if lock_report and lock_report.get("errors"):
                for err in lock_report["errors"]:
                    print(f"[dzfactory][lock] {err}", file=sys.stderr)
            return 2
        return 0

    if not args.manifest:
        print("[dzfactory][error] build requires --manifest unless --dry-run --rom is used", file=sys.stderr)
        return 2
    manifest_path = Path(args.manifest)
    manifest = read_json(manifest_path)
    errors = validate_manifest(manifest, require_complete_layout=True)
    gate = validate_build_gate(manifest)
    write_json(manifest_dir() / "build_gate.json", gate)
    all_errors = errors + gate["errors"]
    if all_errors:
        for err in all_errors:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    if has_enough_super_data(manifest):
        write_lpmake_preview(manifest, logs_dir() / "lpmake_command.txt")
        info(f"wrote lpmake preview to {logs_dir() / 'lpmake_command.txt'}")
    else:
        info("manifest is layout-complete but lacks enough size data for an lpmake preview")
    return 0


def cmd_lock_create(args: argparse.Namespace) -> int:
    manifest = read_json(Path(args.manifest))
    path, errors = create_lock(manifest, args.device, args.allow_incomplete)
    if errors:
        for err in errors:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    info(f"wrote layout lock to {path}")
    return 0


def cmd_lock_compare(args: argparse.Namespace) -> int:
    manifest = read_json(Path(args.manifest))
    report = compare_lock(manifest, args.device)
    write_json(manifest_dir() / "lock_compare.json", report)
    if report.get("errors"):
        for err in report["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    info(f"layout lock comparison passed: {report.get('path')}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    ensure_output_dirs()
    resolved = resolve_input(args.rom)
    write_json(manifest_dir() / "input_resolved.json", resolved)
    if resolved["errors"]:
        for err in resolved["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    info(f"resolved input to {resolved['local_path']}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    ensure_output_dirs()
    resolved = resolve_input(args.rom)
    write_json(manifest_dir() / "input_resolved.json", resolved)
    if resolved["errors"]:
        for err in resolved["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    probe = inspect_package(resolved["local_path"], args.device_hint)
    fingerprint = fingerprint_from_probe(probe, args.device_hint)
    write_json(manifest_dir() / "rom_probe.json", probe)
    write_json(manifest_dir() / "device_fingerprint.json", fingerprint)
    info(f"package_type={probe['package_type']}")
    return 0


def cmd_devices_list(args: argparse.Namespace) -> int:
    report = list_devices(args.set)
    print("\n".join(f"{item.get('codename')} {item.get('display_name', '')}".rstrip() for item in report["devices"]))
    return 0


def cmd_devices_show(args: argparse.Namespace) -> int:
    report = show_device(args.device)
    write_json(manifest_dir() / "device_show.json", report)
    print(report)
    return 0


def cmd_super_read(args: argparse.Namespace) -> int:
    layout = read_super_layout(args.super)
    if layout["safety"]["errors"]:
        for err in layout["safety"]["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    return 0


def cmd_super_unpack(args: argparse.Namespace) -> int:
    report = unpack_super(args.super)
    if report["errors"]:
        for err in report["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    return 0


def cmd_super_rebuild(args: argparse.Namespace) -> int:
    report = rebuild_super(args.layout, args.images)
    if report["errors"]:
        for err in report["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    return 0


def cmd_super_validate(args: argparse.Namespace) -> int:
    report = validate_super_roundtrip(args.original, args.rebuilt)
    if report["status"] != "pass":
        for err in report["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    return 0


def cmd_super_roundtrip(args: argparse.Namespace) -> int:
    layout = read_super_layout(args.super)
    if not layout["safety"]["layout_complete"]:
        for err in layout["safety"]["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    unpack = unpack_super(args.super)
    if unpack["errors"]:
        for err in unpack["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    rebuild = rebuild_super(str(manifest_dir() / "super_layout.json"), str(manifest_dir() / "unpacked_super_images.json"))
    if rebuild["errors"]:
        for err in rebuild["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    report = validate_super_roundtrip(args.super, rebuild["output"])
    if report["status"] != "pass":
        for err in report["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    return 0


def cmd_fastboot_build(args: argparse.Namespace) -> int:
    result = run_fastboot_build(args.rom, args.device, args.profile, args.output, args.allow_unknown_device)
    if result["status"] != "pass":
        for err in result.get("gate", {}).get("errors", []):
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    info(f"fastboot package written to {result['zip']}")
    return 0


def cmd_xiaomi_eu_inspect(args: argparse.Namespace) -> int:
    probe = inspect_xiaomi_eu(args.rom)
    write_json(manifest_dir() / "xiaomi_eu_probe.json", probe)
    if probe.get("errors"):
        for err in probe["errors"]:
            print(f"[dzfactory][error] {err}", file=sys.stderr)
        return 2
    return 0


def cmd_xfu_devices_import(args: argparse.Namespace) -> int:
    report = import_report()
    write_json(updates_dir() / "xfu_devices.json", report)
    info(f"wrote {updates_dir() / 'xfu_devices.json'}")
    return 0


def cmd_xfu_updates_parse(args: argparse.Namespace) -> int:
    report = parse_latest_updates(args.file)
    write_json(updates_dir() / "xfu_latest_updates.json", report)
    info(f"wrote {updates_dir() / 'xfu_latest_updates.json'}")
    return 0


def _run_detect_pipeline(rom: str, device_hint: str = "", profile_name: str = "", variant: str = "balanced", download: bool = True) -> dict:
    ensure_output_dirs()
    resolved = resolve_rom_input(rom, download=download)
    write_json(manifest_dir() / "input_resolved.json", resolved)
    rom_probe = probe_package(resolved)
    device_fp = fingerprint_device(device_hint, rom_probe)
    profile = resolve_profile(profile_name, variant)
    super_layout = detect_super_layout(rom_probe, device_fp)
    manifest = build_manifest(rom_probe, device_fp, super_layout, profile)
    patch_plan = build_patch_plan(profile, manifest)

    write_json(manifest_dir() / "rom_probe.json", rom_probe)
    write_json(manifest_dir() / "device_fingerprint.json", device_fp)
    write_json(manifest_dir() / "super_layout.json", super_layout)
    write_json(manifest_dir() / "build_manifest.json", manifest)
    write_json(manifest_dir() / "patch_plan.json", patch_plan)
    _write_detect_summary(manifest)
    return manifest


def _write_lock_compare_if_possible(manifest: dict) -> dict:
    device = manifest.get("device", {}).get("codename", "")
    if not device:
        return {}
    report = compare_lock(manifest, device)
    write_json(manifest_dir() / "lock_compare.json", report)
    return report


def _write_detect_summary(manifest: dict) -> None:
    safety = manifest.get("safety", {})
    super_cfg = manifest.get("super", {})
    lines = [
        f"package_type={manifest.get('rom', {}).get('package_type', '')}",
        f"device_codename={manifest.get('device', {}).get('codename', '')}",
        f"rom_version={manifest.get('rom', {}).get('version', '')}",
        f"super_layout_source={super_cfg.get('layout_source', '')}",
        f"layout_complete={str(safety.get('layout_complete', False)).lower()}",
        f"dynamic_partitions_count={len(super_cfg.get('dynamic_partitions', []))}",
        f"physical_images_count={len(super_cfg.get('physical_images', []))}",
        "warnings:",
    ]
    lines.extend([f"- {item}" for item in safety.get("warnings", [])])
    lines.append("errors:")
    lines.extend([f"- {item}" for item in safety.get("errors", [])])
    logs_dir().mkdir(parents=True, exist_ok=True)
    (logs_dir() / "detect_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dzfactory.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="resolve local or remote ROM input")
    resolve.add_argument("--rom", required=True)
    resolve.set_defaults(func=cmd_resolve)

    inspect = sub.add_parser("inspect", help="inspect Fastboot/Xiaomi.eu ROM package")
    inspect.add_argument("--rom", required=True)
    inspect.add_argument("--device-hint", default="")
    inspect.set_defaults(func=cmd_inspect)

    detect = sub.add_parser("detect", help="probe a ROM package and write Factory v2 manifests")
    detect.add_argument("--rom", required=True, help="ROM URL or local path")
    detect.add_argument("--device-hint", default="", help="optional device codename hint")
    detect.add_argument("--profile", default="", help="optional Factory v2 profile name")
    detect.add_argument("--variant", default="balanced", help="Factory v2 variant")
    detect.set_defaults(func=cmd_detect)

    build = sub.add_parser("build", help="validate a Factory v2 manifest and preview super build")
    build.add_argument("--manifest", default="", help="path to build_manifest.json")
    build.add_argument("--dry-run", action="store_true", help="resolve, inspect, plan, and generate previews without modifying images")
    build.add_argument("--rom", default="", help="ROM URL or local path for dry-run")
    build.add_argument("--device-hint", default="", help="optional device codename hint for dry-run")
    build.add_argument("--profile", default="", help="optional Factory v2 profile name for dry-run")
    build.add_argument("--variant", default="balanced", help="Factory v2 variant for dry-run")
    build.set_defaults(func=cmd_build)

    lock = sub.add_parser("lock", help="manage verified Factory v2 layout locks")
    lock_sub = lock.add_subparsers(dest="lock_command", required=True)
    lock_create = lock_sub.add_parser("create", help="create a verified layout lock")
    lock_create.add_argument("--manifest", required=True, help="path to build_manifest.json")
    lock_create.add_argument("--device", required=True, help="device codename; currently zircon-first")
    lock_create.add_argument("--allow-incomplete", action="store_true", help="write a diagnostic lock for incomplete layouts")
    lock_create.set_defaults(func=cmd_lock_create)
    lock_compare = lock_sub.add_parser("compare", help="compare manifest layout against a lock")
    lock_compare.add_argument("--manifest", required=True, help="path to build_manifest.json")
    lock_compare.add_argument("--device", required=True, help="device codename")
    lock_compare.set_defaults(func=cmd_lock_compare)

    devices = sub.add_parser("devices", help="query Factory v2 device database")
    devices_sub = devices.add_subparsers(dest="devices_command", required=True)
    devices_list = devices_sub.add_parser("list")
    devices_list.add_argument("--set", required=True)
    devices_list.set_defaults(func=cmd_devices_list)
    devices_show = devices_sub.add_parser("show")
    devices_show.add_argument("device")
    devices_show.set_defaults(func=cmd_devices_show)

    super_cmd = sub.add_parser("super", help="super image roundtrip commands")
    super_sub = super_cmd.add_subparsers(dest="super_command", required=True)
    super_read = super_sub.add_parser("read")
    super_read.add_argument("--super", required=True)
    super_read.set_defaults(func=cmd_super_read)
    super_unpack = super_sub.add_parser("unpack")
    super_unpack.add_argument("--super", required=True)
    super_unpack.set_defaults(func=cmd_super_unpack)
    super_rebuild = super_sub.add_parser("rebuild")
    super_rebuild.add_argument("--layout", required=True)
    super_rebuild.add_argument("--images", required=True)
    super_rebuild.set_defaults(func=cmd_super_rebuild)
    super_validate = super_sub.add_parser("validate")
    super_validate.add_argument("--original", required=True)
    super_validate.add_argument("--rebuilt", required=True)
    super_validate.set_defaults(func=cmd_super_validate)
    super_roundtrip = super_sub.add_parser("roundtrip")
    super_roundtrip.add_argument("--super", required=True)
    super_roundtrip.set_defaults(func=cmd_super_roundtrip)

    fastboot = sub.add_parser("fastboot", help="Fastboot-first Factory v2 commands")
    fastboot_sub = fastboot.add_subparsers(dest="fastboot_command", required=True)
    fastboot_build = fastboot_sub.add_parser("build")
    fastboot_build.add_argument("--rom", required=True)
    fastboot_build.add_argument("--device", default="auto")
    fastboot_build.add_argument("--profile", default="none")
    fastboot_build.add_argument("--output", default="output/final")
    fastboot_build.add_argument("--allow-unknown-device", action="store_true")
    fastboot_build.set_defaults(func=cmd_fastboot_build)

    xiaomi_eu = sub.add_parser("xiaomi-eu", help="Xiaomi.eu hybrid helpers")
    xiaomi_eu_sub = xiaomi_eu.add_subparsers(dest="xiaomi_eu_command", required=True)
    xiaomi_eu_inspect = xiaomi_eu_sub.add_parser("inspect")
    xiaomi_eu_inspect.add_argument("--rom", required=True)
    xiaomi_eu_inspect.set_defaults(func=cmd_xiaomi_eu_inspect)

    xfu = sub.add_parser("xfu", help="XiaomiFirmwareUpdater report helpers")
    xfu_sub = xfu.add_subparsers(dest="xfu_command", required=True)
    xfu_devices = xfu_sub.add_parser("devices")
    xfu_devices_sub = xfu_devices.add_subparsers(dest="xfu_devices_command", required=True)
    xfu_devices_import = xfu_devices_sub.add_parser("import")
    xfu_devices_import.set_defaults(func=cmd_xfu_devices_import)
    xfu_updates = xfu_sub.add_parser("updates")
    xfu_updates_sub = xfu_updates.add_subparsers(dest="xfu_updates_command", required=True)
    xfu_updates_parse = xfu_updates_sub.add_parser("parse")
    xfu_updates_parse.add_argument("--file", required=True)
    xfu_updates_parse.set_defaults(func=cmd_xfu_updates_parse)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
