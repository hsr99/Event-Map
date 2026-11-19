"""
backend/extractor.py - Poster -> event extraction for the backend.

Reads the poster with the vision-model cascade in extract_poster_vlm.py
(Groq -> Gemini -> local Qwen), then maps that raw output onto the event shape
the frontend and database use (title, category, ISO datetimes, price, ...).
If every model fails, it falls back to a filename heuristic and flags the
result for review.
"""
import re
import sys
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from extract_poster_vlm import extract_from_image  # noqa: E402

IST = "+05:30"
DEFAULT_START_TIME = "18:00"

# VLM categories (see extract_poster_vlm.SYSTEM_PROMPT) -> frontend category ids.
CATEGORY_MAP = {
    "tech": "tech-events",
    "networking_business": "tech-events",
    "music": "concerts",
    "film_theatre": "movies",
    "college_cultural": "college-culturals",
    "comedy": "social-gatherings",
    "art_workshop": "social-gatherings",
    "sports_fitness": "social-gatherings",
    "food_drink": "social-gatherings",
    "community_social": "social-gatherings",
}
FRONTEND_CATEGORIES = {"concerts", "tech-events", "college-culturals", "movies", "social-gatherings"}


def map_category(raw: Optional[str]) -> str:
    if not raw:
        return "social-gatherings"
    key = raw.strip().lower()
    if key in FRONTEND_CATEGORIES:
        return key
    return CATEGORY_MAP.get(key, "social-gatherings")


def parse_price(raw: Optional[str]) -> int:
    """'Free' -> 0, 'Rs.299' -> 299, 'Rs.199-Rs.499' -> 199 (lowest tier)."""
    if raw is None:
        return 0
    text = str(raw).lower()
    if "free" in text:
        return 0
    amounts = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]
    return min(amounts) if amounts else 0


def _valid_time(t: Optional[str]) -> Optional[str]:
    if t and re.fullmatch(r"\d{1,2}:\d{2}", t.strip()):
        h, m = t.strip().split(":")
        if int(h) < 24 and int(m) < 60:
            return f"{int(h):02d}:{m}"
    return None


def build_datetimes(d: Optional[str], d_end: Optional[str], t: Optional[str], t_end: Optional[str]):
    """Combine the VLM's separate date/time fields into ISO 8601 IST datetimes."""
    try:
        start_day = date.fromisoformat((d or "").strip()[:10])
    except ValueError:
        return None, None
    start_t = _valid_time(t) or DEFAULT_START_TIME
    start = f"{start_day.isoformat()}T{start_t}:00{IST}"

    end_t = _valid_time(t_end)
    try:
        end_day = date.fromisoformat((d_end or "").strip()[:10])
    except ValueError:
        end_day = start_day
    if end_t:
        # An end time earlier than the start on the same day means it runs past midnight.
        if end_day == start_day and end_t <= start_t:
            end_day = start_day + timedelta(days=1)
        return start, f"{end_day.isoformat()}T{end_t}:00{IST}"
    if end_day != start_day:
        return start, f"{end_day.isoformat()}T23:59:00{IST}"
    return start, None


def vlm_to_event(vlm: Dict[str, Any], filename: str = "") -> Dict[str, Any]:
    """Map extract_poster_vlm output onto the frontend/database event shape."""
    start, end = build_datetimes(vlm.get("date"), vlm.get("date_end"), vlm.get("time"), vlm.get("time_end"))
    review = list(vlm.get("needs_review") or [])
    if start is None:
        start = f"{date.today().isoformat()}T{DEFAULT_START_TIME}:00{IST}"
        if "date" not in review:
            review.append("date")
    elif not _valid_time(vlm.get("time")):
        review.append("time")

    price = parse_price(vlm.get("ticket_price"))
    title = (vlm.get("event_name") or "").strip() or _title_from_filename(filename)
    return {
        "title": title,
        "category": map_category(vlm.get("category")),
        "date": start,
        "end_date": end,
        "venue": (vlm.get("venue") or "").strip(),
        "area": (vlm.get("area") or "").strip(),
        "price": price,
        "is_free": price == 0,
        "isFree": price == 0,
        "booking_link": (vlm.get("booking_link") or "").strip(),
        "contact_phone": (vlm.get("contact_phone") or "").strip(),
        "instagram": (vlm.get("instagram") or "").strip(),
        "description": (vlm.get("description") or "").strip(),
        "needs_review": review,
        "backend": vlm.get("backend", "unknown"),
    }


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem if filename else ""
    return stem.replace("_", " ").replace("-", " ").title() or "Untitled Event"


def heuristic_event(filename: str = "") -> Dict[str, Any]:
    """Last resort when every model fails: guess from the filename and flag everything."""
    lower_fn = filename.lower()
    category = "social-gatherings"
    if any(k in lower_fn for k in ["gig", "concert", "music", "dandiya", "dj", "band"]):
        category = "concerts"
    elif any(k in lower_fn for k in ["tech", "ai", "hack", "code", "dev"]):
        category = "tech-events"
    elif any(k in lower_fn for k in ["movie", "cinema", "film", "screening"]):
        category = "movies"
    elif any(k in lower_fn for k in ["cultural", "fest", "college"]):
        category = "college-culturals"
    today = date.today().isoformat()
    return {
        "title": _title_from_filename(filename),
        "category": category,
        "date": f"{today}T{DEFAULT_START_TIME}:00{IST}",
        "end_date": None,
        "venue": "",
        "area": "",
        "price": 0,
        "is_free": True,
        "isFree": True,
        "booking_link": "",
        "contact_phone": "",
        "instagram": "",
        "description": "",
        "needs_review": ["extraction_failed"],
        "backend": "heuristic",
    }


def extract_poster_details(
    image_bytes: bytes,
    filename: str = "",
    ref: Optional[date] = None,
    backend: str = "auto",
) -> Dict[str, Any]:
    """Extract event fields from poster bytes.

    Returns the event-shaped dict (see vlm_to_event) plus "raw": the unmapped
    model output, kept for the posters audit table.
    """
    ref = ref or date.today()
    try:
        img = Image.open(BytesIO(image_bytes))
        img.load()
        vlm = extract_from_image(img, Path(filename or "upload"), ref, backend=backend)
    except Exception as exc:
        print(f"[Extractor] All vision backends failed for {filename or 'upload'}: {exc}", file=sys.stderr)
        event = heuristic_event(filename)
        event["raw"] = {"error": str(exc)}
        return event

    event = vlm_to_event(vlm, filename)
    event["raw"] = vlm
    return event
