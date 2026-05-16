# Xiaomi.eu Hybrid Base

Xiaomi.eu hybrid ZIPs are allowed as Factory v2 bases only when they expose usable Fastboot or super data.

Inspect a package with:

```bash
python -m dzfactory.cli xiaomi-eu inspect --rom /path/to/xiaomi.eu.zip
```

Rules:

- If the package contains `images/super.img`, use the same Fastboot-first build flow.
- If it contains `payload.bin` only, stop real build unless a layout lock exists.
- If it has Fastboot scripts and images, collect images but generate DeadZone scripts from the manifest.
- Do not trust Xiaomi.eu scripts blindly.

No ProjectZK diff is required for this milestone.
