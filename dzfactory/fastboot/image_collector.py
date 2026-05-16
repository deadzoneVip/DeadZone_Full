from __future__ import annotations

import hashlib
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

from dzfactory.common.paths import output_dir

PHYSICAL_IMAGES = (
    "boot.img",
    "init_boot.img",
    "vendor_boot.img",
    "dtbo.img",
    "vbmeta.img",
    "vbmeta_system.img",
    "vbmeta_vendor.img",
    "logo.img",
)


def extract_image(package_path: str, image_name: str, destination: Path) -> Path | None:
    src = Path(package_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        found = next((item for item in src.rglob(image_name) if item.is_file() and _is_images_entry(item, src)), None)
        if found:
            shutil.copyfile(found, destination)
            return destination
        return None
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                if _entry_key(info.filename) == f"images/{image_name}":
                    with zf.open(info) as fh, destination.open("wb") as out:
                        shutil.copyfileobj(fh, out, length=1024 * 1024)
                    return destination
    if tarfile.is_tarfile(src):
        with tarfile.open(src) as tf:
            for member in tf.getmembers():
                if member.isfile() and _entry_key(member.name) == f"images/{image_name}":
                    fh = tf.extractfile(member)
                    if fh:
                        with fh, destination.open("wb") as out:
                            shutil.copyfileobj(fh, out, length=1024 * 1024)
                        return destination
    return None


def collect_physical_images(package_path: str, image_names: list[str], dest_dir: Path | None = None) -> list[dict[str, Any]]:
    dest_dir = dest_dir or output_dir() / "fastboot_images"
    images = []
    for entry in image_names:
        name = Path(entry).name
        extracted = extract_image(package_path, name, dest_dir / name)
        if extracted:
            images.append({"partition": name[:-4], "path": str(extracted), "size": extracted.stat().st_size, "sha256": _sha256(extracted)})
    return images


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry_key(entry: str) -> str:
    lower = entry.replace("\\", "/").strip("/").lower()
    if "/images/" in lower:
        return "images/" + lower.rsplit("/images/", 1)[1]
    if lower.startswith("images/"):
        return lower
    return Path(lower).name


def _is_images_entry(path: Path, root: Path) -> bool:
    return "images" in path.relative_to(root).parts
