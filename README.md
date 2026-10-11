# Bluetooth — KON Bluetooth Lab

Independent laboratory for Bluetooth modules, UART bridges, BLE/GATT studies and repeatable device identification.

## Modules

- [DX-BT18 / BT18-T](DX-BT18/README.md) — **ACTIVE, TEST-01 UART/AT FULL PASS (2026-10-12)**. Real CH340 COM4 exchange at 9600 baud: **8/8 AT queries answered**, firmware reported `V3.01`, name `BT18-T`. Chip authenticity and Bluetooth payload transfer remain unverified. [Read the certified test record](DX-BT18/tests/TEST-01_AT_UART_RESULT_2026-10-12.md).

## KonSol-SPPM — Android Classic SPP console

- [KonSol-SPPM v0.1.1 — Android 7.0+](KonSol-SPPM/README.md) — paired Classic SPP/RFCOMM, RX/TX terminal, TEXT/HEX, 8 configurable command buttons, shareable logs.
- [GitHub Actions APK build](.github/workflows/konsol-sppm-android.yml): choose the successful **v0.1.1 Android7** artifact. Earlier v0.1 builds required Android 8 and cannot install on Android 7. Hardware SPP exchange remains unverified.
- The Windows BLE/GATT test is closed as inconclusive; this mobile app tests **Classic SPP**, not BLE.

## Windows quick start

If Git is not installed: `winget install --id Git.Git -e --source winget`, then open a new PowerShell.

```powershell
New-Item -ItemType Directory -Force C:\GitHub | Out-Null
cd C:\GitHub
git clone https://github.com/AIDevelopersMonster/Bluetooth.git
cd Bluetooth
py --version
py -m pip install --user -r .\DX-BT18\tools\requirements.txt
py .\DX-BT18\tools\bt18_probe.py --list-ports
```

Existing clones: `cd C:\GitHub\Bluetooth; git pull --ff-only`.

The lab is separate from Arduino-UNO-Shields. **No venv is needed**: use the installed Windows Python via `py`. Dependencies are installed in the user's Python environment with `--user`. TEST-01 has a physical FULL PASS for the reported read-only UART/AT exchange; all other hardware functions remain separately unverified.
