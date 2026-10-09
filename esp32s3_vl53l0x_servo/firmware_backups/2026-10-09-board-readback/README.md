# ESP32-S3 board readback (2026-10-09)

This directory contains a read-only backup captured from `/dev/ttyACM0` before
making any project or flash changes.

## Detected firmware

- Project name: `esp32s3_vl53l0x_servo`
- App version: `c529b87-dirty`
- Build time: `2026-10-09 06:40:03 UTC`
- ESP-IDF: `v5.5.1`
- Runtime log tag: `TOF_BLOWER`
- Application image validation hash:
  `21e5dd127b1734f18001a5536b91f49a4acc62b6c5991b121107e0adc732c91c`

The firmware identifies two VL53L0X sensors, an HC-SR04, and a GPIO7 relay for
a blower. No LCD controller, LCD model, LCD pin assignment, display text, or
LCD initialization message was found in the boot log or application strings.
The `LCD_CAM` string is an ESP32-S3 SoC peripheral name and is not evidence that
the application uses an LCD.

At inspection time, both TOF sensors initialized successfully. The HC-SR04
repeatedly reported echo timeouts.

## Partition table

| Name | Type | Offset | Size |
|---|---|---:|---:|
| `nvs` | data/nvs | `0x9000` | 24 KiB |
| `phy_init` | data/phy | `0xF000` | 4 KiB |
| `factory` | app/factory | `0x10000` | 1 MiB |

## Files

- `system-region-0x00000-0x0ffff.bin`: bootloader, partition table, NVS, and PHY
  region exactly as read from flash.
- `partition-table-0x8000.bin`: standalone partition-table copy.
- `factory-app-0x10000-1mb.bin`: complete 1 MiB factory application partition,
  including unused erased bytes.

These are compiled binary backups, not recoverable C/C++ source code.
