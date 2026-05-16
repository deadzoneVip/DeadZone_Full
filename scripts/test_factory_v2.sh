#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m compileall -q dzfactory

required_files=(
  "configs/devices/xiaomi/zircon.yml"
  "configs/devices/xiaomi/garnet.yml"
  "configs/families/xiaomi_mtk_vab.yml"
  "configs/families/xiaomi_qcom_vab.yml"
  "configs/profiles/DeadZone_Gaming/profile.yml"
  "configs/profiles/DeadZone_Legend/profile.yml"
  "configs/profiles/DeadZone_EPiC/profile.yml"
  "schemas/build_manifest.schema.json"
  "schemas/device.schema.json"
  "schemas/profile.schema.json"
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || {
    echo "missing required file: $file" >&2
    exit 1
  }
done

rm -rf output/manifest output/probe

python3 -m dzfactory.cli detect \
  --rom "zircon-ota_full-OS3.0.303.0.WNOCNXM-user-16.0-test.zip" \
  --device-hint zircon \
  --profile DeadZone_Gaming

[[ -f output/manifest/build_manifest.json ]] || {
  echo "build_manifest.json was not created" >&2
  exit 1
}

python3 -m dzfactory.cli detect \
  --rom "garnet_global_images_OS2.0.1.0.USER-15.0-test.zip" \
  --device-hint garnet \
  --profile DeadZone_Legend

[[ -f output/manifest/rom_probe.json ]]
[[ -f output/manifest/device_fingerprint.json ]]
[[ -f output/manifest/super_layout.json ]]
[[ -f output/manifest/patch_plan.json ]]

python3 - <<'PY'
from dzfactory.layout.parse_lpdump import parse_lpdump_text

sample = """
Metadata max size: 65536 bytes
Metadata slot count: 3
Super partition size: 9126805504 bytes
Group: main_a
Maximum size: 4563402752 bytes
Partition name: system_a
Group name: main_a
Size: 123456 bytes
Attributes: readonly
Partition name: vendor_a
Group name: main_a
Size: 654321 bytes
Attributes: readonly
"""
parsed = parse_lpdump_text(sample)
assert parsed["super_size"] == 9126805504
assert parsed["metadata_slots"] == 3
assert parsed["slot_mode"] == "vab"
assert parsed["active_slot"] == "a"
assert parsed["groups"][0]["name"] == "main_a"
assert parsed["dynamic_partitions"][0]["readonly"] is True
PY

python3 - <<'PY'
from dzfactory.layout.validate_manifest import validate_manifest

manifest = {
    "schema_version": 1,
    "rom": {},
    "device": {},
    "super": {},
    "profile": {},
    "safety": {"layout_complete": False, "warnings": [], "errors": ["missing super_size"]},
}
errors = validate_manifest(manifest, require_complete_layout=True)
assert "layout_complete=false; refusing Factory v2 build" in errors
assert "missing super_size" in errors
PY

python3 - <<'PY'
from dzfactory.probe.package_probe import classify_entries

classification = classify_entries([
    "some_rom/images/super.img",
    "some_rom/images/boot.img",
    "some_rom/flash_all.bat",
])
assert classification["package_type"] == "fastboot_rom"
assert classification["detected_entries"]["images/super.img"] is True
assert classification["detected_entries"]["flash_all.bat"] is True
PY

python3 - <<'PY'
from pathlib import Path
from dzfactory.resolvers.resolve_input import resolve_rom_input

sample = Path("output/test_local_rom.zip")
sample.parent.mkdir(parents=True, exist_ok=True)
sample.write_bytes(b"deadzone-test")
resolved = resolve_rom_input(str(sample), download=False)
assert resolved["exists"] is True
assert resolved["sha256"]
assert resolved["filename"] == "test_local_rom.zip"
PY

python3 - <<'PY'
from dzfactory.layout.validate_build_gate import validate_build_gate

manifest = {
    "rom": {"package_type": "recovery_payload_ota", "version": "OS3.0.0.0.TEST"},
    "device": {"codename": "zircon", "brand": "xiaomi"},
    "super": {"dynamic_partitions": [], "groups": [], "super_size": None, "metadata_slots": None, "layout_source": "none"},
    "safety": {"layout_complete": False, "errors": ["missing super_size"]},
}
gate = validate_build_gate(manifest)
assert gate["allowed"] is False
assert any("layout_complete=false" in error for error in gate["errors"])
PY

python3 - <<'PY'
from dzfactory.layout.lock_manager import compare_lock, create_lock

lock_manifest = {
    "rom": {"version": "OS3.0.LOCK.TEST", "package_type": "fastboot_rom"},
    "device": {"codename": "zircon", "brand": "xiaomi", "soc_vendor": "mtk"},
    "super": {
        "layout_source": "fastboot_super_img_lpdump",
        "super_size": 100,
        "metadata_slots": 3,
        "slot_mode": "vab",
        "dynamic_partitions": [{"name": "system_a"}, {"name": "odm_a"}, {"name": "mi_ext_a"}],
    },
    "safety": {"layout_complete": True, "errors": [], "warnings": []},
}
path, errors = create_lock(lock_manifest, "zircon")
assert not errors, errors
compare_manifest = {
    **lock_manifest,
    "super": {**lock_manifest["super"], "dynamic_partitions": [{"name": "system_a"}]},
}
report = compare_lock(compare_manifest, "zircon")
assert any("odm" in error for error in report["errors"])
assert any("mi_ext" in error for error in report["errors"])
PY

python3 - <<'PY'
from dzfactory.profiles.resolve_profile import resolve_profile
from dzfactory.profiles.build_patch_plan import build_patch_plan

manifest = {
    "rom": {"rom_family": "hyperos", "rom_major": 3, "android_version": "16", "region": "china"},
    "device": {"codename": "zircon", "soc_vendor": "mtk"},
}
profile = resolve_profile("DeadZone_Gaming", "performance")
plan = build_patch_plan(profile, manifest)
ids = {item["id"] for item in plan["selected_patch_sets"]}
assert "hyperos3_mtk_zircon_performance_props" in ids
PY

python3 - <<'PY'
from pathlib import Path
from dzfactory.package.script_generator import generate_fastboot_scripts

manifest = {"super": {"physical_images": ["images/super.img", "images/vbmeta.img"]}}
paths = generate_fastboot_scripts(manifest, Path("output/test_scripts"))
for path in paths.values():
    text = Path(path).read_text(encoding="utf-8").lower()
    assert "fastboot -w" not in text
    assert "--disable-verity" not in text
    assert "--disable-verification" not in text
PY

echo "Factory v2 smoke tests passed"
