# Bluetooth — KON Bluetooth Lab

Independent laboratory for Bluetooth modules, UART bridges, BLE/GATT studies and repeatable device identification.

## Modules

- [DX-BT18 / BT18-T — archived identification lab](DX-BT18/README.md) — **CLOSED / NOT CERTIFIED** for the unmarked tested samples. Original marked units had worked well for the owner; these specimens did not yield usable AT access. Historical documentation and read-only scripts are retained.

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

The lab is separate from Arduino-UNO-Shields. **No venv is needed**: use the installed Windows Python via `py`. Dependencies are installed in the user's Python environment with `--user`. Testing of the current unmarked DX-BT18 specimens is CLOSED / NOT CERTIFIED, not a PASS.
