# KonSol AT Studio 0.1.0 | KON Tools

A small native **Windows GUI AT terminal/configurator**, based on the UART AT inquiry
protocol already used by KON Bluetooth Lab's `DX-BT18/tools/bt18_probe.py`.
It does not embed module-specific logic into the GUI: **one module folder with a
`profile.json` file creates one tab**. Only Python, Tkinter (included with normal
Windows Python) and `pyserial` are required. No Arduino, firmware upload, web browser
or other GUI framework is needed.

## Launch on Windows (PowerShell)

Unzip the project anywhere, open PowerShell in the extracted `KonSol-AT-Studio`
folder (or double-click `start.cmd`):

```powershell
py --version
py -m pip install --user -r .\requirements.txt
py .\main.py
```

For an isolated profile-only validation (no GUI or COM adapter needed):

```powershell
py .\main.py --check-profiles
```

## First physical test: BT18-T

1. Keep the USB-UART hardware as already tested: CH340 on `COM4`, 9600 8N1,
   existing EN/AT-mode state. No new jumpers or rewiring are required.
2. Disconnect KonSol-SPPM on Android before accessing AT configuration.
3. Run the GUI, select **BT18-T / DX-BT18**, COM4, 9600, then press **OPEN**.
4. Click **Read ALL**. The eight queries should reproduce the previous successful
   read-only CLI inquiry set. A profile's first use should be **read only**.
5. Click **Save snapshot JSON** to save the configuration locally before changes.
6. To change *documented settings* such as device name, check **Enable AT WRITES**,
   enter the new value and press **Apply**, then confirm the exact outgoing AT line.
   The tool automatically reads that field before writing, requires `OK`, and tries
   a readback afterward. An `OK` acknowledgement alone is not proof of persistence.
7. If the UART baud index is changed, the hardware may require a power cycle and
   the PC COM speed must be updated before further communication.

Never run the echo CLI, `bt18_probe.py` or another serial monitor simultaneously
on the same COM port. This GUI owns the port until **CLOSE**.

### BT18-T commands and known boundaries

The verified 8/8 read-only AT commands are:

`AT+TEST`, `AT+VERS?`, `AT+ADSS?`, `AT+NAME?`, `AT+BAUD?`,
`AT+PIN?`, `AT+UUID?`, `AT+FLOW?`.

The original module manual documents setters for NAME, BAUD, PIN and FLOW.
They are **not claimed physically verified by the lab**. For safety, FLOW write
is disabled in the initial profile because enabling hardware flow control without
RTS/CTS can make UART communications unavailable. UUID and Bluetooth address
writes are also excluded from this first version. No commands are sent on GUI
startup, on opening a COM port, or on changing tabs.

The BT18-LE tab is **documentation-based only**. No tested BT18-LE hardware is claimed,
and BT18-LE is *not* compatible with the Classic-SPP-only KonSol-SPPM Android app.

Reference: [Original DX-BT18 / BT18-LE technical manual](https://manuals.plus/m/b2042a61df3340ba1f528646b16efdf3d786b18f2edb66204799996c10bea264).

## How to add a module = how to add a tab

Create a new folder and add a validated JSON file:

```text
KonSol-AT-Studio/
  main.py
  konat/                shared GUI + serial/protocol implementation
  modules/
    bt18_dual/
      profile.json      -> "BT18-T / DX-BT18" tab
    bt18_le/
      profile.json      -> "BT18-LE" tab
    my_next_module/
      profile.json      -> new tab on startup / Reload module folders
  tests/
  snapshots/            automatically generated, NEVER committed
```

The JSON controls the displayed title, default UART baud/ending, AT inquiry
commands, expected reply prefix, optional validated edit controls and optional
factory-reset action. See [PROFILE_FORMAT.md](PROFILE_FORMAT.md) for a minimal
profile and command restrictions. Folders contain **data only**: no imported or
executed Python plugins.

## Factory reset button

Every tab has a **Factory defaults** section. For the supplied BT18-T and
BT18-LE profiles its button is **disabled**, because their matching documented
AT command lists contain **no confirmed full factory-restore command**. Do not
copy `AT+DEFAULT`, `AT+RESET`, `AT+ORGL` or `AT+RESTORE` from unrelated module
manuals. Restarting a module is also **not the same** as factory restoration.

The button becomes operational for a new profile *only* when the profile
explicitly supplies a factory-reset command, a primary source reference and
`verified_on_hardware: true`. In that case it requires enabling AT writes, two
user confirmations (including typing `RESET`) and it stores a **complete** local
pre-reset snapshot. If a read fails during this snapshot, the reset command is
NOT SENT. After a reset, the user must verify settings and pairing manually.

## Lab evidence vs implementation

**Software-only checks:**

```powershell
py -m unittest discover -s .\tests -v
```

**Hardware acceptance:** NOT YET PERFORMED for the new GUI. For this module,
previous `bt18_probe.py` read-only test reported 8/8 physical replies with CH340
at COM4/9600. The GUI still requires a fresh physical test.

## Privacy and security

- The app does not access the network or send telemetry.
- Local snapshots and the session log may contain a Bluetooth address and PIN.
  Treat these as private, and do not upload them to public GitHub issues.
- The `snapshots/` directory is excluded by `.gitignore`.
- `profile.json` cannot load arbitrary Python code; it can define AT commands to
  send, so use only module profiles you trust.
- Read/Write/Factory actions are exclusive on a single worker thread; UI remains responsive.
- Never store passwords, SSH keys, signing keystores or API tokens in profiles.

**Scope:** UART AT configuration of compatible modules, not firmware flashing,
SWD/JTAG or arbitrary-chip-memory access.
