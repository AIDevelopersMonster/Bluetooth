# DX-BT18 / BT18-T — TEST-02B GATT connection attempt

**Date:** 12 October 2026  
**Status:** **NOT CONFIRMED — GATT connect/enum TIMEOUT**, not Bluetooth module FAIL.  
**Source:** terminal output provided by the hardware owner.

## Actual command and observed outcome

```powershell
cd C:\GitHub\Bluetooth
py -3.14 .\DX-BT18\tools\bt18_ble_scan.py --duration 8 --name BT18-T --address "98:DA:F0:00:EE:27" --connect-timeout 25
```

Console reported:
```text
BLE scan: 8s (NOT Classic SPP)
Name: BT18-T
BLE address/OS identifier: 98:DA:F0:00:EE:27
RSSI: -79 dBm
Advertised service UUIDs: 0000ffe0-0000-1000-8000-00805f9b34fb
Manufacturer data IDs: 0x0000
Devices matching filter: 1
Connecting to discovered BLEDevice '98:DA:F0:00:EE:27' (GATT timeout: 25s)...
GATT CONNECT TIMEOUT: connection/services enumeration not confirmed. Previously observed BLE advertising remains PASS.
```

**Grounded result:** Windows BLE adapter functioned and BLE advertisement from `BT18-T` with `FFE0` was received; after 25-second bounded attempt the GATT connection plus services enumeration was not completed. No `Connected: True` appeared and `FFE1`/`FFE2` have NOT been enumerated. No GATT values were read/written; no AT write and no firmware operations.

Prior BLE tests had established repeated discovery at RSSI -79, -87 and -82 dBm. A previous Windows WinRT `NO_BLUETOOTH` episode was a separate host-side pre-scan issue, **not** the present failure.

## Mode hypothesis from original DX-SMART manual — not yet proved for this clone

Original DX-BT18 datasheet, P26/GPIO25:

| Pin condition | Original module mode |
| --- | --- |
| `P26 -> GND` | AT commands |
| `P26 = NC` (open) | Transparent data mode |

[Original DX-BT18 technical manual](https://manuals.plus/m/b2042a61df3340ba1f528646b16efdf3d786b18f2edb66204799996c10bea264).

The owner previously reported a successful 8/8 AT test at 9600 with **EN tied to GND** and **button not pressed**. It is **not established** that this unmarked board's pad labelled `EN` is identical to the original module's P26, nor was the electrical state of EN independently logged during the BLE scan.

Nevertheless, an AT-only versus transparent-data mode difference is a **plausible** explanation for GATT connection timing out while BLE advertisement is visible. Do not call the module defective based on this test.

## One functional next check: exit the suspected AT-control mode

Only if the owner wishes to test the transparent-data hypothesis:

1. **Power off the Bluetooth module.**
2. **Disconnect the EN-to-GND connection** (do not short EN to VCC or to any other signal); leave VCC, GND, TX and RX unchanged. Do not press the button.
3. Repower; make one brief **discovery** run:
   ```powershell
   py -3.14 .\DX-BT18\tools\bt18_ble_scan.py --duration 8 --name BT18-T
   ```
4. **Only if advertised and if testing GATT is still warranted:** one attempt at GATT connection, with the actually discovered Windows BLE identifier:
   ```powershell
   py -3.14 .\DX-BT18\tools\bt18_ble_scan.py --duration 8 --name BT18-T --address "98:DA:F0:00:EE:27" --connect-timeout 25
   ```
   Replace the address if the Windows identifier changes. Do **not** repeat GATT with unchanged conditions after another timeout.

If no BLE advertising appears after removing EN-to-GND, this alone does not prove failure; record the condition and restore the documented working configuration with power off. No soldering or random short-circuiting. For the next work item, test a Classic SPP / transparent UART data path independently and with confirmed mode wiring.

## Evidence limits

**PASS:** TEST-02A advertising, repeated; TEST-01 UART AT 8/8.  
**NOT CERTIFIED:** TEST-02B connection and GATT characteristic enumeration, `FFE1/FFE2`, GATT transfer, Classic SPP / UART transparency.  
**Unknown:** pin EN true function on clone, button purpose, cause of timeout, silicon origin.

Related: [TEST-02A discovery](TEST-02_BLE_DISCOVERY_2026-10-12.md), [TEST-01 UART](TEST-01_AT_UART_RESULT_2026-10-12.md), [test plan](TEST_PLAN.md).
