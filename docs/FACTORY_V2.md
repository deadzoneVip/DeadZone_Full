# DeadZone ROM Factory v2

Factory v2 is the new multi-device foundation for DeadZone. It lives beside the legacy ROM Kitchen and starts with a safe `detect_only` mode that writes structured JSON reports without modifying ROM images.

Factory v2 remains behind `FACTORY_V2=true` for build-related flows. The legacy build remains the default path.

## detect_only Mode

`detect_only` probes a ROM URL or local package path, fingerprints the target device from package metadata and optional config hints, detects the super layout as far as the package allows, and writes manifests under `output/manifest/`.

Example for zircon:

```bash
python3 -m dzfactory.cli detect \
  --rom "zircon-ota_full-OS3.0.303.0.WNOCNXM-user-16.0.zip" \
  --device-hint zircon \
  --profile DeadZone_Gaming
```

Example for garnet:

```bash
python3 -m dzfactory.cli detect \
  --rom "garnet_global_images_OS2.0.1.0.zip" \
  --device-hint garnet \
  --profile DeadZone_Legend
```

The legacy entrypoint can also run detection:

```bash
OUTPUT_TYPE=detect_only ./main.sh "$ROM_URL" zircon true detect_only
```

## ROM Resolver

The resolver accepts page URLs, direct URLs, and local paths. Remote inputs are downloaded to `output/downloads/` with resume support where the server allows it. The resolved input, local cache path, and SHA-256 are written to `output/manifest/input_resolved.json`.

## Package Probe

The package probe detects:

- `fastboot_rom`
- `recovery_payload_ota`
- `images_package`
- `unknown`

It lists archive entries without extracting the full ROM and writes `output/logs/package_entries.txt`. It looks for fastboot flash scripts, payload files, vbmeta images, boot images, `dynamic_partitions_op_list`, and dynamic partition images.

When `images/super.img` or `images/super_empty.img` is present, detect mode extracts only that image into `output/probe/` so `lpdump` can inspect the real layout.

## Device Fingerprint

Device configs under `configs/devices/` are hints and safety overrides. They do not define the final super layout. For example, zircon is marked as MTK and garnet as Qualcomm when the matching hint is supplied.

## Super Layout Detection

Factory v2 must not guess one global layout. The intended priority order is:

1. `lpdump` from `super.img`
2. `lpdump` from `super_empty.img`
3. `dynamic_partitions_op_list`
4. payload manifest metadata
5. extracted image names for dynamic partition names only
6. device config hints

Fastboot `images/super.img` is preferred when available. Factory v2 writes `output/logs/lpdump_super.txt` or `output/logs/lpdump_super_empty.txt`, parses groups and dynamic partitions, and records missing fields explicitly when the layout is incomplete.

## build_manifest.json

`output/manifest/build_manifest.json` is the single source of truth for Factory v2. Build mode reads this file, validates it, and refuses to continue when `safety.layout_complete=false`.

Build gates also require a known device, known ROM version, complete dynamic partitions, super size, groups, metadata slots, no safety errors, and either an existing layout lock or a Fastboot ROM layout proven by `lpdump`.

## Profile System

Profiles live in `configs/profiles/`. The resolver currently creates `output/manifest/patch_plan.json` as a skeleton. Factory v2 profiles do not modify ROM images yet.

Profiles are declarative dry-run patch plans. Variants are `lite`, `balanced`, `performance`, `extreme`, and `clean`.

## Legacy-Safe Migration

The legacy build path remains the default. `main.sh` only enters Factory v2 when:

- `OUTPUT_TYPE=detect_only`, or
- `FACTORY_V2=true` for build-related output types.

Until Factory v2 is complete, keep production package builds on the legacy path.

## Layout Locks

Verified zircon layouts can be locked after `detect_only`:

```bash
python3 -m dzfactory.cli lock \
  --manifest output/manifest/build_manifest.json \
  --device zircon
```

The lock is written under `db/known_builds/xiaomi/zircon/` only when the manifest came from `lpdump` on `super.img` or `super_empty.img` and includes dynamic partitions.
