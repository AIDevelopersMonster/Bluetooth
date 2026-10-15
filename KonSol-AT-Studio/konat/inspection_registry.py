"""Private KonSol Tools inspection registry; SQLite source of truth.

Similarity to GPS Lab registry is intentional: module_code, factory_id,
identity_source, tested_at_utc, result, profile and diagnostic JSON are kept.
Unlike the initial GPS table, an inspection is append-only, never overwritten.
A MAC read from an AT-capable module is a provisional identifier, not proof
that an address is unique, immutable or burned into silicon.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import html
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = 1
DEFAULT_DB = Path.home() / ".konsol-tools" / "inspections.sqlite3"
STATUS = {"PASS", "FAIL", "INCOMPLETE"}
SOURCE_TYPES = {"live_uart", "historical_screenshot", "manual_import"}
IDENTITY_RULE = "device_reported_mac_not_unique_proof"
MAC_RX = re.compile(r"[0-9A-F]{12}\Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_mac(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("The module address must be text")
    mac = re.sub(r"[:-]", "", value).strip().upper()
    if not MAC_RX.fullmatch(mac):
        raise ValueError("Expected a complete six-byte MAC (12 hex digits)")
    if mac in {"000000000000", "FFFFFFFFFFFF"}:
        raise ValueError("All-zero/all-FF addresses cannot identify a tested module")
    return mac


def _validate_date(day: str) -> str:
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("Use YYYY-MM-DD for the local observed date")
    return day


def _validate_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None or t.utcoffset().total_seconds() != 0:
        raise ValueError("tested_at_utc must be UTC with Z suffix")
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_payload(value: Any, key: str = "") -> Any:
    """Do not retain UART replies or parameter values exposing pairing PINs."""
    if any(x in key.lower() for x in ("pin", "password", "secret", "token", "pairing_code")):
        return "[REDACTED]"
    if isinstance(value, dict):
        # When a PIN query is present, redact the query's returned raw bytes too.
        if str(value.get("qid", value.get("id", ""))).lower() in {"pin", "pairing_pin"}:
            return {k: ("[REDACTED]" if k in {"value", "old", "new", "actual", "response_text", "response_hex", "reply", "reply_hex"} else _safe_payload(v, k))
                    for k, v in value.items()}
        return {str(k): _safe_payload(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_payload(x) for x in value]
    if isinstance(value, tuple):
        return [_safe_payload(x) for x in value]
    if isinstance(value, bytes):
        return {"hex": value.hex().upper()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def ensure_db(path: Path = DEFAULT_DB) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        current_version = con.execute("PRAGMA user_version").fetchone()[0]
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(f"Registry schema {current_version} is newer than supported {SCHEMA_VERSION}")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT UNIQUE NOT NULL,
                reported_mac TEXT UNIQUE NOT NULL,
                identity_source TEXT NOT NULL,
                identity_assurance TEXT NOT NULL,
                first_profile TEXT NOT NULL,
                first_seen_on TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_uid TEXT NOT NULL UNIQUE,
                module_id INTEGER NOT NULL REFERENCES modules(id),
                tested_on TEXT NOT NULL,
                tested_at_utc TEXT,
                recorded_at_utc TEXT NOT NULL,
                profile TEXT NOT NULL,
                test_code TEXT NOT NULL,
                result TEXT NOT NULL,
                acceptance_status TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
                evidence_source TEXT NOT NULL,
                evidence_ref TEXT,
                board TEXT,
                receiver TEXT,
                sw_version TEXT,
                hw_version TEXT,
                port TEXT,
                baud INTEGER,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_inspections_module ON inspections(module_id, id);
            CREATE INDEX IF NOT EXISTS idx_inspections_date ON inspections(tested_on, id);
            CREATE INDEX IF NOT EXISTS idx_inspections_result ON inspections(result, profile);
        """)
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return path


def db_status(path: Path = DEFAULT_DB) -> dict:
    path = Path(path).expanduser()
    summary = {"path": str(path), "exists": path.is_file(), "modules": 0,
               "inspections": 0, "schema_version": None}
    if not path.is_file():
        return summary
    with sqlite3.connect(path) as con:
        summary["schema_version"] = con.execute("PRAGMA user_version").fetchone()[0]
        summary["modules"] = con.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
        summary["inspections"] = con.execute("SELECT COUNT(*) FROM inspections").fetchone()[0]
    return summary


def _next_code(con: sqlite3.Connection, on: str) -> str:
    year = on[:4]
    # The row id order is authoritative, even if older records were imported later.
    rows = con.execute("SELECT module_code FROM modules WHERE module_code LIKE ?", (f"BT-{year}-%",))
    used = [int(r[0].rsplit("-", 1)[1]) for r in rows if r[0].rsplit("-", 1)[1].isdigit()]
    return f"BT-{year}-{max(used, default=0)+1:05d}"


