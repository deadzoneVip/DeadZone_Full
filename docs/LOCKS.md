# Factory v2 Layout Locks

Layout locks record a known-good dynamic partition layout for a specific device and ROM version. They are stored under:

```text
db/known_builds/xiaomi/<device>/<rom_version>.lock.json
```

## Create A Lock

```bash
python3 -m dzfactory.cli lock create \
  --manifest output/manifest/build_manifest.json \
  --device zircon
```

Lock creation is allowed only when the manifest layout source is `lpdump` from `super.img` or `super_empty.img`, the ROM version exists, and dynamic partitions are present.

## Compare A Lock

```bash
python3 -m dzfactory.cli lock compare \
  --manifest output/manifest/build_manifest.json \
  --device zircon
```

Comparison checks super size, metadata slots, slot mode, and dynamic partition names. It reports missing partitions such as `odm` or `mi_ext`.

## Recovery OTA Rule

Recovery OTA packages must be compared against an existing layout lock before build. Factory v2 must not infer a full super layout from OTA metadata alone.
