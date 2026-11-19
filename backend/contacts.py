"""
backend/contacts.py - Clean up organiser contact details read off posters or typed in.

Each function returns a tidy value, or None when the input isn't usable.
"""
import re
from typing import Optional
from urllib.parse import urlparse

_INSTAGRAM_HANDLE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_DOMAIN_LIKE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+(/\S*)?$", re.IGNORECASE)


def normalize_phone(value: Optional[str]) -> Optional[str]:
    """Indian mobile or landline -> '+91XXXXXXXXXX'. Other countries keep their '+' code."""
    text = (value or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if text.startswith("+") and not digits.startswith("91"):
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    if digits.startswith("0091"):
        digits = digits[4:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]  # 044 2345 6789 / 098765 43210
    if len(digits) != 10 or digits[0] == "0":
        return None
    return f"+91{digits}"


def normalize_instagram(value: Optional[str]) -> Optional[str]:
    """'@chennai.gigs', 'instagram.com/chennai.gigs/' or 'chennai.gigs' -> 'chennai.gigs'."""
    text = (value or "").strip()
    if not text:
        return None
    if "instagram.com" in text.lower():
        url = text if "://" in text else f"https://{text}"
        parts = [p for p in urlparse(url).path.split("/") if p]
        if not parts or parts[0] in ("p", "reel", "reels", "stories", "explore"):
            return None
        text = parts[0]
    text = text.lstrip("@").strip().rstrip("/")
    if not _INSTAGRAM_HANDLE.match(text) or text.startswith(".") or text.endswith("."):
        return None
    return text


def normalize_link(value: Optional[str]) -> Optional[str]:
    """Booking links printed on posters often lack 'https://' (e.g. 'bit.ly/xyz')."""
    text = (value or "").strip()
    if not text:
        return None
    if "://" not in text and _DOMAIN_LIKE.match(text):
        text = f"https://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return text
