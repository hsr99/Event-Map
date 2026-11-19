#!/usr/bin/env python3
"""
tools/ingest_posters.py - Turn new posters into events.

For every image in frontend/public/posters/ that isn't already an event:
  1. Read it with the vision-model cascade (Groq -> Gemini -> local Qwen)
  2. Resolve the venue to coordinates
  3. Save the event to the backend database (data/events.db)
Then export the database to the frontend (events.js / events.json).

The backend database is the source of truth; this script never writes the
frontend files directly. Posters already in the database are skipped, so it is
safe to re-run. Events the model was unsure about are saved as "pending" and
are NOT shown on the site until reviewed.

Usage:
    python tools/ingest_posters.py
    python tools/ingest_posters.py --dry-run          # extract and print, save nothing
    python tools/ingest_posters.py --backend gemini   # force one model backend
    python tools/ingest_posters.py --publish-all      # publish even low-confidence events
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.database import (  # noqa: E402
    export_to_frontend,
    get_event_by_image_url,
    get_poster_by_hash,
    init_db,
    insert_event,
    insert_poster_record,
)
from backend.extractor import extract_poster_details  # noqa: E402
from backend.geocoder import resolve_venue_coordinates  # noqa: E402

# Single source of truth: posters live where the frontend serves them from.
POSTERS_DIR = ROOT_DIR / "frontend" / "public" / "posters"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def build_event(details: dict, image_url: str, publish_all: bool) -> dict:
    geo = resolve_venue_coordinates(details["venue"], details["area"])
    review = list(details["needs_review"])
    if geo["precision"] == "city":
        review.append("location")
    return {
        "title": details["title"],
        "category": details["category"],
        "venue": geo.get("venue") or details["venue"] or "Chennai, Tamil Nadu",
        "area": geo["area"] if geo["precision"] == "venue" else (details["area"] or geo["area"]),
        "date": details["date"],
        "end_date": details["end_date"],
        "price": details["price"],
        "isFree": details["isFree"],
        "description": details["description"],
        "booking_link": details["booking_link"],
        "image_url": image_url,
        "lat": geo["lat"],
        "lng": geo["lng"],
        "is_featured": False,
        "status": "published" if publish_all or not review else "pending",
        "_review": review,
    }


def run_ingestion(dry_run: bool = False, backend: str = "auto", publish_all: bool = False) -> int:
    init_db()
    posters = sorted(p for p in POSTERS_DIR.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    print(f"\n[Poster Ingest] Found {len(posters)} poster(s) in {POSTERS_DIR.relative_to(ROOT_DIR).as_posix()}/")

    added = pending = skipped = 0
    for path in posters:
        image_url = f"/posters/{path.name}"
        data = path.read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()

        if get_event_by_image_url(image_url) or get_poster_by_hash(file_hash):
            skipped += 1
            continue

        print(f"  - {path.name}: extracting...")
        details = extract_poster_details(data, filename=path.name, backend=backend)
        event = build_event(details, image_url, publish_all)
        review = event.pop("_review")

        print(f"      [{details['backend']}] '{event['title'][:40]}' | {event['category']} | "
              f"{event['date']} | {event['area']} | Rs.{event['price']} -> {event['status']}")
        if review:
            print(f"      needs review: {', '.join(review)}")

        if dry_run:
            continue
        event_id = insert_event(event)
        insert_poster_record(event_id, path.name, file_hash, details.get("raw"))
        added += 1
        pending += event["status"] == "pending"

    if not dry_run:
        export_to_frontend()
    print(f"\n[Poster Ingest] {added} new event(s) saved ({pending} pending review), "
          f"{skipped} already in the database.{' (dry run: nothing saved)' if dry_run else ''}")
    if not dry_run:
        print("  - Frontend data exported: frontend/src/data/events.js, frontend/public/events.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn new posters in frontend/public/posters/ into events.")
    ap.add_argument("--dry-run", action="store_true", help="extract and print, but save nothing")
    ap.add_argument("--backend", choices=["auto", "groq", "gemini", "qwen", "hf"], default="auto",
                    help="vision backend; 'auto' = Groq -> Gemini -> local Qwen")
    ap.add_argument("--publish-all", action="store_true",
                    help="publish events even when the model flagged fields for review")
    args = ap.parse_args()
    return run_ingestion(dry_run=args.dry_run, backend=args.backend, publish_all=args.publish_all)


if __name__ == "__main__":
    sys.exit(main())
