"""
backend/seed.py - Seeds the SQLite database from existing posters and verified venues.
"""
from backend.database import init_db, insert_event, insert_venue, export_to_frontend

SEED_VENUES = [
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

SEED_EVENTS = [
    {
        "title": "The Unfiltered - Open Mic Edition 02",
        "category": "social-gatherings",
        "area": "Adyar",
        "venue": "The Backyard, 53/23 3rd Main Rd, Gandhi Nagar, Adyar",
        "date": "2026-11-15T16:00:00+05:30",
        "end_date": "2026-11-15T19:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "Music, poetry, storytelling, stand-up comedy and dance. An open stage to live some more, presented by Vaazh.",
        "image_url": "/posters/openmic.jpeg",
        "lat": 13.0078,
        "lng": 80.2552,
    },
    {
        "title": "The Room_We Hijack",
        "category": "social-gatherings",
        "area": "Adyar",
        "venue": "The Backyard, 53/23 3rd Main Rd, Gandhi Nagar, Adyar",
        "date": "2026-11-22T17:00:00+05:30",
        "end_date": "2026-11-22T20:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "A room full of strangers. One cosy evening. Endless conversations and unexpected connections for Malayalees in Chennai by Nattil Evideya.",
        "image_url": "/posters/meetup.jpeg",
        "lat": 13.0078,
        "lng": 80.2552,
    },
    {
        "title": "Suriya: The One's Show",
        "category": "movies",
        "area": "Thiruvanmiyur",
        "venue": "Ariakoodam, Thiruvanmiyur, Chennai",
        "date": "2026-11-14T16:00:00+05:30",
        "end_date": "2026-11-14T19:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "Thirai Vattam presents a deep dive into Suriya's filmography: revisiting eras, career peaks, iconic scenes, cinema-based games and challenges.",
        "image_url": "/posters/fanmeetup.jpeg",
        "lat": 12.9866,
        "lng": 80.2608,
    },
    {
        "title": "Photowalk to Koyambedu Flower Market",
        "category": "social-gatherings",
        "area": "Koyambedu",
        "venue": "Koyambedu Flower Market, Koyambedu",
        "date": "2026-11-15T06:30:00+05:30",
        "end_date": "2026-11-15T09:30:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "Morning photowalk capturing the colours, hustle and life of Asia's largest perishable goods market with the Vaazh photography community.",
        "image_url": "/posters/photowalk.jpeg",
        "lat": 13.0694,
        "lng": 80.1948,
    },
    {
        "title": "Science for Moms (அறிவியல் அம்மா)",
        "category": "social-gatherings",
        "area": "Adyar",
        "venue": "The Backyard (Upper Floor), 53/23 3rd Main Rd, Gandhi Nagar, Adyar",
        "date": "2026-11-14T09:30:00+05:30",
        "end_date": "2026-11-14T13:00:00+05:30",
        "price": 450,
        "is_free": False,
        "description": "Interactive science workshop in simple Tamil for mothers, hosted by Sapien Science with trainers Shobana Narayanan & Halasyan.",
        "image_url": "/posters/science.jpeg",
        "lat": 13.0078,
        "lng": 80.2552,
    },
    {
        "title": "10 Skills X 10 Minutes: Knowledge Swap",
        "category": "social-gatherings",
        "area": "Adyar",
        "venue": "The Backyard, 53/23 3rd Main Rd, Gandhi Nagar, Adyar",
        "date": "2026-11-14T18:30:00+05:30",
        "end_date": "2026-11-14T21:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "An evening of rapid skill and knowledge sharing for women-identifying individuals, hosted by Koffee & Kalavaram x Backyard.",
        "image_url": "/posters/skillz.jpeg",
        "lat": 13.0078,
        "lng": 80.2552,
    },
    {
        "title": "The Southern Sound: S Chennai Live",
        "category": "concerts",
        "area": "Chennai",
        "venue": "Chennai, Tamil Nadu",
        "date": "2026-11-29T18:30:00+05:30",
        "end_date": "2026-11-29T22:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "A live celebration of Chennai indie hip-hop, Gaana, and beat culture featuring local artists.",
        "image_url": "/posters/gig.jpeg",
        "lat": 13.0400,
        "lng": 80.2500,
    },
    {
        "title": "Tote Library Vol 1: Notebooks Exhibit",
        "category": "social-gatherings",
        "area": "Chennai",
        "venue": "Chennai, Tamil Nadu",
        "date": "2027-04-01T10:00:00+05:30",
        "end_date": "2027-04-05T19:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "A participatory exhibit showcasing notebooks that carry thought & process, by The Paper Fusion & Kannadi Cupboard.",
        "image_url": "/posters/tote.jpeg",
        "lat": 13.0400,
        "lng": 80.2500,
    },
    {
        "title": "Dandiya 2026: Tradition Meets Today",
        "category": "concerts",
        "area": "Guindy",
        "venue": "Arimathumbi, 1/38 North Parade Road, St. Thomas Mount",
        "date": "2026-10-16T17:00:00+05:30",
        "end_date": "2026-10-16T22:00:00+05:30",
        "price": 699,
        "is_free": False,
        "description": "An open air night of dance, DJ music, dinner and celebration at Arimathumbi, St. Thomas Mount.",
        "image_url": "/posters/image.png",
        "lat": 13.0044,
        "lng": 80.1982,
    },
    {
        "title": "Why can't it be Politics & Economics Rather than Politics V/S Economics?",
        "category": "tech-events",
        "area": "Nungambakkam",
        "venue": "Brunch Theory, KNK Road, Nungambakkam",
        "date": "2026-10-11T11:00:00+05:30",
        "end_date": "2026-10-11T13:00:00+05:30",
        "price": 0,
        "is_free": True,
        "description": "Pint of View talk with Praveen Chakravarthy on economic policy, public finance and governance at Brunch Theory, KNK Road.",
        "image_url": "/posters/image2.png",
        "lat": 13.0604,
        "lng": 80.2437,
    },
]

def run_seed():
    init_db()
    print("[Seed] Seeding venues...")
    for v in SEED_VENUES:
        insert_venue(v)
    print(f"  ✓ Inserted {len(SEED_VENUES)} venues.")

    print("[Seed] Seeding events...")
    for ev in SEED_EVENTS:
        insert_event(ev)
    print(f"  ✓ Inserted {len(SEED_EVENTS)} events.")

    export_to_frontend()
    print("  ✓ Exported fresh events to frontend dataset.")

if __name__ == "__main__":
    run_seed()
