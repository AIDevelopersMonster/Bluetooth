# JDY-31A V2.241: UART/SPP configuration

Physical evidence: AT+VERSION, AT+LADDR, AT+NAME, AT+BAUD and AT+PIN all read on this module. The old +NAME=? was a stored value, later +NAME=JDY-31. The NAME setter is **physically verified** on 15 Oct 2026: original `JDY-31` -> `AT+NAMEKON-BT31` -> `+OK` -> immediate `+NAME=KON-BT31`; subsequent same-session read also matched. Local SQLite inspection #22 is PASS for scope AT_WRITE_READBACK_V1. Persistence after a full power-cycle is **not verified**. PIN and BAUD writes remain **untested**.

This profile intentionally exposes only five UART commands. The candidate BLE/related-model commands have been removed; BLE GATT is a different transport/connection mode and should be developed and validated separately, not confused with UART AT.

The legacy JDY-31 manual documents setting name, PIN and baud using AT+NAME{value}, AT+PIN{value}, AT+BAUD{index}, without =. These are provisionally enabled with firmware gate JDY-31A-V2.241, current-value pre-read, explicit confirmation and response checking. Baud change is pending a power-cycle and host baud adjustment, not automatically verified.

NAME write/readback is now hardware-verified. For PIN and BAUD, use separate controlled tests with rollback plans, and do not infer their success from the NAME test.

## Local documentation

Run .\download-references.ps1 in PowerShell. The local references/ directory is gitignored, and each PDF gets a .source.json provenance record. These documents relate to older JDY-31 and JDY-33, not a confirmed manufacturer datasheet for V2.241.

Sources:
- https://adastra-soft.com/wp-content/uploads/2021/06/JDY-31_manual_2.pdf
- https://fccid.io/2AXM8-JDY-33/User-Manual/15-JDY-33-UserMan-US-r2-4936883.pdf
