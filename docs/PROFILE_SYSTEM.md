# Factory v2 Profile System

Factory v2 profiles are declarative manifests. They select patch sets and write `output/manifest/patch_plan.json`; they do not run arbitrary scripts and do not modify ROM images in the current pipeline.

## Profiles

- `DeadZone_Gaming`
- `DeadZone_Legend`
- `DeadZone_EPiC`

## Variants

- `lite`
- `balanced`
- `performance`
- `extreme`
- `clean`

## Match Inputs

Patch sets are selected from manifest facts:

- device codename
- SoC vendor
- ROM family
- ROM major version
- Android version
- region
- selected profile
- selected variant

Example:

```bash
python3 -m dzfactory.cli detect \
  --rom /path/to/zircon-fastboot.tgz \
  --device-hint zircon \
  --profile DeadZone_Gaming \
  --variant performance
```

This writes a dry-run patch plan under `output/manifest/patch_plan.json`.
