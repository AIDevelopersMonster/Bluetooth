# KonSol AT Studio 0.2.0 | KonSol Tools

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
**NAME setter + immediate readback was physically verified** on 2026-10-12;
BAUD, PIN and FLOW writes are **not claimed physically verified**. For safety, FLOW write
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

## Internal incoming inspection registry (v0.2.0)

The program now has a private SQLite inspection registry, modeled on our GPS
Lab database. The GUI offers **Inspect & record** for a fresh full AT
query batch (read-only), plus an **Inspection registry** browser in the
bottom panel. Successful configuration **Apply** operations generate
separate, dated write/readback records when the current module MAC is known.
Each record has its own test scope; overall incoming approval is *not*
inferred from a single PASS. MAC/PIN are kept out of the public repository,
and PIN values are redacted from saved inspection payloads.

Primary file: `%USERPROFILE%\.konsol-tools\inspections.sqlite3`.

See [INSPECTION_REGISTRY.md](INSPECTION_REGISTRY.md) for the GPS-inspired
field mapping, CLI, backup, JSON/CSV/HTML export and historical evidence rules.

Quick local commands: `registry.cmd status`, `registry.cmd list --limit 20`,
`registry.cmd summary`. These work even when the GUI is not running.

## Lab evidence vs implementation

**Software-only checks:**

```powershell
py -m unittest discover -s .\tests -v
```

**Hardware acceptance:** operator GUI screenshots (2026-10-12) demonstrate 8/8
AT reads and a Bluetooth NAME configuration write verified by immediate
readback on a physical BT18-T. Other writes and persistence after power-cycle
remain unverified. The new v0.2.0 **registry integration has software tests
only** until the next bench run; it is not yet a physically accepted release.

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
