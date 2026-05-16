from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def output_dir() -> Path:
    return repo_root() / "output"


def manifest_dir() -> Path:
    return output_dir() / "manifest"


def logs_dir() -> Path:
    return output_dir() / "logs"


def probe_dir() -> Path:
    return output_dir() / "probe"


def downloads_dir() -> Path:
    return output_dir() / "downloads"


def images_dir() -> Path:
    return output_dir() / "images"


def final_dir() -> Path:
    return output_dir() / "final"


def updates_dir() -> Path:
    return output_dir() / "updates"


def ensure_output_dirs() -> None:
    manifest_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    probe_dir().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)
    images_dir().mkdir(parents=True, exist_ok=True)
    final_dir().mkdir(parents=True, exist_ok=True)
    updates_dir().mkdir(parents=True, exist_ok=True)


def config_dir() -> Path:
    return repo_root() / "configs"
