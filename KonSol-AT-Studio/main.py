#!/usr/bin/env python3
"""Run KonSol AT Studio; use the system Python with pyserial installed."""
from pathlib import Path
import sys
from konat.ui import ATStudio


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    if len(sys.argv) == 2 and sys.argv[1] == "--check-profiles":
        from konat.profiles import discover_profiles
        profiles, errors = discover_profiles(root / "modules")
        for p in profiles:
            print(f"VALID  {p.key}  {p.title}: {len(p.queries)} queries; {len(p.setters)} setters")
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
        sys.exit(1 if errors else 0)
    ATStudio(root).run()
