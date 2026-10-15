# JDY-31A V2.241 laboratory reference

Physical identification (15 Oct 2026, UART): `+VERSION=JDY-31A-V2.241,Bluetooth V3.0+BLE`; default UART 9600 8N1 CRLF; `+BAUD=4`; address read through `AT+LADDR`. Name request answered `+NAME=?`; **do not treat '?' as a certified device name**. PIN was read but should not be published.

## Command evidence classes

- **Measured on this firmware:** AT+VERSION, AT+LADDR, AT+NAME, AT+BAUD, AT+PIN. These five are the **Read core / Inspect** set. No setters.
- **Candidates for manual, opt-in investigation:** AT, AT+ENLOG, AT+STAT, AT+NAMB, AT+TYPE, AT+UUIDLEN, AT+SVRUUID, AT+CHRUUID, AT+CRXUUID, AT+UARTMODE, AT+STTS. Candidate syntax is drawn from related-module documents and must **not** be interpreted as a verified JDY-31A V2.241 command list. Their actions may differ across firmwares; do not bulk transmit. GUI prompts before an individual experimental query.
- **Forbidden in this profile:** configuration setters, factory reset, AT+RESET, AT+DISC, AT+SLEEP.

The older JDY-31 manual lists fewer commands; **it does not fully document this firmware**. Related JDY-33 documents help form hypotheses but are not proof.

## Local PDFs

Run `./download-references.ps1` in PowerShell from this directory. Files go to **untracked** `references/` beside this README; a matching `.source.json` records the URL and SHA-256. They are deliberately excluded from Git to avoid republishing vendor copyrighted PDFs and to avoid asserting an exact firmware match. If a vendor URL is unreachable, the script reports failure; it never treats an HTML error page as a PDF.

Sources:
- Legacy JDY-31 PDF: https://adastra-soft.com/wp-content/uploads/2021/06/JDY-31_manual_2.pdf
- Related JDY-33 FCC manual: https://fccid.io/2AXM8-JDY-33/User-Manual/15-JDY-33-UserMan-US-r2-4936883.pdf

## Protocol note

`Read core`, snapshots and SQLite incoming inspections **ignore opt-in probes** so unsupported commands cannot generate false FAIL statuses. `+NAME=?` is treated as an unknown value in inspection scoring; neither a valid name nor a passed name check is claimed.

Do not publish session logs, inspection database, real device MACs or pairing PINs.
