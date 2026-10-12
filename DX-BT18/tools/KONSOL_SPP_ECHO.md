# Universal SPP UART Echo CLI — KonSol-SPPM laboratory

A lightweight, byte-exact software echo tester for Android **KonSol-SPPM** and other Bluetooth Classic SPP terminals. The PC receives bytes via an existing USB-UART COM port and sends the **same bytes back** through a transparent Bluetooth-UART bridge.

This tester **is not tied to BT18-T**. It can work with other transparent UART bridges when they provide a Bluetooth Classic SPP connection, a compatible UART wiring/configuration and a matching serial speed. Example modules include SPP-capable HC-05/HC-06 and ESP32 Classic SPP implementations. Compatibility must be physically checked; BLE-only modules cannot connect to KonSol-SPPM.

## Requirements

- Windows + Python 3.10+ with `pyserial`; a COM-port USB-UART adapter already connected to an SPP-capable bridge
- Android phone with KonSol-SPPM and the bridge paired in Android settings
- Set UART speed to the module's **actual data-mode speed**; default in our BT18-T laboratory is 9600, 8N1

No firmware upload, AT commands, new jumpers, PC Bluetooth adapter or module reconfiguration are needed.

## Run (PowerShell)

```powershell
cd C:\GitHub\Bluetooth
py -m pip install --user pyserial
py .\DX-BT18\tools\konsol_spp_echo.py --list-ports
py .\DX-BT18\tools\konsol_spp_echo.py --port COM4 --baud 9600
```

Omit `--port` to select a COM port interactively. `--seconds 30` stops automatically after 30 seconds. `--quiet` hides per-chunk diagnostic lines. Otherwise stop with **Ctrl+C**.

Open KonSol-SPPM, select the paired Classic SPP module and connect. Send **TEXT** `PING` with **CRLF** ending. Expected total is six bytes: `50 49 4E 47 0D 0A`.

Example PC log:

```text
RX   #0001 [6 B] TEXT='PING\\r\\n' HEX=50 49 4E 47 0D 0A
ECHO #0001 [6 B] TEXT='PING\\r\\n' HEX=50 49 4E 47 0D 0A
```

The Android RX log should show an identical return. Also try HEX `00 FF 55 AA` with HEX-mode RX display. The tester adds **no** prefix, line ending or encoding, and handles partial COM writes.

**Caution:** UART and RFCOMM are byte streams. A PC read chunk is not a guaranteed complete command. TX/RX entries may be split across multiple log records; concatenate the bytes when comparing. A terminal's own TX entry alone is not proof of end-to-end delivery.

**Result classification:** Python unit checks validate echo logic only. Physical PASS requires observing the returned bytes in the phone's RX journal. No physical echo PASS is claimed by this document.

## Related application

[KonSol-SPPM](../../KonSol-SPPM/README.md) is a **universal Bluetooth Classic SPP terminal**, not a vendor-specific BT18 application. It connects using the standard SPP UUID `00001101-0000-1000-8000-00805F9B34FB`, selects among paired devices, offers TEXT/HEX TX, selectable line endings, RX journal and user-programmable M1–M8 buttons. It does **not** support BLE GATT or selectable custom service UUIDs. The physically opened/installed Android baseline is **v0.1.2** in branch `baseline/konsol-sppm-v0.1.2-redmi`.

## Run the software-only checks

```powershell
py -m unittest discover -s .\DX-BT18\tools -p test_konsol_spp_echo.py -v
```
