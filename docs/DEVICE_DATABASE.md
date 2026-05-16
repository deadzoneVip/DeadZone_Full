# Device Database

Factory v2 starts with OS3 device sets split by SoC family.

## Commands

```bash
python -m dzfactory.cli devices list --set os3_mtk
python -m dzfactory.cli devices list --set os3_snapdragon
python -m dzfactory.cli devices show zircon
python -m dzfactory.cli devices show garnet
```

## Sets

- `configs/device_sets/os3_mtk.yml`
- `configs/device_sets/os3_snapdragon.yml`
- `configs/device_sets/postponed_os2.yml`

Zircon is MTK. Garnet is Snapdragon/QCOM. Factory v2 must not infer Qualcomm just because a device is Xiaomi.

XiaomiFirmwareUpdater integration is database/report only for now:

```bash
python -m dzfactory.cli xfu devices import
python -m dzfactory.cli xfu updates parse --file latest.yml
```

No autobuild is performed from tracker data in this milestone.
