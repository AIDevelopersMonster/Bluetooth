# JDY-31 — KonSol AT Studio tab

This folder illustrates the *data-only module tab* mechanism. No changes to the Tkinter GUI, main.py, or UART transport are needed.

## Create a new tab

1. Under `KonSol-AT-Studio/modules/`, make a new directory (lowercase ASCII slug).
2. Place `profile.json` inside it with matching `id`.
3. Open PowerShell in `KonSol-AT-Studio`, run `py .\main.py --check-profiles`.
4. Run `py .\main.py`; if already running, CLOSE the UART session and click **Reload module folders**.
5. A new tab is created from the JSON title and query list.

## JDY-31 setup

- 9600 baud, 8N1, CRLF, no flow control; validate these against the actual module.
- Pins on photographed breakout (reverse-side labels): **VCC (3.6–6 V), GND, TXD, RXD**. UART logic is labelled **3.3 V**. Do not connect a 5 V TX output directly to module RXD.
- Use **Read selected** first (`AT+VERSION`). Do not press Inspect & record until module-specific response format and address read have been observed.
- This is a **reference profile**, not a hardware-tested result.
- `AT+VERSION`, `AT+LADDR`, `AT+NAME`, `AT+BAUD` and `AT+PIN` are read-only queries in this tab.
- No setters or factory-reset command are enabled.
- Some JDY-31 firmwares return `+KEY=value\r\n` without an `OK` line. The scoped incoming-inspection evaluator supports this for this profile. Actual response formats may differ between JDY-31 variants.
- PIN values may remain visible in the local GUI/session logs. Avoid publishing screenshots containing PIN or MAC.

## Future profiles

Copy this *folder*, rename its directory and JSON `id`, and replace commands using the target module's **own** manual. See `../../PROFILE_FORMAT.md`. Do not copy JDY-31 commands to unrelated UART/BLE modules. UART defaults, read commands, optional write fields, and supported EOL are declared in JSON; there is no Python plugin execution.

### Source

- JDY-31 manual: https://adastra-soft.com/wp-content/uploads/2021/06/JDY-31_manual_2.pdf
