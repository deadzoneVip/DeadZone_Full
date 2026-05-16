from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any


def package_fastboot_zip(images: list[dict[str, Any]], scripts_dir: Path, output_zip: Path, bin_dir: Path | None = None) -> Path:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in images:
            path = Path(item["path"])
            if path.exists() and path.suffix == ".img":
                zf.write(path, f"images/{path.name}")
        for script in ("windows_install_upgrade.bat", "windows_install_and_format_data.bat", "windows_format_data_only.bat"):
            path = scripts_dir / script
            if path.exists():
                zf.write(path, script)
        if bin_dir and bin_dir.exists():
            for name in ("fastboot.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"):
                path = bin_dir / name
                if path.exists():
                    zf.write(path, f"bin/windows/{name}")
    return output_zip
