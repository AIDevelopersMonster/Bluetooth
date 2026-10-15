"""Reproducible, scope-limited inspections from fresh UART AT responses."""
from __future__ import annotations

from datetime import datetime, timezone

from .inspection_registry import normalize_mac
from .profiles import response_value, status_of


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def examine_queries(profile, replies: dict[str, bytes]) -> dict:
    """Evaluate a batch: no unsupported claims or guessed MAC identities."""
    checks = []
    mac = None
    firmware = None
    for q in profile.queries:
        if q.get("probe_only"):
            continue
        reply = replies.get(q["id"], b"")
        state = status_of(reply)
        value = response_value(reply, q.get("prefix", ""))
        ok = (state == "OK" or (profile.key == "jdy31" and state == "RESPONSE" and bool(value))) and (not q.get("prefix") or bool(value))
        unknown = bool(ok and value in q.get("unknown_values", []))
        if unknown:
            ok = False
        if q["id"] == "address" and ok:
            try:
                mac = normalize_mac(value)
            except ValueError:
                ok = False
        if q["id"] == "version" and ok:
            firmware = value
        record = {"qid": q["id"], "command": q["command"], "status": "PASS" if ok else
                  ("INCOMPLETE" if state == "TIMEOUT" or unknown else "FAIL"),
                  "response_status": state, "value": value}
        if q["id"] != "pin":
            record["response_hex"] = reply.hex().upper()
        else:
            record["value"] = "[REDACTED]" if value is not None else None
            record["response_hex"] = "[REDACTED]"
        checks.append(record)
    passes = sum(c["status"] == "PASS" for c in checks)
    statuses = {c["status"] for c in checks}
    result = "PASS" if passes == len(checks) else ("FAIL" if "FAIL" in statuses else "INCOMPLETE")
    return {"mac": mac, "firmware": firmware, "result": result,
            "passed": passes, "total": len(checks), "checks": checks}
