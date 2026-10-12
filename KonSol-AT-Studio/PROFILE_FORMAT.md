# Module profile format (`schema_version: 1`)

Every immediate child of `modules/` with a `profile.json` is discovered on
startup and using **Reload module folders**. The `id` must match its folder.
No Python plugin code is loaded; tabs are constructed from these data fields.

## Minimal, read-only module profile

Create `modules/example_module/profile.json`:

```json
{
  "schema_version": 1,
  "id": "example_module",
  "title": "Example / AT UART",
  "baud": 9600,
  "ending": "CRLF",
  "timeout_ms": 650,
  "verified_reads": false,
  "notes": "Unverified example profile. Consult the exact module manual.",
  "queries": [
    {"id": "test", "label": "AT test", "command": "AT"},
    {"id": "name", "label": "Module name", "command": "AT+NAME?", "prefix": "+NAME="}
  ],
  "factory_reset": null
}
```

Use `py main.py --check-profiles` to validate the profile, then press **Reload
module folders**. If the COM port is connected, close it before reloading.

## Explicit writable field

Add an `edit` object *only if the exact module documentation supports it*:

```json
{
  "id": "name",
  "label": "Bluetooth name",
  "command": "AT+NAME?",
  "prefix": "+NAME=",
  "edit": {
    "template": "AT+NAME={value}",
    "pattern": "[A-Za-z0-9_-]{1,18}",
    "risk": "medium",
    "hint": "Change device name. Re-pairing might be needed.",
    "power_cycle": false
  }
}
```

The GUI sends no writes unless **Enable AT WRITES** is checked and the user
confirms the exact AT command. The UART worker then reads the old setting,
sends the write only after a valid reply, requires an `OK` acknowledgement,
and attempts readback verification. Parameters must be single-line ASCII and
match their profile regex and optional `choices` list. Set `"enabled": false`
in the edit section to show a setter that is locked until validation.

## Factory restoration (module-specific, never guessed)

**Do not place this example in either supplied BT18 profile.** The listed
commands for those exact modules do not document a factory-reset operation.

For a *different*, separately verified module, add a factory reset block only
after locating primary documentation and physically verifying the command:

```json
{
  "factory_reset": {
    "command": "AT+FACTORY_COMMAND_FROM_THAT_MODULE_MANUAL",
    "source_url": "https://vendor.example/module-manual",
    "verified_on_hardware": true
  }
}
```

`AT+FACTORY_COMMAND_FROM_THAT_MODULE_MANUAL` is a **placeholder**, not a real
AT command. Replace it with the real, verified documented command. For safety
and uniformity, only simple uppercase `AT` / `AT+TOKEN` reset command tokens
are accepted, and factory reset requires explicit two-step confirmation.

On reset, the GUI first reads all configured query fields into an untracked
local JSON snapshot. If any query lacks a reply, reset is aborted; even a
complete read snapshot is not a guarantee of a recoverable hardware setup.

## Versioning

Each module is isolated. Profiles can be added, removed or updated without
changing the Python GUI/serial core. An incompatible protocol syntax should
use a new schema version and a deliberate core update, not guesswork.
