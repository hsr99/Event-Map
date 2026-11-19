"""
tools/backfill_fingerprints.py - Fingerprint posters saved before duplicate checks existed.

Run once after adding the poster_fingerprint column (supabase_schema.sql):
    python tools/backfill_fingerprints.py
Safe to re-run: only submissions without a fingerprint are touched.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import store  # noqa: E402
from backend.dedupe import poster_fingerprint  # noqa: E402


def main() -> int:
    rows = (
        store.client().table("submissions").select("id,event_id,poster_path")
        .is_("poster_fingerprint", "null").not_.is_("poster_path", "null").execute().data
    )
    print(f"[Backfill] {len(rows)} poster(s) without a fingerprint")
    done = 0
    for row in rows:
        try:
            data = store.client().storage.from_(store.POSTER_BUCKET).download(row["poster_path"])
        except Exception as exc:
            print(f"  - event {row['event_id']}: couldn't download {row['poster_path']} ({exc})")
            continue
        fp = poster_fingerprint(data)
        if not fp:
            print(f"  - event {row['event_id']}: unreadable image")
            continue
        store.client().table("submissions").update({"poster_fingerprint": fp}).eq("id", row["id"]).execute()
        done += 1
    print(f"[Backfill] fingerprinted {done} poster(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
