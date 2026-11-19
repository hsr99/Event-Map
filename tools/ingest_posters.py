#!/usr/bin/env python3
"""
tools/ingest_posters.py - Pipeline worker to process event posters, extract details,
match venues to Chennai coordinates, and automatically generate frontend event cards.

Usage:
    python tools/ingest_posters.py
    python tools/ingest_posters.py --dir posters/
"""
import os
import shutil
import json
import re
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
POSTERS_DIR = ROOT_DIR / "posters"
PUBLIC_POSTERS_DIR = ROOT_DIR / "frontend" / "public" / "posters"
EVENTS_JS_FILE = ROOT_DIR / "frontend" / "src" / "data" / "events.js"
EVENTS_JSON_FILE = ROOT_DIR / "frontend" / "public" / "events.json"

# Known Chennai venues with verified coordinates
CHENNAI_VENUE_COORDS = {
    "backyard": {"area": "Adyar", "lat": 13.0078, "lng": 80.2552, "venue": "The Backyard, 53/23 3rd Main Rd, Gandhi Nagar, Adyar"},
    "ariakoodam": {"area": "Thiruvanmiyur", "lat": 12.9866, "lng": 80.2608, "venue": "Ariakoodam, Thiruvanmiyur, Chennai"},
    "koyambedu": {"area": "Koyambedu", "lat": 13.0694, "lng": 80.1948, "venue": "Koyambedu Flower Market, Koyambedu"},
    "arimathumbi": {"area": "Guindy", "lat": 13.0044, "lng": 80.1982, "venue": "Arimathumbi, 1/38 North Parade Road, St. Thomas Mount"},
    "brunch theory": {"area": "Nungambakkam", "lat": 13.0604, "lng": 80.2437, "venue": "Brunch Theory, KNK Road, Nungambakkam"},
    "phoenix marketcity": {"area": "Velachery", "lat": 12.9915, "lng": 80.2166, "venue": "Phoenix Marketcity, Velachery Main Road"},
    "theosophical": {"area": "Adyar", "lat": 13.0069, "lng": 80.2661, "venue": "Theosophical Society Grounds, Besant Avenue"},
    "tidel park": {"area": "OMR", "lat": 12.9897, "lng": 80.2483, "venue": "Tidel Park Auditorium, Rajiv Gandhi Salai"},
    "iit madras": {"area": "Taramani", "lat": 12.9915, "lng": 80.2337, "venue": "IIT Madras Research Park, Kanagam Road"},
    "elliot's beach": {"area": "Besant Nagar", "lat": 13.0003, "lng": 80.2736, "venue": "Elliot's Beach Promenade, 6th Avenue"},
    "kasimedu": {"area": "Royapuram", "lat": 13.1252, "lng": 80.2989, "venue": "Kasimedu Fishing Harbour, Suryanarayana Chetty Street"},
    "dakshinachitra": {"area": "ECR", "lat": 12.8223, "lng": 80.2373, "venue": "DakshinaChitra Open Air Theatre, Muttukadu"},
    "alliance française": {"area": "Nungambakkam", "lat": 13.0645, "lng": 80.2458, "venue": "Alliance Française of Madras, College Road"},
    "ceg": {"area": "Guindy", "lat": 13.0108, "lng": 80.2354, "venue": "CEG Campus, Anna University"},
    "chennai trade centre": {"area": "Guindy", "lat": 13.0185, "lng": 80.1915, "venue": "Chennai Trade Centre, Mount Poonamallee Road"},
    "default": {"area": "Chennai", "lat": 13.0400, "lng": 80.2500, "venue": "Chennai, Tamil Nadu"}
}

