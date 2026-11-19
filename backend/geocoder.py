"""
backend/geocoder.py - Resolves Chennai venue names and areas to exact GPS coordinates.
"""
from typing import Dict, Any, Optional

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
    """Resolves venue and area strings to lat/lng and standardized area name."""
    text = f"{venue} {area or ''}".lower()

    # Match specific localities
    for key, loc in CHENNAI_LOCALITIES.items():
        if key in text:
            return {
                "lat": loc["lat"],
                "lng": loc["lng"],
                "area": area if area and area.strip() else loc["area"],
            }

    # Default to Chennai center
    return {
        "lat": DEFAULT_CHENNAI["lat"],
        "lng": DEFAULT_CHENNAI["lng"],
        "area": area if area and area.strip() else DEFAULT_CHENNAI["area"],
    }
