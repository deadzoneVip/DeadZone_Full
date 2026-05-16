#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


MIB = 1024 * 1024
KNOWN_DYNAMIC_PARTITIONS = {
    "system",
    "product",
    "system_ext",
    "vendor",
    "vendor_dlkm",
    "system_dlkm",
    "odm",
    "odm_dlkm",
    "mi_ext",
    "my_product",
    "my_region",
    "my_stock",
    "my_preload",
}
COMMON_GROUP_NAMES = ("qti_dynamic_partitions", "main", "default")


def align(value: int, boundary: int = MIB) -> int:
    return ((value + boundary - 1) // boundary) * boundary


def shell_quote(value: str | int) -> str:
    return shlex.quote(str(value))


def parse_partitions_tsv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 5:
            continue
        part, img, size, container, fs = fields[:5]
        if Path(img).is_file():
            rows.append({"part": part, "img": img, "size": size, "container": container, "fs": fs})
    return rows


def is_dynamic_image(path: Path) -> bool:
    name = path.name
    if not name.endswith(".img"):
        return False
    part = name[:-4]
    if part.endswith(".raw"):
        part = part[:-4]
    if part.endswith("_a") or part.endswith("_b"):
        part = part[:-2]
    return part in KNOWN_DYNAMIC_PARTITIONS or part.endswith("_dlkm")


def partition_name(path: Path) -> str:
    part = path.name[:-4]
    if part.endswith(".raw"):
        part = part[:-4]
    if part.endswith("_a") or part.endswith("_b"):
        part = part[:-2]
    return part


def scan_images(search_dirs: list[Path], configured: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    configured_set = set(configured)
    discovered: dict[str, dict[str, str]] = {}
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.img")):
            if not is_dynamic_image(path):
                continue
            part = partition_name(path)
            if configured_set and part not in configured_set and part not in KNOWN_DYNAMIC_PARTITIONS and not part.endswith("_dlkm"):
                continue
            discovered.setdefault(
                part,
                {
                    "part": part,
                    "img": str(path),
                    "size": str(path.stat().st_size),
                    "container": "raw",
                    "fs": "unknown",
                },
            )

    ordered: list[dict[str, str]] = []
    missing: list[str] = []
    for part in configured:
        if part in discovered:
            ordered.append(discovered.pop(part))
        else:
            missing.append(part)
    ordered.extend(discovered.values())
    return ordered, missing


def read_lpdump(candidate: Path, lpdump: str, report_lines: list[str]) -> dict[str, str] | None:
    if not candidate.is_file():
        return None
    try:
        proc = subprocess.run([lpdump, str(candidate)], check=False, text=True, capture_output=True)
    except OSError as exc:
        report_lines.append(f"lpdump_error={exc}")
        return None
    if proc.returncode != 0:
        report_lines.append(f"lpdump_error={candidate}:{proc.stderr.strip()}")
        return None

    metadata_size = ""
    metadata_slots = ""
    group_name = ""
    group_size = ""
    current_name = ""
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if line.startswith("Metadata max size:"):
            metadata_size = first_int(line)
        elif line.startswith("Metadata slot count:"):
            metadata_slots = first_int(line)
        elif line.startswith("Name:"):
            current_name = line.split(":", 1)[1].strip()
        elif line.startswith("Maximum size:") and current_name and not group_size:
            group_name = current_name
            group_size = first_int(line)

    if metadata_size and metadata_slots and group_name and group_size:
        return {
            "source": "lpdump",
            "super_size": str(candidate.stat().st_size),
            "group_size": group_size,
            "group_name": group_name.removesuffix("_a").removesuffix("_b"),
            "metadata_size": metadata_size,
            "metadata_slots": metadata_slots,
        }
    return None


def first_int(text: str) -> str:
    for token in text.replace(":", " ").split():
        if token.isdigit():
            return token
    return ""


def write_partitions_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"{row['part']}\t{row['img']}\t{row['size']}\t{row['container']}\t{row['fs']}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve automatic lpmake super metadata.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--extracted", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--logs", required=True)
    parser.add_argument("--device-codename", default="")
    parser.add_argument("--device-brand", default="")
    parser.add_argument("--dynamic-partitions", default="")
    parser.add_argument("--super-size", default="")
    parser.add_argument("--group-size", default="")
    parser.add_argument("--group-name", default="")
    parser.add_argument("--group-basename", default="")
    parser.add_argument("--slot-mode", default="")
    parser.add_argument("--output-format", default="")
    parser.add_argument("--metadata-size", default="")
    parser.add_argument("--metadata-slots", default="")
    parser.add_argument("--lpdump", default="lpdump")
    parser.add_argument("--env-out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    extracted = Path(args.extracted)
    output = Path(args.output)
    logs = Path(args.logs)
    partitions_tsv = workspace / "partitions.tsv"
    logs.mkdir(parents=True, exist_ok=True)

    configured = [part for part in args.dynamic_partitions.split() if part]
    rows = parse_partitions_tsv(partitions_tsv)
    if not rows:
        rows, missing = scan_images([extracted, output / "images"], configured)
    else:
        present = {row["part"] for row in rows}
        extra_rows, missing = scan_images([extracted, output / "images"], configured)
        for row in extra_rows:
            if row["part"] not in present:
                rows.append(row)
                present.add(row["part"])
        missing = [part for part in configured if part not in present]

    if not rows:
        raise SystemExit("No dynamic partition images found for auto super mode.")

    write_partitions_tsv(partitions_tsv, rows)

    report_lines: list[str] = []
    manual = bool(args.super_size.strip() and args.group_size.strip())
    slot_mode = args.slot_mode.strip() or "VAB"
    output_format = args.output_format.strip() or "sparse"
    metadata_size = args.metadata_size.strip() or "65536"
    metadata_slots = args.metadata_slots.strip() or "2"
    group_base = args.group_basename.strip() or args.group_name.strip()
    if not group_base:
        group_base = "qti_dynamic_partitions" if args.device_brand.lower() == "xiaomi" or args.device_codename else COMMON_GROUP_NAMES[0]

    source = "manual"
    super_size = args.super_size.strip()
    group_size = args.group_size.strip()

    if not manual:
        source = "calculated"
        for candidate in (extracted / "super.img", output / "images" / "super.img", workspace / "input" / "super.img"):
            lpdump_result = read_lpdump(candidate, args.lpdump, report_lines)
            if lpdump_result:
                source = lpdump_result["source"]
                super_size = lpdump_result["super_size"]
                group_size = lpdump_result["group_size"]
                group_base = args.group_basename.strip() or lpdump_result["group_name"] or group_base
                metadata_size = lpdump_result["metadata_size"] or metadata_size
                metadata_slots = lpdump_result["metadata_slots"] or metadata_slots
                break

    aligned_sum = sum(align(int(row["size"])) for row in rows)
    reserve = 512 * MIB if aligned_sum >= 4 * 1024 * MIB else 256 * MIB
    if not group_size:
        group_size = str(align(aligned_sum + reserve))
    if not super_size:
        super_size = str(align(int(group_size) + reserve + 16 * MIB))
    if int(group_size) >= int(super_size):
        super_size = str(align(int(group_size) + reserve))

    mode = "manual" if manual else "auto"
    env = {
        "AUTO_SUPER_RESOLVED": "true",
        "AUTO_SUPER_MODE": mode,
        "AUTO_SUPER_SOURCE": source,
        "SUPER_SIZE": super_size,
        "DYNAMIC_PARTITION_GROUP_SIZE": group_size,
        "DYNAMIC_PARTITION_GROUP_NAME": args.group_name.strip() or group_base,
        "SUPER_GROUP_BASENAME": group_base,
        "SUPER_SLOT_MODE": slot_mode,
        "SUPER_OUTPUT_FORMAT": output_format,
        "SUPER_METADATA_SIZE": metadata_size,
        "SUPER_METADATA_SLOTS": metadata_slots,
        "DYNAMIC_PARTITIONS": " ".join(row["part"] for row in rows),
        "AUTO_SUPER_INCLUDED_PARTITIONS": " ".join(row["part"] for row in rows),
        "AUTO_SUPER_MISSING_PARTITIONS": " ".join(missing),
    }

    Path(args.env_out).write_text("".join(f"export {key}={shell_quote(value)}\n" for key, value in env.items()), encoding="utf-8")

    report = [
        "Auto Super Config Report",
        "========================",
        f"mode={mode}",
        f"source={source}",
        f"super_size={super_size}",
        f"group_size={group_size}",
        f"group_name={env['DYNAMIC_PARTITION_GROUP_NAME']}",
        f"group_basename={group_base}",
        f"slot_mode={slot_mode}",
        f"output_format={output_format}",
        f"metadata_size={metadata_size}",
        f"metadata_slots={metadata_slots}",
        f"aligned_image_sum={aligned_sum}",
        f"reserve={reserve}",
        "real_partitions_included=" + " ".join(row["part"] for row in rows),
        "missing_configured_partitions_skipped=" + (" ".join(missing) if missing else "none"),
    ]
    report.extend(report_lines)
    report.append("lpmake_command_args=written_after_build")
    Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
