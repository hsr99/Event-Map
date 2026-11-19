#!/usr/bin/env python3
"""
tools/ingest_posters.py - Turn new posters into events in Supabase.

For every image in frontend/public/posters/ that isn't on record yet:
  1. Read it with the vision-model cascade (Groq -> Gemini -> local Qwen)
  2. Resolve the venue to coordinates
  3. Upload the poster to Supabase Storage and save the event

Posters are matched by content hash, so re-running is safe. Events the model
was unsure about are saved as "review" and stay off the site until approved
(see tools/review_events.py).

Usage:
    python tools/ingest_posters.py
    python tools/ingest_posters.py --dry-run          # extract and print, save nothing
    python tools/ingest_posters.py --backend gemini   # force one model backend
    python tools/ingest_posters.py --publish-all      # publish even low-confidence events
"""
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import dedupe, store  # noqa: E402
from backend.contacts import normalize_instagram, normalize_link, normalize_phone  # noqa: E402
from backend.extractor import extract_poster_details  # noqa: E402
from backend.geocoder import resolve_venue_coordinates  # noqa: E402
from backend.posters import InvalidPoster, inspect_poster  # noqa: E402

POSTERS_DIR = ROOT_DIR / "frontend" / "public" / "posters"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def build_event(details: dict, publish_all: bool) -> tuple[dict, list]:
    geo = resolve_venue_coordinates(details["venue"], details["area"])
    review = list(details["needs_review"])
    if geo["precision"] == "city":
        review.append("location")
    event = {
        "title": details["title"],
        "category": details["category"],
        "venue": geo.get("venue") or details["venue"] or "Chennai, Tamil Nadu",
        "area": geo["area"] if geo["precision"] == "venue" else (details["area"] or geo["area"]),
        "date": details["date"],
        "end_date": details["end_date"],
        "price": details["price"],
        "is_free": details["isFree"],
        "description": details["description"],
        "booking_link": normalize_link(details["booking_link"]),
        "contact_phone": normalize_phone(details.get("contact_phone")),
        "instagram": normalize_instagram(details.get("instagram")),
        "lat": geo["lat"],
        "lng": geo["lng"],
        "status": "published" if publish_all or not review else "review",
    }
    return event, review


def run_ingestion(dry_run: bool = False, backend: str = "auto", publish_all: bool = False) -> int:
    posters = sorted(p for p in POSTERS_DIR.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    print(f"\n[Poster Ingest] Found {len(posters)} poster(s) in {POSTERS_DIR.relative_to(ROOT_DIR).as_posix()}/")

    added = in_review = skipped = 0
    for path in posters:
        data = path.read_bytes()
        try:
            info = inspect_poster(data)
        except InvalidPoster as exc:
            print(f"  - {path.name}: skipped ({exc})")
            continue
        if store.find_submission_by_hash(info.sha256):
            skipped += 1
            continue

        print(f"  - {path.name}: extracting...")
        details = extract_poster_details(data, filename=path.name, backend=backend)
        event, review = build_event(details, publish_all)

        matches = store.find_duplicates(event, info.fingerprint)
        block = dedupe.blocking_match(matches)
        if block:
            print(f"      already on record as event {block['id']} ('{(block['title'] or '')[:40]}'): skipped")
            skipped += 1
            continue
        if matches:
            # Never auto-publish a possible duplicate; let a person decide.
            event["status"] = "review"
            review.append("possible duplicate of " + ", ".join(f"#{m['id']}" for m in matches[:3]))

        print(f"      [{details['backend']}] '{event['title'][:40]}' | {event['category']} | "
              f"{event['date']} | {event['area']} | Rs.{event['price']} -> {event['status']}")
        if review:
            print(f"      needs review: {', '.join(review)}")
        if dry_run:
            continue

        event["image_url"] = store.upload_poster(data, info)
        store.create_event(event, source="ingest", poster=info, extracted_data=details.get("raw"))
        added += 1
        in_review += event["status"] == "review"

    print(f"\n[Poster Ingest] {added} new event(s) saved ({in_review} waiting for review), "
          f"{skipped} already on record.{' (dry run: nothing saved)' if dry_run else ''}")
    if in_review:
        print("  - Approve them with: python tools/review_events.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn new posters in frontend/public/posters/ into events.")
    ap.add_argument("--dry-run", action="store_true", help="extract and print, but save nothing")
    ap.add_argument("--backend", choices=["auto", "groq", "gemini", "qwen", "hf"], default="auto",
                    help="vision backend; 'auto' = Groq -> Gemini -> local Qwen")
    ap.add_argument("--publish-all", action="store_true",
                    help="publish events even when the model flagged fields for review")
    args = ap.parse_args()
    try:
        return run_ingestion(dry_run=args.dry_run, backend=args.backend, publish_all=args.publish_all)
    except store.StoreNotConfigured as exc:
        print(f"[Poster Ingest] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
