"""
backend/geocoder.py - Resolves Chennai venue names and areas to exact GPS coordinates.

Lookup order: a known venue (exact pin) -> a known locality (area centre) -> city centre.
"""
from typing import Dict, Any, Optional

# Venues with verified coordinates. Keys are lowercase substrings matched against
# the venue/area text pulled off a poster.
KNOWN_VENUES = {
    "backyard": {"area": "Adyar", "lat": 13.0078, "lng": 80.2552, "venue": "The Backyard, 53/23 3rd Main Rd, Gandhi Nagar, Adyar"},
    "ariakoodam": {"area": "Thiruvanmiyur", "lat": 12.9866, "lng": 80.2608, "venue": "Ariakoodam, Thiruvanmiyur, Chennai"},
    "koyambedu flower market": {"area": "Koyambedu", "lat": 13.0694, "lng": 80.1948, "venue": "Koyambedu Flower Market, Koyambedu"},
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
    "alliance francaise": {"area": "Nungambakkam", "lat": 13.0645, "lng": 80.2458, "venue": "Alliance Française of Madras, College Road"},
    "chennai trade centre": {"area": "Guindy", "lat": 13.0185, "lng": 80.1915, "venue": "Chennai Trade Centre, Mount Poonamallee Road"},
}

CHENNAI_LOCALITIES = {
    "adyar": {"lat": 13.0078, "lng": 80.2552, "area": "Adyar"},
    "besant nagar": {"lat": 13.0003, "lng": 80.2736, "area": "Besant Nagar"},
    "thiruvanmiyur": {"lat": 12.9866, "lng": 80.2608, "area": "Thiruvanmiyur"},
    "koyambedu": {"lat": 13.0694, "lng": 80.1948, "area": "Koyambedu"},
    "velachery": {"lat": 12.9915, "lng": 80.2166, "area": "Velachery"},
    "omr": {"lat": 12.9897, "lng": 80.2483, "area": "OMR"},
    "taramani": {"lat": 12.9915, "lng": 80.2337, "area": "Taramani"},
    "guindy": {"lat": 13.0044, "lng": 80.1982, "area": "Guindy"},
    "st. thomas mount": {"lat": 13.0044, "lng": 80.1982, "area": "Guindy"},
    "nungambakkam": {"lat": 13.0604, "lng": 80.2437, "area": "Nungambakkam"},
    "mylapore": {"lat": 13.0333, "lng": 80.2667, "area": "Mylapore"},
    "alwarpet": {"lat": 13.0345, "lng": 80.2520, "area": "Alwarpet"},
    "royapuram": {"lat": 13.1252, "lng": 80.2989, "area": "Royapuram"},
    "ecr": {"lat": 12.8223, "lng": 80.2373, "area": "ECR"},
    "egmore": {"lat": 13.0784, "lng": 80.2612, "area": "Egmore"},
    "t nagar": {"lat": 13.0418, "lng": 80.2341, "area": "T Nagar"},
    "anna nagar": {"lat": 13.0850, "lng": 80.2101, "area": "Anna Nagar"},
}

DEFAULT_CHENNAI = {"lat": 13.0400, "lng": 80.2500, "area": "Chennai"}


def resolve_venue_coordinates(venue: str, area: Optional[str] = None) -> Dict[str, Any]:
    """Resolves venue and area strings to lat/lng and a standardized area name.

    Returns {"lat", "lng", "area", "precision"} plus "venue" (the canonical
    venue string) when a known venue matched. precision is "venue", "area" or "city".
    """
    text = f"{venue or ''} {area or ''}".lower()
    given_area = area.strip() if area and area.strip() else None

    for key, v in KNOWN_VENUES.items():
        if key in text:
            return {"lat": v["lat"], "lng": v["lng"], "area": v["area"],
                    "venue": v["venue"], "precision": "venue"}

    for key, loc in CHENNAI_LOCALITIES.items():
        if key in text:
            return {"lat": loc["lat"], "lng": loc["lng"],
                    "area": given_area or loc["area"], "precision": "area"}

    return {"lat": DEFAULT_CHENNAI["lat"], "lng": DEFAULT_CHENNAI["lng"],
            "area": given_area or DEFAULT_CHENNAI["area"], "precision": "city"}
