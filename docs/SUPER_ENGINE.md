# Super Engine

The Factory v2 super engine treats the original Fastboot `super.img` as the source of truth.

## Acceptance Test

The first production acceptance test is:

```bash
python -m dzfactory.cli super roundtrip --super /path/to/super.img
```

This runs:

1. `super read`
2. `super unpack`
3. `super rebuild`
4. `super validate`

Success means `output/images/super.img` exists and `output/logs/super_roundtrip_report.json` reports `pass`.

## Rules

- Do not use file size of `super.img` as `super_size`.
- Do not hardcode `qti_dynamic_partitions`.
- Preserve group names and sizes.
- Preserve metadata slots.
- Preserve partition names and logical sizes.
- Preserve `odm`, `mi_ext`, `vendor_dlkm`, `system_dlkm`, and `odm_dlkm` when present.

The engine uses `lpdump`, `lpunpack`, `lpmake`, and sparse conversion tools when required.
