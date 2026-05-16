from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dzfactory.common.paths import downloads_dir


def resolve_rom_input(source: str, download: bool = True) -> dict:
    parsed = urlparse(source)
    is_url = parsed.scheme in {"http", "https", "ftp"}
    path = None if is_url else Path(source).expanduser()
    filename = Path(parsed.path if is_url else source).name
    warnings: list[str] = []
    errors: list[str] = []
    resolved_path = path.resolve() if path and path.exists() else None
    sha256 = ""

    if is_url and download:
        filename = filename or "downloaded_rom.bin"
        target = downloads_dir() / filename
        try:
            resolved_path = _download_with_resume(source, target)
            sha256 = _sha256(resolved_path)
        except Exception as exc:  # pragma: no cover - network failures are environment dependent
            errors.append(f"download failed: {exc}")
    elif resolved_path:
        sha256 = _sha256(resolved_path) if resolved_path.is_file() else ""

    return {
        "source": source,
        "is_url": is_url,
        "downloaded": bool(is_url and resolved_path and resolved_path.exists()),
        "exists": bool(resolved_path and resolved_path.exists()),
        "path": str(resolved_path) if resolved_path else str(path) if path else "",
        "filename": filename,
        "suffixes": Path(filename).suffixes,
        "sha256": sha256,
        "warnings": warnings,
        "errors": errors,
    }


def _download_with_resume(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    headers = {}
    mode = "wb"
    if tmp.exists():
        headers["Range"] = f"bytes={tmp.stat().st_size}-"
        mode = "ab"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        if getattr(response, "status", 200) == 200 and mode == "ab":
            mode = "wb"
        with tmp.open(mode) as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
    tmp.replace(target)
    return target


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
