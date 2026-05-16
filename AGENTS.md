# DeadZone ROM Factory

This repository is DeadZone ROM Factory. It currently contains the legacy DeadZone ROM Kitchen build flow and the new Factory v2 foundation.

## Legacy Safety

- Preserve the legacy build flow unless a task explicitly asks to change it.
- Do not remove old core scripts under `core/`.
- Do not replace the old build path until Factory v2 is proven and explicitly enabled.
- New Factory v2 code lives under `dzfactory/`.

## Factory v2 Rules

- Never guess or globally hardcode a super partition layout.
- Do not assume all Xiaomi devices use `qti_dynamic_partitions`.
- ROM package metadata and extracted files are the source of truth.
- Device configs are hints and safety overrides only.
- `build_manifest.json` is the single source of truth for Factory v2.
- If a layout is incomplete, `detect_only` must still write JSON reports with warnings/errors.
- Build mode must stop safely when `layout_complete=false`.

## Implementation Rules

- Use Python for detection, parsing, manifest generation, and validation.
- Use Bash only for orchestration and external tools.
- Public fastboot ZIPs must not include logs, runner paths, `sha256sums`, `build_info`, or upload links.
