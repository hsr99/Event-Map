"""
backend/dedupe.py - Spot events that are already on record.

Two independent checks, so a duplicate has to slip past both:

* Poster fingerprint: a 256-bit difference hash of the image. Unlike the sha256
  hash, it survives resizing, recompression, screenshots with bars around the
  poster and small brightness changes. Distinct posters sit 100+ bits apart;
  copies of one poster usually differ by under 40.
* Details: the same (or a very similar) title on the same day, or a similar
  title at the same venue on the same day. This catches a different poster for
  the same event, e.g. an Instagram square and a story.
"""
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional

from PIL import Image, ImageChops, ImageOps

CHENNAI = timezone(timedelta(hours=5, minutes=30))

HASH_SIZE = 16              # 16x16 = 256 bits
SAME_POSTER_BITS = 48       # at most this many bits apart => same poster
IDENTICAL_POSTER_BITS = 12  # re-encoded copy of the same file; no need to read it again
MIN_DETAIL_BITS = 16        # fewer edges than this: too plain to fingerprint

STOPWORDS = {
    "the", "a", "an", "and", "of", "in", "at", "by", "for", "with", "to", "on",
    "presents", "present", "live", "chennai", "s",
}


# --------------------------------------------------------------------------- #
# Poster fingerprint
# --------------------------------------------------------------------------- #
def _trim_border(img: Image.Image) -> Image.Image:
    """Drop a solid border (screenshot bars, letterboxing) if there is one."""
    gray = img.convert("L")
    corner = Image.new("L", gray.size, gray.getpixel((0, 0)))
    box = ImageChops.difference(gray, corner).point(lambda p: 255 if p > 8 else 0).getbbox()
    if box and box[2] - box[0] > gray.width * 0.3 and box[3] - box[1] > gray.height * 0.3:
        return img.crop(box)
    return img


def poster_fingerprint(data: bytes) -> Optional[str]:
    """64-character hex fingerprint of how the poster looks, or None if unreadable."""
    try:
        with Image.open(BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            small = _trim_border(img).convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS)
    except Exception:
        return None
    px = small.load()
    bits = 0
    for y in range(HASH_SIZE):
        for x in range(HASH_SIZE):
            bits = (bits << 1) | (px[x, y] > px[x + 1, y])
    # A near-blank image has almost no edges, so every plain image would "match".
    if bin(bits).count("1") < MIN_DETAIL_BITS:
        return None
    return f"{bits:064x}"


def fingerprint_distance(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b:
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Details
# --------------------------------------------------------------------------- #
def _words(text: Optional[str]) -> List[str]:
    """Lower-cased words in any script (Tamil vowel signs stay with their letters)."""
    cleaned = "".join(
        ch if unicodedata.category(ch)[0] in "LMN" else " "
        for ch in unicodedata.normalize("NFC", (text or "").lower())
    )
    return [w for w in cleaned.split() if w not in STOPWORDS]


def text_similarity(a: Optional[str], b: Optional[str]) -> float:
    """0..1. High when one title is the other reworded, reordered or with extra words."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    score = SequenceMatcher(None, " ".join(wa), " ".join(wb)).ratio()
    sa, sb = set(wa), set(wb)
    if min(len(sa), len(sb)) >= 2:
        # "Suriya: The One's Show" vs "The One's Show - A Suriya Special"
        score = max(score, 0.95 * len(sa & sb) / min(len(sa), len(sb)))
    return score


def _day(value: Any) -> Optional[str]:
    if not value:
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CHENNAI)
    return dt.astimezone(CHENNAI).date().isoformat()


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def find_matches(
    event: Dict[str, Any],
    fingerprint: Optional[str],
    candidates: Iterable[Dict[str, Any]],
    exclude_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Events in `candidates` that look like the same event.

    Each candidate needs id, title, venue, date, status, image_url and
    `poster_fingerprint`. Returns the matches, strongest first, each with a
    plain-English `reason` and `same_poster` / `same_day` flags.
    """
    day = _day(event.get("date"))
    matches = []
    for other in candidates:
        if other.get("id") == exclude_id:
            continue
        other_day = _day(other.get("date"))
        same_day = bool(day and other_day and day == other_day)
        dates_clash = bool(day and other_day and day != other_day)

        distance = fingerprint_distance(fingerprint, other.get("poster_fingerprint"))
        same_poster = distance is not None and distance <= SAME_POSTER_BITS
        title_sim = text_similarity(event.get("title"), other.get("title"))
        venue_sim = text_similarity(event.get("venue"), other.get("venue"))

        reason = None
        if same_poster:
            reason = "Same poster, different date" if dates_clash else "Same poster"
        elif same_day and title_sim >= 0.75:
            reason = "Same title on the same day"
        elif same_day and venue_sim >= 0.75 and title_sim >= 0.45:
            reason = "Same day and venue, similar title"
        elif not dates_clash and not same_day and title_sim >= 0.9:
            reason = "Same title (date not known)"
        if not reason:
            continue

        strength = (2 if same_poster and not dates_clash else 1 if same_poster else 0) + title_sim
        matches.append({
            "id": other["id"],
            "title": other.get("title"),
            "venue": other.get("venue"),
            "date": other.get("date"),
            "status": other.get("status"),
            "image_url": other.get("image_url"),
            "reason": reason,
            "same_poster": same_poster,
            "same_day": same_day,
            "distance": distance,
            "title_similarity": round(title_sim, 2),
            "_strength": strength,
        })
    matches.sort(key=lambda m: m.pop("_strength"), reverse=True)
    return matches


def blocking_match(matches: List[Dict[str, Any]], today: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The match that makes a new submission pointless: a copy of the poster of an
    upcoming event that's already live or waiting for review.

    Refusing is reserved for near-certain cases; everything else is only flagged
    for review. So:
    * a past event never blocks (the same poster may be reused for a repeat);
    * a re-saved copy of the very same image blocks;
    * a lookalike only blocks for the same day AND a similar title, because
      series and festivals reuse one design for different acts and dates.
    """
    today = today or datetime.now(CHENNAI).date().isoformat()
    for m in matches:
        if m["status"] not in ("published", "review") or m["distance"] is None:
            continue
        day = _day(m.get("date"))
        if day and day < today:
            continue
        if m["distance"] <= IDENTICAL_POSTER_BITS:
            return m
        if m["same_poster"] and m["same_day"] and m["title_similarity"] >= 0.6:
            return m
    return None


def duplicate_message(match: Dict[str, Any]) -> str:
    if match.get("status") == "published":
        return "This event is already on the map."
    return "This event has already been submitted and is waiting for review."
