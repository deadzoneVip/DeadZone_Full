from __future__ import annotations

import re
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from dzfactory.common.paths import logs_dir, probe_dir


REGION_HINTS = {
    "CN": "china",
    "EU": "europe",
    "MI": "global",
    "IN": "india",
    "ID": "indonesia",
    "RU": "russia",
    "TR": "turkey",
    "TW": "taiwan",
}

DETECTED_ENTRIES = (
    "images/super.img",
    "images/super_empty.img",
    "images/boot.img",
    "images/init_boot.img",
    "images/vendor_boot.img",
    "images/dtbo.img",
    "images/vbmeta.img",
    "images/vbmeta_system.img",
    "images/vbmeta_vendor.img",
    "images/system.img",
    "images/product.img",
    "images/system_ext.img",
    "images/vendor.img",
    "images/vendor_dlkm.img",
    "images/system_dlkm.img",
    "images/odm.img",
    "images/odm_dlkm.img",
    "images/mi_ext.img",
    "payload.bin",
    "payload_properties.txt",
    "dynamic_partitions_op_list",
    "flash_all.bat",
    "flash_all.sh",
)


def _inspect_zip(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def _inspect_tar(path: Path) -> list[str]:
    with tarfile.open(path) as tf:
        return tf.getnames()


def _read_zip_member(path: Path, basename: str) -> str:
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if Path(name).name == basename:
                with zf.open(name) as fh:
                    return fh.read(1024 * 1024).decode("utf-8", errors="replace")
    return ""


def _read_tar_member(path: Path, basename: str) -> str:
    with tarfile.open(path) as tf:
        for member in tf.getmembers():
            if Path(member.name).name == basename and member.isfile():
                fh = tf.extractfile(member)
                if fh:
                    return fh.read(1024 * 1024).decode("utf-8", errors="replace")
    return ""


def _entry_key(name: str) -> str:
    normalized = name.replace("\\", "/").strip("/")
    lower = normalized.lower()
    if "/images/" in lower:
        return "images/" + lower.rsplit("/images/", 1)[1]
    if lower.startswith("images/"):
        return lower
    return Path(lower).name


def classify_entries(names: list[str], filename: str = "") -> dict[str, Any]:
    keys = [_entry_key(name) for name in names]
    key_set = set(keys)
    detected = {entry: entry in key_set for entry in DETECTED_ENTRIES}
    image_entries = sorted({key for key in keys if key.startswith("images/") and key.endswith(".img")})
    has_flash_script = detected["flash_all.bat"] or detected["flash_all.sh"]

    if detected["images/super.img"] and has_flash_script:
        package_type = "fastboot_rom"
    elif detected["payload.bin"]:
        package_type = "recovery_payload_ota"
    elif image_entries:
        package_type = "images_package"
    else:
        package_type = "unknown"

    if not names:
        lower_name = filename.lower()
        if "ota" in lower_name:
            package_type = "recovery_payload_ota"
        elif "images" in lower_name or "fastboot" in lower_name:
            package_type = "images_package"

    return {
        "package_type": package_type,
        "detected_entries": detected,
        "image_entries": image_entries,
        "has_flash_script": has_flash_script,
    }


def _write_entries_log(names: list[str]) -> None:
    logs_dir().mkdir(parents=True, exist_ok=True)
    content = "\n".join(names)
    (logs_dir() / "package_entries.txt").write_text((content + "\n") if content else "", encoding="utf-8")


def _copy_stream_to_probe(stream: Any, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        shutil.copyfileobj(stream, out, length=1024 * 1024)
    return str(destination)


def _extract_zip_probe_image(path: Path, basename: str, destination: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if _entry_key(name) == f"images/{basename}":
                with zf.open(name) as source:
                    return _copy_stream_to_probe(source, destination)
    return ""


def _extract_tar_probe_image(path: Path, basename: str, destination: Path) -> str:
    with tarfile.open(path) as tf:
        for member in tf.getmembers():
            if _entry_key(member.name) == f"images/{basename}" and member.isfile():
                source = tf.extractfile(member)
                if source:
                    return _copy_stream_to_probe(source, destination)
    return ""


def _metadata_from_filename(filename: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "codename": "",
        "version": "",
        "android_version": "",
        "region": "",
        "rom_family": "",
        "rom_major": None,
    }
    stem = filename
    codename_match = re.search(r"(^|[-_])([a-z0-9]+)[-_](?:ota|images|fastboot|global)", stem, re.I)
    if codename_match:
        data["codename"] = codename_match.group(2).lower()

    version_match = re.search(r"(OS\d+(?:\.\d+){2,}\.[A-Z0-9]+|V\d+(?:\.\d+){2,}\.[A-Z0-9]+)", stem, re.I)
    if version_match:
        version = version_match.group(1).upper()
        data["version"] = version
        if version.startswith("OS"):
            data["rom_family"] = "hyperos"
            major = re.match(r"OS(\d+)", version)
        else:
            data["rom_family"] = "miui"
            major = re.match(r"V(\d+)", version)
        if major:
            data["rom_major"] = int(major.group(1))
        build_code = version.split(".")[-1]
        region_code = build_code[3:5] if len(build_code) >= 5 else ""
        data["region"] = REGION_HINTS.get(region_code, region_code.lower())

    android_match = re.search(r"user[-_](\d+(?:\.\d+)*)", stem, re.I)
    if android_match:
        data["android_version"] = android_match.group(1)
    return data


def probe_package(resolved: dict[str, Any]) -> dict[str, Any]:
    filename = resolved["filename"]
    names: list[str] = []
    warnings: list[str] = list(resolved.get("warnings", []))
    errors: list[str] = list(resolved.get("errors", []))
    dynamic_partitions_op_list = ""
    local_paths: dict[str, str] = {}
    path = Path(resolved["path"]) if resolved.get("exists") else None

    if path:
        try:
            if path.is_dir():
                names = [str(item.relative_to(path)).replace("\\", "/") for item in path.rglob("*") if item.is_file()]
                op_file = next((item for item in path.rglob("dynamic_partitions_op_list") if item.is_file()), None)
                if op_file:
                    dynamic_partitions_op_list = op_file.read_text(encoding="utf-8", errors="replace")
                    local_paths["dynamic_partitions_op_list"] = str(op_file)
                for image_name in ("super.img", "super_empty.img"):
                    image_file = next((item for item in path.rglob(image_name) if item.is_file()), None)
                    if image_file:
                        dest = probe_dir() / image_name
                        shutil.copyfile(image_file, dest)
                        local_paths[image_name] = str(dest)
            elif zipfile.is_zipfile(path):
                names = _inspect_zip(path)
                dynamic_partitions_op_list = _read_zip_member(path, "dynamic_partitions_op_list")
                for image_name in ("super.img", "super_empty.img"):
                    extracted = _extract_zip_probe_image(path, image_name, probe_dir() / image_name)
                    if extracted:
                        local_paths[image_name] = extracted
            elif tarfile.is_tarfile(path):
                names = _inspect_tar(path)
                dynamic_partitions_op_list = _read_tar_member(path, "dynamic_partitions_op_list")
                for image_name in ("super.img", "super_empty.img"):
                    extracted = _extract_tar_probe_image(path, image_name, probe_dir() / image_name)
                    if extracted:
                        local_paths[image_name] = extracted
        except Exception as exc:  # pragma: no cover - defensive report path
            errors.append(f"failed to inspect package contents: {exc}")
    else:
        warnings.append("ROM input is not a local file; detection is based on filename only")

    names = sorted(names)
    _write_entries_log(names)
    classification = classify_entries(names, filename)
    detected_entries = classification["detected_entries"]
    image_names = sorted({Path(entry).name for entry in classification["image_entries"]})

    meta = _metadata_from_filename(filename)
    return {
        "source": resolved["source"],
        "filename": filename,
        "package_type": classification["package_type"],
        "contents_inspected": bool(names),
        "content_count": len(names),
        "entries": names,
        "detected_entries": detected_entries,
        "contains": {
            "payload.bin": detected_entries["payload.bin"],
            "payload_properties.txt": detected_entries["payload_properties.txt"],
            "super.img": detected_entries["images/super.img"],
            "super_empty.img": detected_entries["images/super_empty.img"],
            "images": bool(classification["image_entries"]),
            "dynamic_partitions_op_list": detected_entries["dynamic_partitions_op_list"],
            "flash_all.bat": detected_entries["flash_all.bat"],
            "flash_all.sh": detected_entries["flash_all.sh"],
        },
        "physical_images": classification["image_entries"],
        "image_names": image_names,
        "metadata": meta,
        "dynamic_partitions_op_list": dynamic_partitions_op_list,
        "local_paths": local_paths,
        "warnings": warnings,
        "errors": errors,
    }
