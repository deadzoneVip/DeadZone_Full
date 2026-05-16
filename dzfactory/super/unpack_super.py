from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import write_json
from dzfactory.common.paths import manifest_dir, output_dir, probe_dir
from dzfactory.common.shell import run_capture, which


def unpack_super(super_path: str) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    image = Path(super_path)
    out_dir = output_dir() / "super_unpacked"
    out_dir.mkdir(parents=True, exist_ok=True)
    source = image
    if not image.exists():
        errors.append(f"super image does not exist: {image}")
    elif not which("lpunpack"):
        errors.append("lpunpack not available")
    else:
        rc, _, stderr = run_capture(["lpunpack", str(source), str(out_dir)], timeout=900)
        if rc != 0 and _looks_sparse(image) and which("simg2img"):
            raw = probe_dir() / "super.raw.img"
            conv_rc, _, conv_err = run_capture(["simg2img", str(image), str(raw)], timeout=900)
            if conv_rc == 0:
                source = raw
                rc, _, stderr = run_capture(["lpunpack", str(source), str(out_dir)], timeout=900)
            else:
                errors.append(f"simg2img failed: {conv_err.strip()}")
        if rc != 0:
            errors.append(f"lpunpack failed: {stderr.strip()}")
    images = []
    for item in sorted(out_dir.glob("*.img")):
        images.append({"partition": item.stem, "path": str(item), "size": item.stat().st_size, "sha256": _sha256(item)})
    report = {"images": images, "warnings": warnings, "errors": errors}
    write_json(manifest_dir() / "unpacked_super_images.json", report)
    return report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_sparse(path: Path) -> bool:
    try:
        return path.read_bytes()[:4] == b"\x3a\xff\x26\xed"
    except OSError:
        return False
