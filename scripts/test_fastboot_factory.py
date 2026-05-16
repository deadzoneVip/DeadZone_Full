from __future__ import annotations

import json
import zipfile
from pathlib import Path

from dzfactory.cli import build_parser
from dzfactory.devices.device_sets import load_device_set
from dzfactory.fastboot.package_inspector import inspect_package
from dzfactory.fastboot.script_generator import generate_windows_scripts
from dzfactory.fastboot.zip_validator import validate_fastboot_zip
from dzfactory.super.lpmake_builder import build_lpmake_command


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "test_fastboot_factory"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    test_package_classifier()
    test_script_generator_safety()
    test_zip_validator_rejects_sidecars()
    test_lpmake_preserves_layout_names()
    test_device_database()
    test_super_roundtrip_command_exists()
    print("fastboot factory tests passed")


def test_package_classifier() -> None:
    package = OUT / "fake_fastboot.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("images/super.img", b"fake")
        zf.writestr("images/boot.img", b"fake")
        zf.writestr("flash_all.bat", "fastboot flash super images\\super.img\n")
    probe = inspect_package(str(package))
    assert probe["package_type"] == "official_fastboot_rom"
    assert probe["has_super_img"] is True
    assert probe["has_fastboot_scripts"] is True


def test_script_generator_safety() -> None:
    image = OUT / "super.img"
    image.write_bytes(b"fake")
    report = generate_windows_scripts([{"partition": "super", "path": str(image)}], OUT / "scripts")
    assert report["status"] == "pass"
    for script_path in report["scripts"]:
        text = Path(script_path).read_text(encoding="utf-8").lower()
        assert "fastboot -w" not in text
        assert "--disable-verity" not in text
        assert "--disable-verification" not in text


def test_zip_validator_rejects_sidecars() -> None:
    bad_zip = OUT / "bad.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("images/super.img", b"fake")
        zf.writestr("output/logs/build.log", "nope")
        zf.writestr("sha256sums.txt", "nope")
    report = validate_fastboot_zip(bad_zip)
    assert report["status"] == "fail"
    assert any("forbidden" in err or "logs" in err for err in report["errors"])


def test_lpmake_preserves_layout_names() -> None:
    layout = {
        "super_size": 1000,
        "metadata_size": 65536,
        "metadata_slots": 3,
        "groups": [{"name": "main_a", "size": 900}],
        "dynamic_partitions": [{"name": "system_a", "size": 10, "group": "main_a"}],
    }
    system = OUT / "system_a.img"
    system.write_bytes(b"system")
    images = {"images": [{"partition": "system_a", "path": str(system)}]}
    cmd, errors = build_lpmake_command(layout, images, OUT / "super.img")
    assert not errors
    joined = " ".join(cmd)
    assert "main_a:900" in joined
    assert "system_a:readonly:10:main_a" in joined


def test_device_database() -> None:
    assert any(item["codename"] == "zircon" for item in load_device_set("os3_mtk"))
    assert any(item["codename"] == "garnet" for item in load_device_set("os3_snapdragon"))


def test_super_roundtrip_command_exists() -> None:
    parser = build_parser()
    args = parser.parse_args(["super", "roundtrip", "--super", "dummy.img"])
    assert args.super_command == "roundtrip"


if __name__ == "__main__":
    main()