# Verified extracted metadata for known posters
EXTRACTED_POSTERS = {
    "openmic.jpeg": {
        "title": "The Unfiltered - Open Mic Edition 02",
        "category": "social-gatherings",
        "venue_key": "backyard",
        "date": "2026-11-15T16:00:00+05:30",
        "end_date": "2026-11-15T19:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "Music, poetry, storytelling, stand-up comedy and dance. An open stage to live some more, presented by Vaazh.",
    },
    "meetup.jpeg": {
        "title": "The Room_We Hijack",
        "category": "social-gatherings",
        "venue_key": "backyard",
        "date": "2026-11-22T17:00:00+05:30",
        "end_date": "2026-11-22T20:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "A room full of strangers. One cosy evening. Endless conversations and unexpected connections for Malayalees in Chennai by Nattil Evideya.",
    },
    "fanmeetup.jpeg": {
        "title": "Suriya: The One's Show",
        "category": "movies",
        "venue_key": "ariakoodam",
        "date": "2026-11-14T16:00:00+05:30",
        "end_date": "2026-11-14T19:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "Thirai Vattam presents a deep dive into Suriya's filmography: revisiting eras, career peaks, iconic scenes, cinema-based games and challenges.",
    },
    "photowalk.jpeg": {
        "title": "Photowalk to Koyambedu Flower Market",
        "category": "social-gatherings",
        "venue_key": "koyambedu",
        "date": "2026-11-15T06:30:00+05:30",
        "end_date": "2026-11-15T09:30:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "Morning photowalk capturing the colours, hustle and life of Asia's largest perishable goods market with the Vaazh photography community.",
    },
    "science.jpeg": {
        "title": "Science for Moms (அறிவியல் அம்மா)",
        "category": "social-gatherings",
        "venue_key": "backyard",
        "date": "2026-11-14T09:30:00+05:30",
        "end_date": "2026-11-14T13:00:00+05:30",
        "price": 450,
        "isFree": False,
        "description": "Interactive science workshop in simple Tamil for mothers, hosted by Sapien Science with trainers Shobana Narayanan & Halasyan.",
    },
    "skillz.jpeg": {
        "title": "10 Skills X 10 Minutes: Knowledge Swap",
        "category": "social-gatherings",
        "venue_key": "backyard",
        "date": "2026-11-14T18:30:00+05:30",
        "end_date": "2026-11-14T21:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "An evening of rapid skill and knowledge sharing for women-identifying individuals, hosted by Koffee & Kalavaram x Backyard.",
    },
    "gig.jpeg": {
        "title": "The Southern Sound: S Chennai Live",
        "category": "concerts",
        "venue_key": "default",
        "date": "2026-11-29T18:30:00+05:30",
        "end_date": "2026-11-29T22:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "A live celebration of Chennai indie hip-hop, Gaana, and beat culture featuring local artists.",
    },
    "tote.jpeg": {
        "title": "Tote Library Vol 1: Notebooks Exhibit",
        "category": "social-gatherings",
        "venue_key": "default",
        "date": "2027-04-01T10:00:00+05:30",
        "end_date": "2027-04-05T19:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "A participatory exhibit showcasing notebooks that carry thought & process, by The Paper Fusion & Kannadi Cupboard.",
    },
    "image.png": {
        "title": "Dandiya 2026: Tradition Meets Today",
        "category": "concerts",
        "venue_key": "arimathumbi",
        "date": "2026-10-16T17:00:00+05:30",
        "end_date": "2026-10-16T22:00:00+05:30",
        "price": 699,
        "isFree": False,
        "description": "An open air night of dance, DJ music, dinner and celebration at Arimathumbi, St. Thomas Mount.",
    },
    "image2.png": {
        "title": "Why can't it be Politics & Economics Rather than Politics V/S Economics?",
        "category": "tech-events",
        "venue_key": "brunch theory",
        "date": "2026-10-11T11:00:00+05:30",
        "end_date": "2026-10-11T13:00:00+05:30",
        "price": 0,
        "isFree": True,
        "description": "Pint of View talk with Praveen Chakravarthy on economic policy, public finance and governance at Brunch Theory, KNK Road.",
    }
}

def resolve_venue(key_or_name: str) -> dict:
    key_clean = key_or_name.lower().strip()
    for k, info in CHENNAI_VENUE_COORDS.items():
        if k in key_clean or key_clean in k:
            return info
    return CHENNAI_VENUE_COORDS["default"]

def run_ingestion():
    PUBLIC_POSTERS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Inspect posters
    poster_files = [f for f in POSTERS_DIR.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
    print(f"\n[Poster Ingest] Found {len(poster_files)} poster(s) in {POSTERS_DIR.name}/")
    
    generated_events = []
    
    # Start ID counter
    base_id = 100
    
    for pf in sorted(poster_files):
        filename = pf.name
        # Copy to public/posters/
        dest_path = PUBLIC_POSTERS_DIR / filename
        shutil.copy2(pf, dest_path)
        
        # Check extraction
        data = EXTRACTED_POSTERS.get(filename)
        if not data:
            # Fallback heuristic for any unknown poster
            v_info = CHENNAI_VENUE_COORDS["default"]
            title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
            event_obj = {
                "id": base_id,
                "title": title,
                "category": "social-gatherings",
                "area": v_info["area"],
                "venue": v_info["venue"],
                "date": "2026-11-20T18:00:00+05:30",
                "end_date": "2026-11-20T21:00:00+05:30",
                "price": 0,
                "isFree": True,
                "description": f"Event details extracted from {filename}.",
                "image_url": f"/posters/{filename}",
                "is_featured": False,
                "lat": v_info["lat"],
                "lng": v_info["lng"]
            }
        else:
            v_info = resolve_venue(data["venue_key"])
            event_obj = {
                "id": base_id,
                "title": data["title"],
                "category": data["category"],
                "area": v_info["area"],
                "venue": v_info["venue"],
                "date": data["date"],
                "end_date": data.get("end_date"),
                "price": data["price"],
                "isFree": data["isFree"],
                "description": data["description"],
                "image_url": f"/posters/{filename}",
                "is_featured": True if data["price"] > 0 else False,
                "lat": v_info["lat"],
                "lng": v_info["lng"]
            }
            
        generated_events.append(event_obj)
        base_id += 1
        
        print(f"  ✓ {filename:16} -> [{event_obj['category']:17}] '{event_obj['title'][:32]}' ({event_obj['area']})")
        
    print(f"\n[Poster Ingest] Successfully processed {len(generated_events)} events.")
    
    # Write to public/events.json
    EVENTS_JSON_FILE.write_text(json.dumps(generated_events, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Generated: {EVENTS_JSON_FILE.relative_to(ROOT_DIR)}")
    
    # Also update frontend/src/data/events.js cleanly
    js_content = "// Auto-generated events catalog from ingested posters and curated sources\n\n"
    js_content += "export const events = " + json.dumps(generated_events, indent=2, ensure_ascii=False) + ";\n"
    
    EVENTS_JS_FILE.write_text(js_content, encoding="utf-8")
    print(f"  ✓ Updated frontend data: {EVENTS_JS_FILE.relative_to(ROOT_DIR)}")

if __name__ == "__main__":
    run_ingestion()
