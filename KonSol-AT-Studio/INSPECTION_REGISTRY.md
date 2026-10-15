# KonSol Tools: Bluetooth module inspection register (v0.2.0)

This is a **private technical incoming-inspection source register**, modeled on
GPS Lab's `~/.gpslab/gpslab.sqlite3` and its `gps-registry` CLI. The Bluetooth
primary store is separate for now:

```text
%USERPROFILE%\.konsol-tools\inspections.sqlite3
```

An inspection is **append-only**. Another inspection of the same module-reported
MAC produces another dated record; it never erases a previous result.

## Data model and evidence boundary

- `modules`: stable local number `BT-YYYY-NNNNN`, raw reported six-byte MAC,
  AT address command source (e.g., `AT+ADSS?`), first-seen date, profile.
- `inspections`: record UUID, linked module, `tested_on` (date), optional
  `tested_at_utc`, automatic `recorded_at_utc`, test profile, test code,
  PASS/FAIL/INCOMPLETE, evidence source/reference, scoped diagnostic JSON.
- `incoming_acceptance = NOT_EVALUATED`: a successful UART/AT test is **not**
  evidence that the equipment passed the complete incoming acceptance program.
- `factory_id = null` on the common export: a configurable AT-reported MAC is
  **not** an authenticated factory serial number.
- The MAC is a **provisional identifier**, not a guarantee of uniqueness,
  permanence or authenticity. Duplicate MACs on separate modules cannot yet be
  distinguished; such modules require a future local label/serial/photo workflow.
- PIN/password values and PIN raw response bytes are **redacted** before
  saving an inspection, even in the private SQLite DB. Local session logs and
  separately saved raw snapshots may still contain these values.

`tested_at_utc` is only set for a fresh, software-timestamped online test.
Historic screenshots have a known date but uncertain time-zone; their
`tested_at_utc` is NULL instead of a fabricated timestamp. `recorded_at_utc`
is the moment evidence was inserted into the registry, **not** the past test time.

## Physical workflow (KonSol AT Studio)

1. Select the matching `modules/<name>/profile.json` tab.
2. Connect COM4 at 9600 (or the actual serial rate) in the module's existing
   working AT mode. No rewiring or firmware operation is required.
3. Click **Inspect & record** in the module tab. The program executes fresh
   read-only queries, checks their responses, reads a complete MAC and creates
   one local SQLite inspection. It **does not** write module settings.
4. Use **Inspection registry** at the bottom of the window to search by MAC,
   inspect history, export JSON/CSV/HTML or take a consistent SQLite backup.
5. A confirmed **Apply** operation records a separate write/readback result
   automatically. It first reads the current module-reported MAC and will not
   perform an untraceable write if the address inquiry fails.

No entry is recorded for a screenshot that has not been explicitly imported,
and pressing **Read ALL** alone remains a non-persistent screen operation.

## Registry CLI (Windows PowerShell)

From the extracted `KonSol-AT-Studio` folder:

```powershell
py -m konat.registry_cli status
py -m konat.registry_cli list --limit 20
py -m konat.registry_cli find --mac 02A1B2C3D4E5
py -m konat.registry_cli show 1
py -m konat.registry_cli summary
py -m konat.registry_cli export-json .\local-inspection-export.json
py -m konat.registry_cli export-csv .\local-inspection-export.csv
py -m konat.registry_cli report .\local-inspection-report.html
py -m konat.registry_cli backup .\local-inspection-backup.sqlite3
```

Import historical screenshot evidence into an existing local database (idempotent;
does not overwrite newer inspections):

```powershell
py -m konat.registry_cli import-history .\private-evidence\historical-bt18-20261012.json
```

A private database can be inspected without changing the Windows registry
by adding `--database path` **before** the subcommand:

```powershell
py -m konat.registry_cli --database .\sample.sqlite3 status
```

