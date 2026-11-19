#!/usr/bin/env python3
"""
tools/migrate_to_supabase.py - One-time move of the existing data into Supabase.

  * Upserts the verified venue directory.
  * Uploads each poster from frontend/public/posters/ to Supabase Storage and
    creates its event (published) from the bundled snapshot,
    frontend/public/events.json.

Safe to re-run: venues upsert by name and events are skipped when their poster
is already on record.

Run supabase_schema.sql in the Supabase SQL editor first.

Usage:
    python tools/migrate_to_supabase.py
"""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import store  # noqa: E402
from backend.posters import inspect_poster  # noqa: E402

SNAPSHOT = ROOT_DIR / "frontend" / "public" / "events.json"
PUBLIC_DIR = ROOT_DIR / "frontend" / "public"

VENUES = [
    {"name": "The Backyard", "area": "Adyar", "address": "53/23 3rd Main Rd, Gandhi Nagar, Adyar", "lat": 13.0078, "lng": 80.2552, "category": "creative-space"},
    {"name": "Ariakoodam", "area": "Thiruvanmiyur", "address": "Thiruvanmiyur, Chennai", "lat": 12.9866, "lng": 80.2608, "category": "cultural-space"},
    {"name": "Koyambedu Flower Market", "area": "Koyambedu", "address": "Koyambedu Perishable Goods Market, Chennai", "lat": 13.0694, "lng": 80.1948, "category": "heritage-market"},
    {"name": "Arimathumbi", "area": "Guindy", "address": "1/38 North Parade Road, St. Thomas Mount", "lat": 13.0044, "lng": 80.1982, "category": "open-air-lawn"},
    {"name": "Brunch Theory", "area": "Nungambakkam", "address": "KNK Road, Nungambakkam", "lat": 13.0604, "lng": 80.2437, "category": "cafe-bistro"},
    {"name": "Phoenix Marketcity", "area": "Velachery", "address": "Velachery Main Road, Velachery", "lat": 12.9915, "lng": 80.2166, "category": "shopping-mall"},
    {"name": "Theosophical Society Grounds", "area": "Adyar", "address": "Besant Avenue Road, Adyar", "lat": 13.0069, "lng": 80.2661, "category": "cultural-heritage"},
    {"name": "Tidel Park Auditorium", "area": "OMR", "address": "Rajiv Gandhi Salai, Taramani", "lat": 12.9897, "lng": 80.2483, "category": "convention"},
    {"name": "IIT Madras Research Park", "area": "Taramani", "address": "Kanagam Road, Taramani", "lat": 12.9915, "lng": 80.2337, "category": "auditorium"},
    {"name": "Elliot's Beach Promenade", "area": "Besant Nagar", "address": "6th Avenue, Besant Nagar", "lat": 13.0003, "lng": 80.2736, "category": "open-air"},
    {"name": "Kasimedu Fishing Harbour", "area": "Royapuram", "address": "Suryanarayana Chetty Street, Kasimedu", "lat": 13.1252, "lng": 80.2989, "category": "heritage-walk"},
    {"name": "DakshinaChitra Heritage Museum", "area": "ECR", "address": "East Coast Road, Muttukadu", "lat": 12.8223, "lng": 80.2373, "category": "open-air-theatre"},
    {"name": "Alliance Française of Madras", "area": "Nungambakkam", "address": "College Road, Nungambakkam", "lat": 13.0645, "lng": 80.2458, "category": "cultural-centre"},
    {"name": "Anna University (CEG Campus)", "area": "Guindy", "address": "Sardar Patel Road, Guindy", "lat": 13.0108, "lng": 80.2354, "category": "college-campus"},
]


def adopt_existing(title, image_url, info) -> bool:
    """Events seeded by hand earlier have no submission record. Rather than
    duplicating them, point them at the uploaded poster and record the poster."""
    c = store.client()
    rows = c.table("events").select("id,submissions(id)").eq("title", title).limit(1).execute().data
    if not rows:
        return False
    event = rows[0]
    c.table("events").update({"image_url": image_url}).eq("id", event["id"]).execute()
    if not event.get("submissions"):
        c.table("submissions").insert({
            "event_id": event["id"],
            "source": "admin",
            "poster_path": info.storage_path if info else None,
            "poster_hash": info.sha256 if info else None,
        }).execute()
    return True


def migrate() -> int:
    store.upsert_venues(VENUES)
    print(f"[Migrate] Venues upserted: {len(VENUES)}")

    events = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    added = skipped = adopted = 0
    for ev in events:
        image_url = ev.get("image_url") or ""
        poster_file = PUBLIC_DIR / image_url.lstrip("/") if image_url.startswith("/posters/") else None
        info = data = None
        if poster_file and poster_file.is_file():
            data = poster_file.read_bytes()
            info = inspect_poster(data)
            if store.find_submission_by_hash(info.sha256):
                skipped += 1
                continue
        else:
            print(f"  - '{ev['title'][:40]}': poster not found locally, migrating without one")

        new_url = store.upload_poster(data, info) if info else image_url
        if adopt_existing(ev["title"], new_url, info):
            adopted += 1
            print(f"  - '{ev['title'][:40]}' -> already in Supabase, poster attached")
            continue

        row = dict(ev)
        row["is_free"] = bool(ev.get("isFree", ev.get("is_free")))
        row["status"] = "published"
        row["image_url"] = new_url
        store.create_event(row, source="admin", poster=info)
        added += 1
        print(f"  - '{ev['title'][:40]}' -> migrated")

    print(f"[Migrate] {added} event(s) migrated, {adopted} existing event(s) updated, "
          f"{skipped} already done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(migrate())
    except store.StoreNotConfigured as exc:
        print(f"[Migrate] {exc}", file=sys.stderr)
        sys.exit(1)
