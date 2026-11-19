"""
tools/backfill_contacts.py - Read organiser contact details off posters saved before
the contact_phone / instagram columns existed.

    python tools/backfill_contacts.py            # events with no booking link, phone or Instagram
    python tools/backfill_contacts.py --dry-run  # show what would change

Only blank fields are filled; nothing you've typed in is overwritten. Uses one
vision-model call per poster.
"""
import argparse
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import store  # noqa: E402
from backend.contacts import normalize_instagram, normalize_link, normalize_phone  # noqa: E402
from backend.extractor import extract_poster_details  # noqa: E402

CLEANERS = {"booking_link": normalize_link, "contact_phone": normalize_phone, "instagram": normalize_instagram}


def poster_bytes(event: dict) -> bytes:
    sub = event.get("submission") or {}
    if sub.get("poster_path"):
        return store.client().storage.from_(store.POSTER_BUCKET).download(sub["poster_path"])
    url = event.get("image_url") or ""
    if url.startswith("/"):
        return (ROOT_DIR / "frontend" / "public" / url.lstrip("/")).read_bytes()
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = [e for status in ("published", "review") for e in store.list_admin_events(status)]
    todo = [e for e in events if e.get("image_url") and not any(e.get(k) for k in CLEANERS)]
    print(f"[Contacts] {len(todo)} event(s) without a booking link, phone or Instagram")
    updated = 0
    for event in todo:
        try:
            details = extract_poster_details(poster_bytes(event), filename=f"event-{event['id']}")
        except Exception as exc:
            print(f"  - #{event['id']}: couldn't read the poster ({exc})")
            continue
        if details.get("backend") == "heuristic":
            print(f"  - #{event['id']}: couldn't read the poster (models unavailable); run again later")
            continue
        found = {k: clean(details.get(k)) for k, clean in CLEANERS.items()}
        found = {k: v for k, v in found.items() if v}
        print(f"  - #{event['id']} {(event.get('title') or '')[:40]!r}: {found or 'nothing found'}")
        if found and not args.dry_run:
            store.update_event(event["id"], found)
            updated += 1
    print(f"[Contacts] updated {updated} event(s){' (dry run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
