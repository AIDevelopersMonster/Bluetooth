# Bluetooth — KON Bluetooth Lab

Independent laboratory for Bluetooth modules, UART bridges, BLE/GATT studies and repeatable device identification.

## Modules

- [DX-BT18 / BT18-compatible (unmarked sample)](DX-BT18/README.md) — AT identification, BLE scan, GATT inspection and cautious firmware feasibility audit; tests PENDING.

## Windows quick start

If Git is not installed: `winget install --id Git.Git -e --source winget`, then open a new PowerShell.

```powershell
New-Item -ItemType Directory -Force C:\GitHub | Out-Null
cd C:\GitHub
git clone https://github.com/AIDevelopersMonster/Bluetooth.git
cd Bluetooth
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\DX-BT18\tools\requirements.txt
.\.venv\Scripts\python.exe .\DX-BT18\tools\bt18_probe.py --list-ports
```

Existing clones: `cd C:\GitHub\Bluetooth; git pull --ff-only`.

The lab is separate from Arduino-UNO-Shields. Never assume bench PASS before hardware verification.
