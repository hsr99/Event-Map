#!/usr/bin/env python3
"""
extract_poster.py - rule-based event field extraction from posters (Tesseract OCR).

Fields: event_name, date, time, venue, area, ticket_price, booking_link, category.
Anything it can't find is null (never guessed). Every field gets a rough confidence,
and `needs_review` lists fields a human should check.

Setup
-----
    pip install pytesseract pillow
    + install the Tesseract engine itself:
        Windows: https://github.com/UB-Mannheim/tesseract/wiki  (then pass --tesseract-cmd
                 "C:\\Program Files\\Tesseract-OCR\\tesseract.exe" if it isn't on PATH)
        macOS:   brew install tesseract
        Ubuntu:  sudo apt install tesseract-ocr
    For Tamil text also install the 'tam' language data and use:  --lang eng+tam

Usage
-----
    python extract_poster.py poster.jpg
    python extract_poster.py posters/ --out results.json --csv results.csv
    python extract_poster.py posters/ --post-date 2026-10-05   # used to infer missing years

Honest limitation: OCR + rules works on clean, text-heavy posters and degrades fast on
artsy fonts, busy backgrounds, and stylised dates. Use it as a baseline to compare
against vision LLMs, not as the final engine.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image, ImageOps

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

CHENNAI_AREAS = [
    "Adyar", "Alwarpet", "Ambattur", "Anna Nagar", "Ashok Nagar", "Besant Nagar",
    "Chetpet", "Chromepet", "Egmore", "ECR", "Guindy", "Kilpauk", "Kodambakkam",
    "Kotturpuram", "Mandaveli", "Medavakkam", "Mogappair", "Mylapore", "Navalur",
    "Nungambakkam", "OMR", "Pallavaram", "Perambur", "Perungudi", "Porur",
    "Royapettah", "Saidapet", "Sholinganallur", "T Nagar", "Tambaram", "St Thomas Mount",
    "Teynampet", "Thiruvanmiyur", "Thoraipakkam", "Vadapalani", "Velachery",
    "Villivakkam", "Washermanpet", "Kelambakkam", "Siruseri", "Kovalam",
    "Triplicane", "George Town", "Poonamallee", "Avadi", "Sriperumbudur",
]
AREA_ALIASES = {a.lower(): a for a in CHENNAI_AREAS}
AREA_ALIASES.update({
    "tnagar": "T Nagar", "thyagaraya nagar": "T Nagar", "besant nagar": "Besant Nagar",
    "bessie": "Besant Nagar", "old mahabalipuram road": "OMR",
    "east coast road": "ECR", "thiruvanmiyur": "Thiruvanmiyur",
})

CATEGORY_KEYWORDS = {
    "tech": ["hackathon", "developer", "developers", "devops", "coding", "startup",
             "startups", "python", "cloud", "cybersecurity", "web3", "gdg", "ai",
             "ml", "data science", "tech", "open source", "llm", "genai"],
    "music": ["concert", "live music", "gig", "band", "dj", "open mic", "jam",
              "unplugged", "carnatic", "classical", "festival", "music"],
    "comedy": ["comedy", "stand-up", "standup", "stand up", "roast", "improv"],
    "art_workshop": ["workshop", "art", "painting", "pottery", "craft", "calligraphy",
                     "photography", "design", "sketch", "dance workshop"],
    "sports_fitness": ["run", "marathon", "cyclothon", "yoga", "football", "cricket",
                       "badminton", "fitness", "trek", "sports", "tournament"],
    "food_drink": ["food", "brunch", "tasting", "pop-up", "popup", "wine", "beer",
                   "coffee", "baking", "cook", "culinary"],
    "networking_business": ["networking", "founders", "entrepreneur", "summit",
                            "conference", "career", "mixer", "investor"],
    "film_theatre": ["screening", "film", "movie", "theatre", "theater", "play",
                     "drama", "cinema"],
    "community_social": ["meetup", "meet-up", "meet up", "community", "social",
                         "book club", "games night", "board games", "walk", "volunteer"],
}

VENUE_WORDS = re.compile(
    r"\b(hall|auditorium|cafe|café|studio|club|park|mall|centre|center|campus|college|"
    r"university|beach|hotel|theatre|theater|arena|stadium|lounge|bar|brewery|gallery|"
    r"museum|library|school|institute|ground|grounds|hub|space|foundation|society|"
    r"rooftop|terrace|resort|convention|bookstore|roastery|kitchen|garden)\b", re.I)

BOOKING_HOST_HINTS = (
    "insider.in", "bookmyshow", "lu.ma", "luma.com", "townscript", "eventbrite",
    "konfhub", "meetup.com", "forms.gle", "docs.google", "bit.ly", "linktr.ee",
    "tinyurl", "rzp.io", "razorpay", "unstop", "devfolio", "hasgeek", "allevents",
    "paytm", "bookmyshow.com", "tix", "register", "tickets",
)
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "twitter.com", "x.com", "youtube.com")

# --------------------------------------------------------------------------- #
# Regexes
# --------------------------------------------------------------------------- #
ORD = r"(?:st|nd|rd|th)?"
NOT_TIME = r"(?!\s*(?::|\.\d|am\b|pm\b|a\.m|p\.m))"
SEP = r"(?:[-–—&,]|to)"

DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}}){ORD}\s*(?:{SEP}\s*(\d{{1,2}}){ORD}{NOT_TIME})?\s*(?:of\s+)?"
    rf"({MONTH_RE})\b\.?(?:\s*,?\s*(\d{{4}}))?", re.I)
MONTH_DAY = re.compile(
    rf"\b({MONTH_RE})\b\.?\s*(\d{{1,2}}){ORD}(?!\d){NOT_TIME}"
    rf"(?:\s*{SEP}\s*(\d{{1,2}}){ORD}(?!\d){NOT_TIME})?(?:\s*,?\s*(\d{{4}}))?", re.I)
NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})\b")

TIME_RANGE = re.compile(
    r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\s*(?:-|–|—|to|till|until)\s*"
    r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", re.I)
TIME_SINGLE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", re.I)
TIME_24 = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")

FREE_RE = re.compile(
    r"\bfree\s+(?:entry|entrance|admission|registration|event|pass|to\s+attend)\b|"
    r"\bentry\s+free\b|\badmission\s+free\b|\bno\s+(?:entry\s+)?(?:fee|charge)s?\b|"
    r"^\s*free\s*!?\s*$", re.I | re.M)
AMOUNT_RE = re.compile(r"(?:₹|\b(?:rs|inr)\b\.?)\s*(\d[\d,]*)|\b(\d[\d,]*)\s*/-", re.I)
# OCR often turns the rupee sign into garbage, so also accept "ticket ... 299".
LOOSE_PRICE_RE = re.compile(
    r"\b(?:tickets?|entry|pass|price|fee|registration)s?\s*(?:from|at|@|:|-)?\s*\W{0,2}\s*(\d{2,5})\b",
    re.I)

URL_RE = re.compile(
    r"(?<![@\w.])((?:https?://|www\.)[^\s<>\"']+|(?:[a-z0-9-]+\.)+"
    r"(?:com|in|co|io|org|net|app|link|ly|me|ma|gl|ee|gle|events|fyi|page|xyz)"
    r"(?:/[^\s<>\"']*)?)", re.I)
LINK_IN_BIO = re.compile(r"link\s+in\s+(?:the\s+)?bio|bio\s+link", re.I)

LABELLED_VENUE = re.compile(r"^\s*(?:venue|location|where)\s*[:\-–]\s*(.+)$", re.I)
LABEL_ONLY = re.compile(r"^\s*(?:venue|location|where)\s*[:\-–]?\s*$", re.I)
AT_VENUE = re.compile(r"^\s*(?:at|@)\s+(.{4,})$", re.I)


# --------------------------------------------------------------------------- #
# OCR layer
# --------------------------------------------------------------------------- #
@dataclass
class Word:
    text: str
    conf: float
    left: int
    top: int
    width: int
    height: int


@dataclass
class Line:
    text: str
    conf: float      # mean word confidence, 0-100
    height: float    # median word height in px (proxy for font size)
    top: int
    left: int


def preprocess_variants(img: Image.Image, fast: bool) -> dict:
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    longest = max(w, h)
    if longest < 1600:
        scale = 1600 / longest
    elif longest > 3200:
        scale = 3200 / longest
    else:
        scale = 1.0
    if scale != 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    variants = {"gray": gray}
    if not fast:
        variants["inverted"] = ImageOps.invert(gray)   # light text on dark background
        variants["thresh"] = gray.point(lambda p: 255 if p > 140 else 0)
    return variants


def run_ocr(img: Image.Image, lang: str, psm: int) -> list[Word]:
    data = pytesseract.image_to_data(
        img, lang=lang, config=f"--oem 3 --psm {psm}",
        output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not text or conf < 0:
            continue
        words.append(Word(text, conf, data["left"][i], data["top"][i],
                          data["width"][i], data["height"][i]))
    return words


def best_ocr(img: Image.Image, lang: str, psm: int, fast: bool):
    """Try a few preprocessing variants, keep the one with the best confidence."""
    best = None
    for name, variant in preprocess_variants(img, fast).items():
        words = run_ocr(variant, lang, psm)
        if not words:
            continue
        mean = statistics.fmean(w.conf for w in words)
        score = mean * math.log(1 + len(words))
        if best is None or score > best[0]:
            best = (score, name, words, variant.size)
    if best is None:
        return "none", [], img.size
    return best[1], best[2], best[3]


def group_lines(words: list[Word]) -> list[Line]:
    """Cluster words into visual lines, splitting wide horizontal gaps (columns)."""
    words = sorted(words, key=lambda w: w.top + w.height / 2)
    rows: list[dict] = []
    for w in words:
        cy = w.top + w.height / 2
        for row in rows:
            if abs(cy - row["cy"]) < max(row["h"], w.height) * 0.6:
                row["words"].append(w)
                n = len(row["words"])
                row["cy"] += (cy - row["cy"]) / n
                row["h"] = max(row["h"], w.height)
                break
        else:
            rows.append({"cy": cy, "h": w.height, "words": [w]})

    lines: list[Line] = []
    for row in rows:
        ws = sorted(row["words"], key=lambda w: w.left)
        segment = [ws[0]]
        segments = []
        for prev, cur in zip(ws, ws[1:]):
            gap = cur.left - (prev.left + prev.width)
            if gap > 2.5 * max(prev.height, cur.height):
                segments.append(segment)
                segment = []
            segment.append(cur)
        segments.append(segment)
        for seg in segments:
            text = " ".join(w.text for w in seg)
            lines.append(Line(
                text=text,
                conf=statistics.fmean(w.conf for w in seg),
                height=statistics.median(w.height for w in seg),
                top=min(w.top for w in seg),
                left=min(w.left for w in seg)))
    return sorted(lines, key=lambda l: (l.top, l.left))


# --------------------------------------------------------------------------- #
# Field extractors. Each returns (value, confidence) or (None, 0.0).
# --------------------------------------------------------------------------- #
def conf_score(weight: float, line_conf: float) -> float:
    return round(weight * (0.6 + 0.4 * line_conf / 100), 2)


class Text:
    """Full text with a map from character offset back to the source line."""

    def __init__(self, lines: list[Line]):
        self.lines = lines
        self.full = "\n".join(l.text for l in lines)
        self.offsets, pos = [], 0
        for l in lines:
            self.offsets.append(pos)
            pos += len(l.text) + 1

    def line_conf_at(self, pos: int) -> float:
        idx = 0
        for i, off in enumerate(self.offsets):
            if off <= pos:
                idx = i
        return self.lines[idx].conf if self.lines else 0.0


def resolve_year(day: int, month: int, year: Optional[int], ref: date):
    """If the poster has no year, take the next occurrence (allowing slightly past dates)."""
    inferred = year is None
    if year is None:
        year = ref.year
        try:
            if date(year, month, day) < ref - timedelta(days=60):
                year += 1
        except ValueError:
            return None, inferred
    elif year < 100:
        year += 2000
    try:
        return date(year, month, day), inferred
    except ValueError:
        return None, inferred


def extract_date(t: Text, ref: date):
    found = []   # (position, start_date, end_date, inferred, line_conf)
    for m in DAY_MONTH.finditer(t.full):
        d1, d2, mon, yr = m.group(1), m.group(2), m.group(3), m.group(4)
        found.append((m.start(), int(d1), int(d2) if d2 else None,
                      MONTHS[mon.lower()], int(yr) if yr else None))
    for m in MONTH_DAY.finditer(t.full):
        mon, d1, d2, yr = m.group(1), m.group(2), m.group(3), m.group(4)
        found.append((m.start(), int(d1), int(d2) if d2 else None,
                      MONTHS[mon.lower()], int(yr) if yr else None))
    for m in NUMERIC_DATE.finditer(t.full):          # assumed DD/MM/YYYY (India)
        d, mo, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12:
            found.append((m.start(), d, None, mo, yr))
    found.sort(key=lambda x: x[0])

    results = []
    for pos, d1, d2, mon, yr in found:
        start, inferred = resolve_year(d1, mon, yr, ref)
        if start is None:
            continue
        end = None
        if d2 and d2 > d1:
            end, _ = resolve_year(d2, mon, yr, ref)
        results.append((start, end, inferred, t.line_conf_at(pos)))
    if not results:
        return None, None, 0.0, []
    start, end, inferred, lc = results[0]
    weight = 0.7 if inferred else 0.9
    others = sorted({r[0].isoformat() for r in results[1:] if r[0] != start})
    return start.isoformat(), end.isoformat() if end else None, conf_score(weight, lc), others


def to_24h(hour: int, minute: int, meridiem: Optional[str]) -> Optional[str]:
    if meridiem:
        meridiem = meridiem.lower()
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def preceded_by_month(text: str, pos: int) -> bool:
    return bool(re.search(rf"({MONTH_RE})\.?[ \t]*\Z", text[max(0, pos - 8):pos], re.I))


def extract_time(t: Text):
    for m in TIME_RANGE.finditer(t.full):
        if preceded_by_month(t.full, m.start()):    # "Oct 11 - 6 PM" is not a time range
            continue
        h1, m1, p1, h2, m2, p2 = m.groups()
        p1 = p1 or p2
        start = to_24h(int(h1), int(m1 or 0), p1)
        end = to_24h(int(h2), int(m2 or 0), p2)
        if start and end:
            return start, end, conf_score(0.9, t.line_conf_at(m.start()))
    for m in TIME_SINGLE.finditer(t.full):
        if preceded_by_month(t.full, m.start()):
            continue
        h, mi, p = m.groups()
        start = to_24h(int(h), int(mi or 0), p)
        if start:
            return start, None, conf_score(0.85, t.line_conf_at(m.start()))
    for m in TIME_24.finditer(t.full):
        return to_24h(int(m.group(1)), int(m.group(2)), None), None, \
            conf_score(0.5, t.line_conf_at(m.start()))
    return None, None, 0.0


def extract_price(t: Text):
    m = FREE_RE.search(t.full)
    if m:
        return "Free", conf_score(0.85, t.line_conf_at(m.start()))
    amounts, confs = [], []
    for m in AMOUNT_RE.finditer(t.full):
        raw = (m.group(1) or m.group(2)).replace(",", "")
        try:
            val = int(float(raw))
        except ValueError:
            continue
        if 0 < val < 100000:
            amounts.append(val)
            confs.append(t.line_conf_at(m.start()))
    weight = 0.85
    if not amounts:                                  # garbled rupee sign fallback
        for m in LOOSE_PRICE_RE.finditer(t.full):
            amounts.append(int(m.group(1)))
            confs.append(t.line_conf_at(m.start()))
        weight = 0.45
    if not amounts:
        return None, 0.0
    lo, hi = min(amounts), max(amounts)
    value = f"₹{lo}" if lo == hi else f"₹{lo}–₹{hi}"
    return value, conf_score(weight, statistics.fmean(confs))


def extract_link(t: Text):
    candidates = []
    for m in URL_RE.finditer(t.full):
        url = m.group(1).rstrip(".,;:)!?")
        low = url.lower()
        if any(s in low for s in SOCIAL_HOSTS):
            continue
        hinted = any(h in low for h in BOOKING_HOST_HINTS)
        candidates.append((0 if hinted else 1, m.start(), url, t.line_conf_at(m.start())))
    note = "link in bio" if LINK_IN_BIO.search(t.full) else None
    if not candidates:
        return None, 0.0, note
    candidates.sort()
    _, _, url, lc = candidates[0]
    return url, conf_score(0.8 if candidates[0][0] == 0 else 0.6, lc), note


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def extract_area(t: Text):
    norm_lines = [normalise(l.text) for l in t.lines]
    for alias in sorted(AREA_ALIASES, key=len, reverse=True):
        pat = re.compile(rf"\b{re.escape(normalise(alias))}\b")
        for line, norm in zip(t.lines, norm_lines):
            if pat.search(norm):
                return AREA_ALIASES[alias], conf_score(0.9, line.conf)
    keys = [normalise(a) for a in AREA_ALIASES]       # fuzzy pass for OCR typos
    for line, norm in zip(t.lines, norm_lines):
        tokens = norm.split()
        for n in (1, 2):
            for i in range(len(tokens) - n + 1):
                gram = " ".join(tokens[i:i + n])
                if len(gram) < 5:
                    continue
                hit = get_close_matches(gram, keys, n=1, cutoff=0.84)
                if hit:
                    alias = list(AREA_ALIASES)[keys.index(hit[0])]
                    return AREA_ALIASES[alias], conf_score(0.6, line.conf)
    return None, 0.0


def is_meta_line(text: str) -> bool:
    """Lines that are date/time/price/link rather than a name or venue."""
    return bool(
        DAY_MONTH.search(text) or MONTH_DAY.search(text) or NUMERIC_DATE.search(text)
        or TIME_SINGLE.search(text) or TIME_RANGE.search(text) or TIME_24.search(text)
        or AMOUNT_RE.search(text) or FREE_RE.search(text) or URL_RE.search(text))


def extract_venue(t: Text, name_lines: set[int]):
    lines = t.lines
    for i, l in enumerate(lines):
        m = LABELLED_VENUE.match(l.text)
        if m:
            return m.group(1).strip(), conf_score(0.9, l.conf)
        if LABEL_ONLY.match(l.text) and i + 1 < len(lines):
            return lines[i + 1].text.strip(), conf_score(0.85, lines[i + 1].conf)

    best = None
    for i, l in enumerate(lines):
        if i in name_lines or is_meta_line(l.text) or l.conf < 35:
            continue
        hits = len(VENUE_WORDS.findall(l.text))
        if hits:
            score = hits + (0.5 if "," in l.text else 0)
            if best is None or score > best[0]:
                best = (score, i)
    if best:
        i = best[1]
        text = re.sub(r"^\s*(?:at|@)\s+", "", lines[i].text.strip(), flags=re.I)
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt and not is_meta_line(nxt.text) and (
                "chennai" in nxt.text.lower() or extract_area(Text([nxt]))[0]):
            text += ", " + nxt.text.strip()
        return text, conf_score(0.6, lines[i].conf)

    for i, l in enumerate(lines):
        m = AT_VENUE.match(l.text)
        if m and not is_meta_line(l.text) and i not in name_lines:
            return m.group(1).strip(), conf_score(0.5, l.conf)
    return None, 0.0


def extract_name(t: Text, image_height: int):
    """Largest-font text in the upper part of the poster, merging adjacent similar lines."""
    cands = []
    for i, l in enumerate(t.lines):
        letters = sum(c.isalpha() for c in l.text)
        compact = len(l.text.replace(" ", ""))
        if (letters >= 3 and compact and letters / compact >= 0.6 and l.conf >= 35
                and l.top < image_height * 0.75 and not is_meta_line(l.text)):
            cands.append((i, l))
    if not cands:
        return None, 0.0, set()
    seed_pos = max(range(len(cands)), key=lambda k: cands[k][1].height)
    seed = cands[seed_pos][1]

    def close(a: Line, b: Line) -> bool:
        similar = abs(a.height - seed.height) <= 0.3 * seed.height
        adjacent = abs(a.top - b.top) <= 2.2 * seed.height
        return similar and adjacent

    chosen = [seed_pos]
    k = seed_pos - 1
    while k >= 0 and close(cands[k][1], cands[chosen[0]][1]):
        chosen.insert(0, k)
        k -= 1
    k = seed_pos + 1
    while k < len(cands) and close(cands[k][1], cands[chosen[-1]][1]):
        chosen.append(k)
        k += 1
    parts = [cands[k][1] for k in chosen]
    name = re.sub(r"\s+", " ", " ".join(p.text for p in parts)).strip(" -–—|:.,")
    conf = conf_score(0.75, statistics.fmean(p.conf for p in parts))
    return name[:100] or None, conf, {cands[k][0] for k in chosen}


def extract_category(t: Text):
    low = t.full.lower()
    scores = {}
    for cat, words in CATEGORY_KEYWORDS.items():
        n = sum(len(re.findall(rf"\b{re.escape(w)}\b", low)) for w in words)
        if n:
            scores[cat] = n
    if not scores:
        return None, 0.0
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = ranked[0]
    tie = len(ranked) > 1 and ranked[1][1] == top[1]
    return top[0], 0.4 if tie else min(0.75, 0.45 + 0.1 * top[1])


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def extract_poster(path: Path, lang: str, psm: int, ref: date, fast: bool) -> dict:
    img = Image.open(path)
    variant, words, size = best_ocr(img, lang, psm, fast)
    lines = group_lines(words)
    t = Text(lines)

    name, name_c, name_lines = extract_name(t, size[1])
    date_start, date_end, date_c, other_dates = extract_date(t, ref)
    time_start, time_end, time_c = extract_time(t)
    venue, venue_c = extract_venue(t, name_lines)
    area, area_c = extract_area(t)
    price, price_c = extract_price(t)
    link, link_c, link_note = extract_link(t)
    category, cat_c = extract_category(t)

    ocr_conf = round(statistics.fmean(w.conf for w in words), 1) if words else 0.0
    notes = []
    if other_dates:
        notes.append(f"other dates found: {', '.join(other_dates)}")
    if link_note:
        notes.append(link_note)
    if date_start and date_c and date_c < 0.8 and not re.search(r"\b20\d\d\b", t.full):
        notes.append("year not on poster; inferred from --post-date")

    result = {
        "file": str(path),
        "event_name": name, "date": date_start, "date_end": date_end,
        "time": time_start, "time_end": time_end,
        "venue": venue, "area": area, "ticket_price": price,
        "booking_link": link, "category": category,
        "confidence": {
            "event_name": name_c, "date": date_c, "time": time_c, "venue": venue_c,
            "area": area_c, "ticket_price": price_c, "booking_link": link_c,
            "category": cat_c,
        },
        "ocr_confidence": ocr_conf,
        "ocr_variant": variant,
        "notes": notes,
    }
    review = []
    if not words:
        review.append("no_text_found")
    for field in ("event_name", "date"):
        if result[field] is None or result["confidence"][field] < 0.55:
            review.append(field)
    if result["venue"] is None and result["area"] is None:
        review.append("venue_or_area")
    elif result["venue"] and result["confidence"]["venue"] < 0.55:
        review.append("venue")
    if ocr_conf < 55:
        review.append("low_ocr_quality")
    result["needs_review"] = review
    result["raw_text"] = t.full
    return result


def find_images(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


CSV_FIELDS = ["file", "event_name", "date", "date_end", "time", "time_end", "venue",
              "area", "ticket_price", "booking_link", "category", "ocr_confidence",
              "needs_review"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract event fields from posters with Tesseract.")
    ap.add_argument("path", type=Path, help="poster image or folder of posters")
    ap.add_argument("--out", type=Path, default=Path("results.json"), help="JSON output path")
    ap.add_argument("--csv", type=Path, help="optional CSV output path")
    ap.add_argument("--lang", default="eng", help="Tesseract language(s), e.g. eng+tam")
    ap.add_argument("--psm", type=int, default=11,
                    help="page segmentation mode (11 = sparse text, good for posters)")
    ap.add_argument("--post-date", type=date.fromisoformat, default=date.today(),
                    help="YYYY-MM-DD, used to infer the year when posters omit it")
    ap.add_argument("--fast", action="store_true", help="single OCR pass (grayscale only)")
    ap.add_argument("--tesseract-cmd", help="full path to the tesseract executable")
    ap.add_argument("--no-raw", action="store_true", help="omit raw OCR text from the JSON")
    args = ap.parse_args()

    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        sys.exit("Tesseract engine not found. Install it (see the header of this file) "
                 "or pass --tesseract-cmd with the path to tesseract.exe.")

    images = find_images(args.path)
    if not images:
        sys.exit(f"No images found at {args.path}")

    results = []
    for n, path in enumerate(images, 1):
        print(f"[{n}/{len(images)}] {path.name}", file=sys.stderr)
        try:
            res = extract_poster(path, args.lang, args.psm, args.post_date, args.fast)
        except Exception as exc:                       # keep going on a bad file
            res = {"file": str(path), "error": str(exc), "needs_review": ["error"]}
        if args.no_raw:
            res.pop("raw_text", None)
        results.append(res)

    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(results)} result(s) to {args.out}", file=sys.stderr)

    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                row = dict(r)
                row["needs_review"] = ";".join(r.get("needs_review", []))
                writer.writerow(row)
        print(f"Wrote CSV to {args.csv}", file=sys.stderr)

    flagged = sum(1 for r in results if r.get("needs_review"))
    print(f"{flagged}/{len(results)} poster(s) flagged for review.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())