Treat SQLite/JSON/CSV/HTML exports as private: they contain device addresses and
possibly locally identifying evidence references. Do not commit them to GitHub.
The source archive ships **without** an internal device database.

## Compatibility bridge for a future universal incoming control system

The JSON export uses `schema: kon-incoming-inspection/v1`. Each record retains
GPS Lab-compatible field names (`module_code`, `factory_id`, `identity_source`,
`tested_at_utc`, `profile`, `result`, plus `payload`) and adds:

- `equipment_category: bluetooth_uart`;
- `reported_mac` and `identity_assurance`;
- `test_code` and separate `incoming_acceptance`;
- `tested_on` and `recorded_at_utc` provenance;
- `evidence_source` / `evidence_ref`.

The universal QC importer can ingest exports from GPS and KonSol AT Studio and
map module numbers into a master equipment registry. **Do not combine source
SQLite files by direct table merging.** Their schemas and identity policies
differ; the common interchange format is the tested integration boundary.

## GPS lineage / differences

| GPS Lab registry | KonSol AT Studio registry |
| --- | --- |
| `~/.gpslab/gpslab.sqlite3` | `~/.konsol-tools/inspections.sqlite3` |
| GPS6-YYYY-NNNNN / receiver factory ID | BT-YYYY-NNNNN / module-reported MAC |
| NMEA/UBX time and identity | UART AT replies and reported MAC |
| JSON/CSV/HTML and SQLite backup | JSON/CSV/HTML and SQLite backup |
| GPS functional profile test result | Bluetooth scoped AT read/write test result |
| Single inspection can be refreshed for a factory ID | New inspection row on **every** test, preserving history |

## Historical evidence, 12 October 2026

The lab operator physically observed:

- **BT18-READ-01**, 8/8 AT queries on BT18-T (CH340 COM4, 9600 8N1).
- **BT18-WRITE-01**, `AT+NAME=TEST-GUI` with immediate
  `AT+NAME?` readback matching `TEST-GUI`; old name `HC-06`.

These results are dated **2026-10-12**; we do not invent a timezone-specific
instant or claim name persistence after power-cycle. A **private** separate
starter SQLite registry can store these historical screenshots with the
actual observed MAC, but it must not be uploaded to the public project.


## Configuration snapshots in both SQLite and JSON

The **Save snapshot JSON** command is now a live UART read, not only a file operation.
It writes a private, timestamped, PIN-redacted JSON in \`snapshots/\` and appends
an \`AT_CONFIG_SNAPSHOT_V1\` inspection to the existing SQLite registry *when the
module reports a valid six-byte MAC*. No database migration is required.
The evidence reference points to the local JSON path; JSON is still retained
as an independent file for review and recovery.

If the MAC cannot be read, the JSON is kept, but no SQLite inspection is
attributed to an unknown module. A partial query set is saved as
\`INCOMPLETE\`/\`FAIL\`, never relabelled as PASS. Neither a snapshot nor a
successful AT query constitutes total incoming acceptance.

PIN values and raw PIN reply bytes are redacted from the **newly generated**
JSON snapshots and inspection records. Older snapshots might still contain
plaintext PINs. Before sharing or archiving earlier snapshots, inspect them
privately. The original SQLite file is preserved, and records are append-only.

## Stock registration policy (revised 2026-10-15)

The SQLite registry is for explicitly registered, successfully tested supplied modules, **not** an experimental log. Read core, setting changes via Apply, factory restore, software restart, and Save snapshot JSON must never auto-register an item. Factory restore operates even when the current configuration fails validation, without creating a database record. The explicit **Register checked module** action performs a fresh full AT inspection and records only a PASS result with a valid module-reported MAC. No FAIL/INCOMPLETE stock rows are created. JSON snapshots are local scratch files and have no database side-effect. Legacy existing records remain intact; no automatic purge occurs. Because old rows may include experimental outcomes, any cleanup must be separately reviewed rather than guessed or automatically performed.
