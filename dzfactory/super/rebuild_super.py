from __future__ import annotations

from pathlib import Path
from typing import Any

from dzfactory.common.jsonio import read_json
from dzfactory.common.paths import images_dir, logs_dir
from dzfactory.common.shell import run_capture, which
from dzfactory.super.lpmake_builder import build_lpmake_command


def rebuild_super(layout_path: str, images_path: str) -> dict[str, Any]:
    layout = read_json(Path(layout_path))
    images = read_json(Path(images_path))
    output = images_dir() / "super.img"
    cmd, errors = build_lpmake_command(layout, images, output)
    logs_dir().mkdir(parents=True, exist_ok=True)
    (logs_dir() / "lpmake_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    if not errors and not which("lpmake"):
        errors.append("lpmake not available")
    if not errors:
        rc, _, stderr = run_capture(cmd, timeout=1200)
        if rc != 0:
            errors.append(f"lpmake failed: {stderr.strip()}")
    return {"output": str(output), "command": cmd, "warnings": [], "errors": errors}
