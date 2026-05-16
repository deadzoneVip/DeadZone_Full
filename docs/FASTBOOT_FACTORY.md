# Fastboot Factory

Factory v2 is now Fastboot-first. Official Xiaomi Fastboot ROMs are the first-class build source because `images/super.img` can be inspected with `lpdump` and round-tripped before packaging.

Factory v2 remains gated behind explicit CLI commands or `FACTORY_V2=true`. The legacy build path is unchanged.

## Supported Inputs

- Official Xiaomi Fastboot `.tgz`, `.tar`, or `.zip`
- Local extracted Fastboot folder
- Xiaomi.eu hybrid ZIP when it exposes usable Fastboot or super data
- Direct HTTP/HTTPS ROM URL

Recovery OTA support comes later after layout locks. OTA payload-only builds must not guess the super layout.

## Build Command

```bash
python -m dzfactory.cli fastboot build \
  --rom /path/to/official_fastboot_rom.tgz \
  --device auto \
  --profile none \
  --output output/final
```

Profile `none` means no patching. The production milestone proves that the factory can read, unpack, rebuild, validate, script, and package a stock-base DeadZone Fastboot ZIP.

## Clean ZIP Rules

Public ZIPs must contain only:

- `bin/windows/fastboot.exe`
- `bin/windows/AdbWinApi.dll`
- `bin/windows/AdbWinUsbApi.dll`
- `images/*.img`
- `windows_install_upgrade.bat`
- `windows_install_and_format_data.bat`
- `windows_format_data_only.bat`

The validator rejects logs, runner paths, `sha256sums.txt`, `build_info.txt`, `upload_links.txt`, absolute paths, `.log` files, and `.txt` sidecars.
