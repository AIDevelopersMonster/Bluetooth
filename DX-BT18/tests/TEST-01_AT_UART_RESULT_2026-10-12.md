# DX-BT18 / BT18-T — TEST-01 UART AT READ-ONLY

**Date:** 2026-10-12  
**Status:** FULL PASS (bounded to read-only UART/AT functionality; 8 of 8 commands)  
**Evidence type:** exact console output provided by the hardware owner in the conversation. No independent measurement by the assistant; user-supplied physical test.

## Test configuration

- Device sold as DX-BT18, unmarked shield; radio discovery name: `BT18-T`.
- Host: Windows / PowerShell, Python launched with standard `py` (no virtualenv required).
- Interface: CH340 USB-UART enumerated as `COM4`.
- Four-wire lab stand: TX, RX, VCC, GND. No additional hardware wires specified.
- UART: **9600 baud**, Python serial default 8 data bits, no parity, 1 stop bit; commands terminated with CRLF.
- Script: `DX-BT18/tools/bt18_probe.py`.
- No configuration write or firmware operation.

```powershell
Set-Location C:\GitHub\Bluetooth
py .\DX-BT18\tools\bt18_probe.py --port COM4 --baud 9600 --profile dual
```

## Actual device responses

| Command | Response observed | Outcome |
| --- | --- | --- |
| `AT+TEST` | `OK` | PASS |
| `AT+VERS?` | `+VERS=V3.01`, `OK` | PASS |
| `AT+ADSS?` | Valid returned address; **redacted** in the public report | PASS |
| `AT+NAME?` | `+NAME=BT18-T`, `OK` | PASS |
| `AT+BAUD?` | `+BAUD=1`, `OK` | PASS |
| `AT+PIN?` | `+PIN=1234`, `OK` | PASS |
| `AT+UUID?` | `+UUID=ffe0,ffe1,ffe2`, `OK` | PASS |
| `AT+FLOW?` | `+FLOW=0`, `OK` | PASS |

Console summary: `Replies: 8/8. Identity is NOT certified by AT compatibility alone.`

Original DX-SMART DX-BT18 documentation maps `AT+BAUD=1` to **9600 baud**, agreeing with the host setting in the successful test. `AT+FLOW=0` reports disabled hardware flow control. The `FFE0/FFE1/FFE2` values come from AT configuration; they do **not** independently certify the over-the-air GATT database.

## Interpretation and pass boundary

1. This exact module responded on UART at 9600 through the CH340, using the documented DX-BT18-style command set. **The previously reported lack of working AT responses has been superseded.**
2. Reported firmware identifier is **V3.01**. It does not establish the physical SoC, manufacturer, or authenticity.
3. These replies certify **configuration inquiry via UART**, not a transparent-data UART session, Classic Bluetooth SPP payload integrity, BLE advertising characteristics, pairing, security, range or throughput.
4. The successful console command used a full eight-command sweep **without** `--start-delay`. Whether a physical button was pressed or held during the sweep was **not stated**, and the required AT-mode switch mechanism remains unknown.
5. Previously unsuccessful sessions are not deleted; the cause (button state, timing, wiring, mode, or other test condition) remains **undetermined**.
6. The complete Bluetooth address has intentionally not been copied into this public GitHub evidence record.

## Next acceptance target

**TEST-02 BLE:** with module powered, run discovery and enumerate GATT, then compare against reported `FFE0/FFE1/FFE2`. Alternatively / later **TEST-03 Classic SPP:** independently demonstrate a byte-for-byte round trip. Do not change module configuration, firmware, or pinout to do so.

No next test receives PASS automatically from this one.
