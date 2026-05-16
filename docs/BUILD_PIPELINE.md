# Factory v2 Build Pipeline

Factory v2 is a gated pipeline. It can inspect ROMs, generate manifests, compare locks, produce patch plans, and generate script previews. It must not patch or rebuild images until the manifest gate passes and the flow is explicitly enabled.

## Dry Run

```bash
python3 -m dzfactory.cli build --dry-run \
  --rom "https://example.com/zircon-fastboot.tgz" \
  --device-hint zircon \
  --profile DeadZone_Gaming \
  --variant performance
```

Dry-run performs:

- input resolution and cache download to `output/downloads/`
- SHA-256 calculation
- package inspection
- selective `super.img` / `super_empty.img` extraction
- lpdump layout detection when tools are available
- `build_manifest.json` generation
- lock comparison when a matching lock exists
- build gate validation
- declarative `patch_plan.json`
- `lpmake_command.txt` preview
- Windows fastboot script previews

The pipeline stops before modifying ROM images.

## Build Gate

Build may continue only when:

- `layout_complete=true`
- device and ROM version are known
- dynamic partitions are complete
- `super_size`, groups, and `metadata_slots` are known
- there are no safety errors
- a layout lock exists, or the package is a Fastboot ROM with an lpdump layout

Recovery OTA builds require an existing layout lock.
