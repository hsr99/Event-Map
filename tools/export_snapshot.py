#!/usr/bin/env python3
"""
tools/export_snapshot.py - Refresh the site's bundled fallback data from Supabase.

The site loads live events from Supabase. frontend/src/data/events.js is only a
fallback (shown instantly on first paint, and used when Supabase is unreachable
or not configured). Run this now and then so the fallback isn't stale.

Usage:
    python tools/export_snapshot.py
"""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import store  # noqa: E402

EVENTS_JS = ROOT_DIR / "frontend" / "src" / "data" / "events.js"
EVENTS_JSON = ROOT_DIR / "frontend" / "public" / "events.json"


def main() -> int:
    try:
        events = store.list_events()
    except store.StoreNotConfigured as exc:
        print(exc, file=sys.stderr)
        return 1
    payload = json.dumps(events, indent=2, ensure_ascii=False)
    EVENTS_JSON.write_text(payload + "\n", encoding="utf-8")
    EVENTS_JS.write_text(
        "// Fallback snapshot of published events, exported from Supabase by tools/export_snapshot.py.\n"
        "// The site loads live data from Supabase; this is only used for first paint and offline.\n\n"
        f"export const events = {payload};\n",
        encoding="utf-8",
    )
    print(f"Exported {len(events)} published event(s) to {EVENTS_JS.relative_to(ROOT_DIR)} and "
          f"{EVENTS_JSON.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
