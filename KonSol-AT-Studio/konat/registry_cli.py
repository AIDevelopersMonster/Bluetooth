"""Local CLI for the KonSol Tools Bluetooth incoming inspection registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .inspection_registry import (
    DEFAULT_DB, db_status, ensure_db, query_inspections, get_inspection,
    registry_summary, export_json, export_csv, generate_report, backup_database, import_history,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="konat-registry", description="KonSol AT Studio internal SQLite registry")
    p.add_argument("--database", type=Path, default=DEFAULT_DB, help="Local SQLite file")
    sub = p.add_subparsers(dest="command", required=True)
    for action in ("status", "create", "summary"):
        sub.add_parser(action)
    q = sub.add_parser("list")
    q.add_argument("--limit", type=int, default=20)
    q = sub.add_parser("find")
    q.add_argument("--mac")
    q.add_argument("--module")
    q.add_argument("--result", choices=["PASS", "FAIL", "INCOMPLETE"])
    q.add_argument("--limit", type=int, default=100)
    q = sub.add_parser("show")
    q.add_argument("inspection_id", type=int)
    for action in ("export-json", "export-csv", "report", "backup"):
        q = sub.add_parser(action)
        q.add_argument("output", type=Path)
    q = sub.add_parser("import-history", help="Import date-grounded private screenshot evidence")
    q.add_argument("input", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = args.database
    if args.command == "create":
        ensure_db(db)
        output = db_status(db)
    elif args.command == "status":
        output = db_status(db)
    elif args.command == "summary":
        output = registry_summary(db)
    elif args.command == "list":
        output = query_inspections(limit=args.limit, db_path=db)
    elif args.command == "find":
        output = query_inspections(mac=args.mac, module=args.module, result=args.result,
                                   limit=args.limit, db_path=db)
    elif args.command == "show":
        output = get_inspection(args.inspection_id, db_path=db)
        if output is None:
            raise SystemExit(f"Inspection #{args.inspection_id} was not found")
    elif args.command == "import-history":
        output = import_history(args.input, db_path=db)
    else:
        tasks = {"export-json": export_json, "export-csv": export_csv,
                 "report": generate_report, "backup": backup_database}
        output = {"saved": str(tasks[args.command](args.output, db_path=db))}
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
