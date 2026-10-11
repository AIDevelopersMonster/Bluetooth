# DX-BT18 — TEST plan and acceptance criteria

**ACTIVE, TEST-01 FULL PASS (2026-10-12)**. User-supplied CH340 `COM4` log at 9600 baud shows **8/8 responses** to documented read-only DX-BT18 AT queries. This **supersedes** the earlier CLOSED / NOT CERTIFIED decision recorded on 2026-10-11, but does not certify genuine silicon, Classic SPP or BLE GATT. [Physical result](TEST-01_AT_UART_RESULT_2026-10-12.md) · [superseded closure record](CLOSURE_2026-10-11.md).

| ID | Procedure | PASS condition | Key non-claim |
|---|---|---|---|
| TEST-01 UART / AT | **FULL PASS: 8/8**, CH340 COM4 at 9600, reported `V3.01` / `BT18-T` | Stable and complete read-only AT replies | AT syntax similarity does not prove maker or chip |
| TEST-02A BLE advertising | **PASS**: BT18-T found on Windows Python 3.14, `FFE0`, -79 dBm, `98:DA:F0:00:EE:27` | Actual broadcast received by Windows BLE adapter | GATT connection and SPP are NOT certified |
| TEST-02B GATT | **PENDING**: enumerate FFE0 / FFE1 / FFE2 | BLE connection and actual service/characteristic list | Advertising UUID alone does not establish GATT |
| TEST-03 Classic/SPP | Pair where supported; inspect OS-created serial port; bidirectional bytes | Exact TX/RX on actual UART and SPP, repeatable | No evidence of SPP merely from device name |
| TEST-04 Identity | Compare both sides of PCB, radio shield, chip markings, AT response and GATT characteristics | Evidence-based family attribution, list alternatives and uncertainty | "DX-BT18" shop title is not part number evidence |
| TEST-05 Firmware feasibility | Check confirmed SoC datasheet, memory organization, programmer, image provenance, OTP protection | Documentation-based decision; **no live writes** | ICE marking alone is not firmware compatibility |

## Execution: standard Python, no virtual environment

Run `py -m pip install --user -r .\DX-BT18\tools\requirements.txt` once from the repository root if dependencies are missing. Then call all scripts directly with `py`; no `.venv` activation is required.

## TEST-01 confirmed result

The executed command was:

```powershell
py .\DX-BT18\tools\bt18_probe.py --port COM4 --baud 9600 --profile dual
```

Observed: **8/8 correctly formatted responses and OK status**, see [protocol](TEST-01_AT_UART_RESULT_2026-10-12.md). The published transcript does **not** establish whether a physical button was held during the successful sweep, so do not infer its wiring.

## Earlier short single-command button check (historical)

Use this method **only if the board has a physical button whose role is still unverified**. In the original DX-BT18 reference circuit KEY1 grounds P26/GPIO25; there is no universal proof that the unmarked `BT18-T` button has the same wiring. Do not use HC-05 power-on or long-press/reset rituals.

1. Power the module normally with four wires (TX, RX, VCC, GND).
2. From `C:\GitHub\Bluetooth`, after `git pull --ff-only`, run:

```powershell
py .\DX-BT18\tools\bt18_probe.py --port COM4 --baud 9600 --profile dual --command "AT+TEST" --start-delay 3 --timeout 0.6
```

3. Press the on-board button only when the countdown shows `Sending in 1...`; **hold through sending/reading until result**, then release immediately.
4. Repeat once with `--command "AT+NAME?"` only if necessary. Stop if still silent, and inspect radio modes or obtain a board photo/seller pinout. A silent read-only probe is not a hardware FAIL.

## TEST-01 command sequence (PowerShell)

```powershell
Set-Location C:\GitHub\Bluetooth
git pull --ff-only
py .\DX-BT18\tools\bt18_probe.py --list-ports
py .\DX-BT18\tools\bt18_probe.py --port COM4 --baud 9600 --profile dual --json .\DX-BT18\results\test-01-dual.json
```

**Physical stand constraint: FOUR WIRES ONLY (VCC, GND, TX, RX).** No KEY/EN/ICE/VPP/P26 connections, jumper experiments or soldering. The original dual-mode DX-BT18 documentation mentions P26/GPIO25 LOW for AT mode, but our four-wire clone does not expose that control to the test. No AT response therefore means **AT ACCESS NOT ESTABLISHED**, not hardware FAIL. Try the documented LE read-only variant at most once if applicable:

```powershell
py .\DX-BT18\tools\bt18_probe.py --port COM4 --baud 9600 --profile le
```

If settings were previously changed, choose a different **known** baud. Avoid brute-force commands that change configuration.

## TEST-02 command sequence

```powershell
py .\DX-BT18\tools\bt18_ble_scan.py --duration 12
```

Copy the actual BLE address/OS identifier from the output only if the user wants GATT enumeration:

```powershell
py .\DX-BT18\tools\bt18_ble_scan.py --address "ACTUAL_DEVICE_IDENTIFIER"
```

## Evidence standard

Use [RESULT_TEMPLATE](RESULT_TEMPLATE.md) for all new result files. Record the date, known hardware, connection diagram, command transcript, detected versions, pass criteria, uncertainty and exact non-claims. Local UART / BLE logs may expose MAC addresses; `results/` is intentionally ignored by Git.

After two or three non-destructive functional attempts fail, record a bounded result and move to another device/task rather than starting a repair investigation.