def add_inspection(*, mac: str, profile: str, test_code: str, result: str,
                   payload: dict, tested_on: str, identity_source: str = "AT+ADSS?",
                   tested_at_utc: str | None = None, evidence_source: str = "live_uart",
                   evidence_ref: str | None = None, board: str | None = None,
                   receiver: str | None = None, sw_version: str | None = None,
                   hw_version: str | None = None, port: str | None = None,
                   baud: int | None = None, inspection_uid: str | None = None,
                   db_path: Path = DEFAULT_DB) -> dict:
    mac = normalize_mac(mac)
    tested_on = _validate_date(tested_on)
    tested_at_utc = _validate_timestamp(tested_at_utc)
    if result not in STATUS:
        raise ValueError(f"Invalid result: {result}")
    if evidence_source not in SOURCE_TYPES:
        raise ValueError("Unknown evidence source")
    if not isinstance(payload, dict) or not profile or not test_code or not identity_source:
        raise ValueError("A profile, test code, identity source and payload are required")
    uid = inspection_uid or str(uuid4())
    safe_json = json.dumps(_safe_payload(payload), ensure_ascii=False, sort_keys=True)
    db_path = ensure_db(db_path)
    now = utc_now()
    with sqlite3.connect(db_path, timeout=10) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id, module_code FROM modules WHERE reported_mac=?", (mac,)).fetchone()
        if row is None:
            code = _next_code(con, tested_on)
            con.execute("INSERT INTO modules (module_code, reported_mac, identity_source, identity_assurance, first_profile, first_seen_on, created_at_utc) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (code, mac, identity_source, IDENTITY_RULE, profile, tested_on, now))
            module_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            module_id, code = row
        con.execute("""
            INSERT OR IGNORE INTO inspections
            (inspection_uid, module_id, tested_on, tested_at_utc, recorded_at_utc,
             profile, test_code, result, evidence_source, evidence_ref, board, receiver,
             sw_version, hw_version, port, baud, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, module_id, tested_on, tested_at_utc, now, profile, test_code,
              result, evidence_source, evidence_ref, board, receiver, sw_version,
              hw_version, port, baud, safe_json))
        if con.execute("SELECT changes()").fetchone()[0] != 1:
            raise ValueError("Duplicate inspection_uid; inspection was not inserted")
        iid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": iid, "module_code": code, "reported_mac": mac, "inspection_uid": uid,
            "result": result, "database": str(db_path)}


def query_inspections(*, mac: str | None = None, module: str | None = None,
                      result: str | None = None, limit: int = 100,
                      db_path: Path = DEFAULT_DB) -> list[dict]:
    path = Path(db_path).expanduser()
    if not path.is_file():
        return []
    where, params = [], []
    if mac:
        where.append("m.reported_mac = ?")
        params.append(normalize_mac(mac))
    if module:
        where.append("m.module_code LIKE ?")
        params.append(f"%{module}%")
    if result:
        if result not in STATUS:
            raise ValueError("Unknown test result")
        where.append("i.result = ?")
        params.append(result)
    sql = """SELECT i.id, i.inspection_uid, m.module_code, m.reported_mac,
                    m.identity_source, m.identity_assurance, i.tested_on,
                    i.tested_at_utc, i.recorded_at_utc, i.profile,
                    i.test_code, i.result, i.acceptance_status,
                    i.evidence_source, i.evidence_ref, i.board, i.receiver,
                    i.sw_version, i.hw_version, i.port, i.baud
             FROM inspections i JOIN modules m ON m.id = i.module_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY i.id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 1000000)))
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(sql, params)]


