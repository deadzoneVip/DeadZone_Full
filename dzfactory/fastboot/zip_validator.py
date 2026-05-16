from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import write_json
from dzfactory.common.paths import logs_dir

FORBIDDEN_NAMES = {"sha256sums.txt", "build_info.txt", "upload_links.txt"}


def validate_fastboot_zip(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    entries: list[str] = []
    if not path.exists():
        errors.append(f"zip does not exist: {path}")
    else:
        with zipfile.ZipFile(path) as zf:
            entries = zf.namelist()
        for entry in entries:
            lower = entry.lower()
            if re.match(r"^[a-z]:[/\\]", entry) or entry.startswith(("/", "\\")):
                errors.append(f"absolute path in zip: {entry}")
            if "output/logs" in lower or lower.startswith("logs/"):
                errors.append(f"logs are forbidden in public zip: {entry}")
            if Path(lower).name in FORBIDDEN_NAMES:
                errors.append(f"forbidden sidecar in zip: {entry}")
            if lower.endswith(".log"):
                errors.append(f"log file forbidden in zip: {entry}")
            if lower.endswith(".txt"):
                errors.append(f"txt sidecar forbidden in zip: {entry}")
    report = {"status": "pass" if not errors else "fail", "entries": entries, "warnings": warnings, "errors": errors}
    write_json(logs_dir() / "zip_validation.json", report)
    return report
