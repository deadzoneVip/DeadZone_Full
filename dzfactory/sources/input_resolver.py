from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from dzfactory.common.paths import downloads_dir


def resolve_input(rom: str) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    parsed = urlparse(rom)
    is_remote = parsed.scheme in {"http", "https"}
    local_path = Path(rom).expanduser() if not is_remote else None
    filename = Path(parsed.path if is_remote else rom).name or "rom_package.bin"
    resolved_type = "remote_url" if is_remote else "local_folder" if local_path and local_path.is_dir() else "local_file"
    final_path: Path | None = None

    if is_remote:
        target = downloads_dir() / filename
        try:
            final_path = _download(rom, target)
        except Exception as exc:  # pragma: no cover - network environment dependent
            errors.append(f"download failed: {exc}")
    elif local_path and local_path.exists():
        final_path = local_path.resolve()
    else:
        errors.append(f"input does not exist: {rom}")

    file_size = final_path.stat().st_size if final_path and final_path.is_file() else 0
    sha256 = _sha256(final_path) if final_path and final_path.is_file() else ""
    return {
        "original_input": rom,
        "resolved_type": resolved_type,
        "local_path": str(final_path) if final_path else "",
        "filename": filename,
        "file_size": file_size,
        "sha256": sha256,
        "warnings": warnings,
        "errors": errors,
    }


def _download(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    headers = {}
    mode = "wb"
    if partial.exists():
        headers["Range"] = f"bytes={partial.stat().st_size}-"
        mode = "ab"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=90) as response:
        if getattr(response, "status", 200) == 200 and mode == "ab":
            mode = "wb"
        with partial.open(mode) as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
    partial.replace(target)
    return target


def _sha256(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