def get_inspection(inspection_id: int, db_path: Path = DEFAULT_DB) -> dict | None:
    path = Path(db_path).expanduser()
    if not path.is_file():
        return None
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("""SELECT i.*, m.module_code, m.reported_mac,
                                    m.identity_source, m.identity_assurance
                             FROM inspections i JOIN modules m ON m.id=i.module_id
                             WHERE i.id=?""", (inspection_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def registry_summary(db_path: Path = DEFAULT_DB) -> dict:
    stats = db_status(db_path)
    result = {"database": stats, "results": {}, "profiles": {}, "last_tested_on": None}
    if not stats["exists"]:
        return result
    with sqlite3.connect(db_path) as con:
        result["results"] = dict(con.execute("SELECT result, COUNT(*) FROM inspections GROUP BY result"))
        result["profiles"] = dict(con.execute("SELECT profile, COUNT(*) FROM inspections GROUP BY profile"))
        result["last_tested_on"] = con.execute("SELECT MAX(tested_on) FROM inspections").fetchone()[0]
    return result


def export_json(output: Path, db_path: Path = DEFAULT_DB) -> Path:
    items = []
    for row in reversed(query_inspections(limit=1000000, db_path=db_path)):
        detail = get_inspection(row["id"], db_path=db_path)
        items.append({"record_id": detail["inspection_uid"], "module_code": detail["module_code"],
                      "equipment_category": "bluetooth_uart", "factory_id": None,
                      "reported_mac": detail["reported_mac"],
                      "identity_source": detail["identity_source"],
                      "identity_assurance": detail["identity_assurance"],
                      "tested_on": detail["tested_on"], "tested_at_utc": detail["tested_at_utc"],
                      "recorded_at_utc": detail["recorded_at_utc"],
                      "profile": detail["profile"], "test_code": detail["test_code"],
                      "result": detail["result"], "incoming_acceptance": detail["acceptance_status"],
                      "board": detail["board"], "receiver": detail["receiver"],
                      "sw_version": detail["sw_version"], "hw_version": detail["hw_version"],
                      "evidence_source": detail["evidence_source"], "evidence_ref": detail["evidence_ref"],
                      "payload": detail["payload"]})
    envelope = {"schema": "kon-incoming-inspection/v1", "source_system": "KonSol AT Studio",
                "exported_at_utc": utc_now(), "records": items}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def export_csv(output: Path, db_path: Path = DEFAULT_DB) -> Path:
    rows = query_inspections(limit=1000000, db_path=db_path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "module_code", "reported_mac", "identity_source", "tested_on",
              "tested_at_utc", "profile", "test_code", "result", "acceptance_status",
              "evidence_source", "sw_version", "board"]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return output


def backup_database(output: Path, db_path: Path = DEFAULT_DB) -> Path:
    source = Path(db_path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(source)
    output = Path(output)
    if output.resolve() == source.resolve():
        raise ValueError("Backup destination must differ from source")
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(output) as dst:
        src.backup(dst)
    return output


def generate_report(output: Path, db_path: Path = DEFAULT_DB) -> Path:
    rows = query_inspections(limit=1000000, db_path=db_path)
    def escape(value):
        return html.escape("-" if value is None else str(value))
    lines = []
    for row in rows:
        lines.append("<tr>" + "".join(f"<td>{escape(row.get(k))}</td>" for k in
             ("id", "module_code", "reported_mac", "tested_on", "profile", "test_code", "result", "acceptance_status", "evidence_source")) + "</tr>")
    page = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<title>KonSol inspection registry</title><style>body{font:15px system-ui;margin:28px;color:#162536}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #b6c4d3;padding:8px;text-align:left}
th{background:#e9f1f8}tr:nth-child(2n){background:#f7fafd}</style></head><body>
<h1>KonSol Tools - incoming inspection history</h1><p>Each row is one scope-limited inspection.
MAC is module-reported, not an immutable hardware certificate. Overall incoming acceptance is NOT EVALUATED.</p>
<table><thead><tr><th>ID</th><th>Module code</th><th>Reported MAC</th><th>Test date</th><th>Profile</th><th>Test</th><th>Result</th><th>Acceptance</th><th>Evidence</th></tr></thead><tbody>"""
    page += "".join(lines) + "</tbody></table></body></html>"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output


def import_history(document_path: Path, db_path: Path = DEFAULT_DB) -> dict:
    """Import a private historical evidence package; never overwrite inspections.

    This is NOT the same as the general interchange export schema. Importing an
    external JSON file records its *claims*, not independent hardware validation.
    Repeat imports are idempotent by inspection_uid.
    """
    path = Path(document_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "kon-inspection-history-seed/v1":
        raise ValueError("Expected kon-inspection-history-seed/v1 JSON envelope")
    records = document.get("records")
    if not isinstance(records, list) or not (1 <= len(records) <= 10000):
        raise ValueError("Expected 1..10000 historical inspections")
    inserted = skipped = 0
    for row in records:
        if not isinstance(row, dict) or not row.get("record_id"):
            raise ValueError("Missing record_id in historical inspection")
        if Path(db_path).is_file():
            with sqlite3.connect(db_path) as con:
                existing = con.execute(
                    "SELECT 1 FROM inspections WHERE inspection_uid=?", (row["record_id"],)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue
        add_inspection(
            mac=row["reported_mac"], identity_source=row["identity_source"],
            profile=row["profile"], test_code=row["test_code"],
            result=row["result"], tested_on=row["tested_on"],
            tested_at_utc=row.get("tested_at_utc"),
            evidence_source="historical_screenshot", evidence_ref=row.get("evidence_ref"),
            board=row.get("board"), sw_version=row.get("sw_version"),
            hw_version=row.get("hw_version"), payload=row["payload"],
            inspection_uid=row["record_id"], db_path=db_path,
        )
        inserted += 1
    return {"inserted": inserted, "already_present": skipped, "database": str(db_path)}
