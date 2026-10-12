# Bluetooth — KON Bluetooth Lab

Independent laboratory for Bluetooth modules, UART bridges, BLE/GATT and reproducible interface experiments.

## Modules

- [DX-BT18 / BT18-T](DX-BT18/README.md) — UART/AT testing and Bluetooth interface investigation. [TEST-01 UART/AT physical result](DX-BT18/tests/TEST-01_AT_UART_RESULT_2026-10-12.md).

## Software

- [KonSol-SPPM](KonSol-SPPM/README.md) — Android Bluetooth Classic SPP terminal, TEXT/HEX exchange and eight user-configurable command buttons.
- [KonSol-SPPM Android build](.github/workflows/konsol-sppm-android.yml) — build a debug APK from source through GitHub Actions.

## Windows CLI setup

If Git is not installed, install it from [Git for Windows](https://git-scm.com/install/windows). Then in PowerShell:

```powershell
New-Item -ItemType Directory -Force C:\GitHub | Out-Null
cd C:\GitHub
git clone https://github.com/AIDevelopersMonster/Bluetooth.git
cd Bluetooth
py -m pip install --user -r .\DX-BT18\tools\requirements.txt
py .\DX-BT18\tools\bt18_probe.py --list-ports
```

For an existing clone: `git pull --ff-only`.

This repository contains reusable source code, documented interfaces and meaningful test results. Transient support diagnostics are kept out of the published project.
