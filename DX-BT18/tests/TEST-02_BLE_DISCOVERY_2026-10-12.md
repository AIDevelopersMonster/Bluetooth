# DX-BT18 / BT18-T — TEST-02A BLE advertisement discovery

**Date:** 2026-10-12  
**Outcome:** **PASS — BLE discovery and advertisement reception** (not yet GATT/Classic SPP)
**Evidence:** Windows PowerShell console transcript provided by hardware owner.

## Environment

- Windows PC BLE adapter (exact Bluetooth adapter model not provided).
- Python **3.14**, selected explicitly with `py -3.14`.
- `bleak 2.1.1`, WinRT-related Python dependencies installed for Python 3.14.
- Target radio sold as DX-BT18, advertising under **BT18-T**.
- Prior UART test: CH340 COM4 at 9600, successful **8/8 AT replies** with **EN connected to GND** and **button not pressed**. No wiring changes were reported for this BLE scan, but physical wiring during the scan was not re-verified independently.

## Reproduction command

```powershell
cd C:\GitHub\Bluetooth
py -3.14 .\DX-BT18\tools\bt18_ble_scan.py --duration 12
```

The earlier command `py .\DX-BT18\tools\bt18_ble_scan.py` had launched **Python 3.9.13** because of the script's `python3` shebang / launcher selection, whereas `py -m pip` used **Python 3.14**. This caused a false impression of missing `bleak`. Explicit `py -3.14` fixed interpreter selection; BLE scanning worked. No package reinstall was required.

## Observed radio result

| Field | Observed value |
| --- | --- |
| Scan duration | 12 s |
| Discovered devices (all) | 6 |
| Target name | `BT18-T` |
| Target BLE address / Windows identifier | **`98:DA:F0:00:EE:27`** |
| Target RSSI | **-79 dBm** |
| Advertised service UUID | **`0000FFE0-0000-1000-8000-00805F9B34FB`** |
| Advertised manufacturer data ID | `0x0000` |
| Discovery state | **PASS** |

Other nearby devices' identifiers are intentionally excluded from this public test log.

### Comparison with AT address fields

Earlier full UART console transcript: `AT+ADSS?` returned **`99ea00f0da98`**. Later the owner separately supplied **`27ee00f0da98`**. The Bluetooth LE scan now reports **`98:DA:F0:00:EE:27`**, which is an **exact reversal of all six bytes** of `27:EE:00:F0:DA:98`.

This strongly links the separately provided `27ee00f0da98` identifier to the discovered `BT18-T`. It does **not** establish whether the earlier `99ea00f0da98` transcript belongs to a different physical module, or was transcribed differently. A vendor-specific byte-order presentation may explain the difference between command output and the Windows BLE rendering; do **not** treat a general reversal convention as proven for all devices.

The two values are published at the owner's request. BLE addresses and configuration fields are **not guaranteed to be globally unique on programmable clones**; this test does not establish a public-vs-random address type or genuine chip manufacturer.

## Evidence boundaries

**Certified by this test:** radio advertising was received by the PC BLE adapter; exact `BT18-T` name and `FFE0` service UUID appeared in the scan.

**Not certified:** successful BLE GATT connection, actual GATT service/characteristic presence `FFE1` and `FFE2`, characteristic read/write/notify, two-way UART↔BLE data, Classic Bluetooth SPP, radio quality or manufacturer authenticity. One RSSI reading is not a range/quality benchmark.

## Next step: TEST-02B GATT layout (no writes)

```powershell
cd C:\GitHub\Bluetooth
py -3.14 .\DX-BT18\tools\bt18_ble_scan.py --duration 12 --name BT18-T --address "98:DA:F0:00:EE:27"
```

This will attempt to **connect** to the discovered device and enumerate GATT services and characteristic properties, without reading or writing characteristic values. Do not press the button or change the proven setup merely for this read-only discovery. A connection failure must be reported separately from this successful BLE advertising test.

## Related evidence

- [TEST-01 UART/AT FULL PASS](TEST-01_AT_UART_RESULT_2026-10-12.md).
- [Laboratory test plan](TEST_PLAN.md).
