"""
backend/main.py - FastAPI server for the Chennai Event Map.

Run from the repo root:
    uvicorn backend.main:app --reload --port 8000

Visitors read published events straight from Supabase; this API handles the
things that need secrets or validation: poster extraction, submissions (which
land in the review queue), reports, and the admin review desk (/api/admin/*,
protected by ADMIN_TOKEN).
"""
import hashlib
import hmac
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import dedupe, store
from backend.contacts import normalize_instagram, normalize_link, normalize_phone
from backend.extractor import extract_poster_details
from backend.geocoder import resolve_venue_coordinates
from backend.posters import MAX_POSTER_BYTES, InvalidPoster, inspect_poster
from backend.ratelimit import client_ip, enforce, limiter

app = FastAPI(
    title="Gathr Chennai Event Map API",
    description="Poster extraction, event submissions, reports and review for the Chennai Event Map.",
    version="2.1.0",
)

# Comma-separated list of sites allowed to call this API from a browser.
DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:5179,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Rough box around greater Chennai; pins outside it are almost certainly typos.
LAT_RANGE = (12.4, 13.6)
LNG_RANGE = (79.6, 80.6)

# Poster reading uses the free vision-model quota: cap it per visitor and overall,
# so one script can't use it all up. Submissions and reports are capped per visitor.
# "Per visitor" means per IP address, and mobile networks put many people behind
# one address, so these only stop floods; the overall cap protects the quota.
READS_PER_VISITOR = (40, 15 * 60)    # 40 reads per 15 minutes
READS_OVERALL = (200, 60 * 60)       # 200 reads per hour across everyone
SUBMITS_PER_VISITOR = (40, 60 * 60)
REPORTS_PER_VISITOR = (40, 60 * 60)
SLOW_DOWN = "Too many requests from your connection. Please wait a few minutes and try again."


def reading_allowed() -> bool:
    return limiter.allow("reads:all", *READS_OVERALL)


@app.exception_handler(store.StoreNotConfigured)
async def store_not_configured(_: Request, exc: store.StoreNotConfigured):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def read_poster(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_POSTER_BYTES + 1)
    try:
        inspect_poster(data)
    except InvalidPoster as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return data


def clean_text(value: Optional[str], field: str, max_len: int, required: bool = False) -> str:
    text = (value or "").strip()
    if required and not text:
        raise HTTPException(status_code=422, detail=f"{field} is required.")
    if len(text) > max_len:
        raise HTTPException(status_code=422, detail=f"{field} must be at most {max_len} characters.")
    return text


def parse_datetime(value: Optional[str], field: str, required: bool = False) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        if required:
            raise HTTPException(status_code=422, detail=f"{field} is required.")
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be an ISO date-time.") from exc
    if parsed.tzinfo is None:
        text += "+05:30"  # form inputs are Chennai local time
    return text


def check_link(value: Optional[str]) -> str:
    link = clean_text(value, "Booking link", 500)
    if not link:
        return link
    fixed = normalize_link(link)  # 'bit.ly/xyz' -> 'https://bit.ly/xyz'
    if not fixed:
        raise HTTPException(status_code=422, detail="Booking link must be a web address, e.g. https://...")
    return fixed


def check_category(value: Optional[str]) -> Optional[str]:
    category = (value or "").strip()
    if category and category not in store.CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown category.")
    return category or None


def locate(venue: Optional[str], area: Optional[str]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Pin a venue/area. Returns (venue, area, geo); geo is {} when there's nothing to go on."""
    if not venue and not area:
        return venue or None, area or None, {}
    geo = resolve_venue_coordinates(venue or "", area or "")
    venue = geo.get("venue") or venue or None
    if geo["precision"] == "venue" or not area:
        area = geo["area"]
    return venue, area, geo


def from_extraction(details: Dict[str, Any]) -> Dict[str, Any]:
    """The extracted fields we can trust: things the model actually read off the poster.

    The extractor fills gaps with guesses (today's date, a title from the
    filename); those are dropped here so they're left blank for review instead.
    """
    if details.get("backend") == "heuristic":
        return {}
    raw = details.get("raw") or {}
    out: Dict[str, Any] = {}
    if raw.get("event_name"):
        out["title"] = details["title"][:200]
    if raw.get("category"):
        out["category"] = details["category"]
    if raw.get("date"):
        out["date"], out["end_date"] = details["date"], details.get("end_date")
    for key in ("venue", "area", "description"):
        if details.get(key):
            out[key] = details[key]
    if raw.get("ticket_price"):
        out["price"], out["is_free"] = details["price"], details["is_free"]
    for key, clean in (("booking_link", normalize_link), ("contact_phone", normalize_phone),
                       ("instagram", normalize_instagram)):
        value = clean(details.get(key))
        if value:
            out[key] = value
    return out


def check_phone(value: Optional[str]) -> Optional[str]:
    if not (value or "").strip():
        return None
    phone = normalize_phone(value)
    if not phone:
        raise HTTPException(status_code=422, detail="That phone number doesn't look right. Use a 10-digit number.")
    return phone


def check_instagram(value: Optional[str]) -> Optional[str]:
    if not (value or "").strip():
        return None
    handle = normalize_instagram(value)
    if not handle:
        raise HTTPException(status_code=422, detail="That Instagram handle doesn't look right, e.g. @chennaigigs.")
    return handle


def already_there(status: Optional[str]) -> str:
    if status in ("published", "review"):
        return dedupe.duplicate_message({"status": status})
    return "This poster has already been submitted."


def describe_missing(fields) -> str:
    """['venue', 'area', 'date', 'lat', 'lng'] -> 'date, venue and map pin'."""
    names = []
    for f in ("title", "date", "venue", "area", "category", "lat", "lng"):
        if f not in fields:
            continue
        if f == "area" and "venue" in fields:
            continue  # implied by the venue
        name = "map pin" if f in ("lat", "lng") else f
        if name not in names:
            names.append(name)
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


# --------------------------------------------------------------------------- #
# Public routes
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health_check():
    return {"status": "ok", "storage_configured": store.is_configured()}


@app.get("/api/events")
def list_events(
    category: Optional[str] = Query(None, description="Category filter (concerts, tech-events, ...)"),
    area: Optional[str] = Query(None, description="Chennai area filter"),
    is_free: Optional[bool] = Query(None, description="Only free (true) or ticketed (false) events"),
    q: Optional[str] = Query(None, max_length=100, description="Search title, venue, area, description"),
):
    """Published events, soonest first."""
    return store.list_events(category=category, area=area, is_free=is_free, query=q)


@app.get("/api/events/{event_id}")
def get_event(event_id: int):
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/api/extract")
async def extract_poster(request: Request, poster: UploadFile = File(...)):
    """Read a poster with the vision models and return suggested form values. Stores nothing.

    Fields the model couldn't read come back blank and are listed in `needs_review`.
    """
    enforce(request, "read", *READS_PER_VISITOR, SLOW_DOWN)
    data = await read_poster(poster)
    if not reading_allowed():
        raise HTTPException(status_code=503, detail="Poster reading is busy right now. Fill in the details by hand, or try again later.")
    details = await run_in_threadpool(extract_poster_details, data, poster.filename or "")
    found = from_extraction(details)

    venue, area, geo = locate(found.get("venue"), found.get("area"))
    result = {
        "title": found.get("title", ""),
        "category": found.get("category", ""),
        "date": found.get("date", ""),
        "end_date": found.get("end_date"),
        "venue": venue or "",
        "area": area or "",
        "description": found.get("description", ""),
        "booking_link": found.get("booking_link", ""),
        "contact_phone": found.get("contact_phone", ""),
        "instagram": found.get("instagram", ""),
        "needs_review": details.get("needs_review", []),
        "backend": details.get("backend"),
        "lat": geo.get("lat"),
        "lng": geo.get("lng"),
        "location_precision": geo.get("precision"),
    }
    if "price" in found:
        result.update(price=found["price"], is_free=found["is_free"], isFree=found["is_free"])
    return result


@app.post("/api/submit", status_code=201)
async def submit_event(
    request: Request,
    poster: Optional[UploadFile] = File(None),
    title: Optional[str] = Form(""),
    category: Optional[str] = Form(""),
    venue: Optional[str] = Form(""),
    area: Optional[str] = Form(""),
    date: Optional[str] = Form(""),
    end_date: Optional[str] = Form(""),
    price: Optional[str] = Form(""),
    is_free: Optional[str] = Form(""),
    description: Optional[str] = Form(""),
    booking_link: Optional[str] = Form(""),
    contact_phone: Optional[str] = Form(""),
    instagram: Optional[str] = Form(""),
    contact: Optional[str] = Form(""),
):
    """Submit an event. A poster on its own is enough: blank fields are read from it.

    Everything is saved as 'review' and appears on the site once approved.
    """
    enforce(request, "submit", *SUBMITS_PER_VISITOR, SLOW_DOWN)
    price_text = (price or "").strip()
    price_value: Optional[int] = None
    if price_text:
        try:
            price_value = int(float(price_text))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Price must be a number.") from exc
        if price_value < 0:
            raise HTTPException(status_code=422, detail="Price can't be negative.")
    free = (is_free or "").strip().lower() in ("true", "1", "on", "yes")

    event: Dict[str, Any] = {
        "title": clean_text(title, "Title", 200) or None,
        "category": check_category(category),
        "venue": clean_text(venue, "Venue", 200) or None,
        "area": clean_text(area, "Area", 100) or None,
        "date": parse_datetime(date, "Date"),
        "end_date": parse_datetime(end_date, "End date"),
        "description": clean_text(description, "Description", 2000),
        "booking_link": check_link(booking_link),
        "contact_phone": check_phone(contact_phone),
        "instagram": check_instagram(instagram),
        "status": "review",
    }
    contact_text = clean_text(contact, "Contact", 200)

    data = poster_info = None
    candidates = None
    if poster and poster.filename:
        data = await read_poster(poster)
        poster_info = inspect_poster(data)
        existing = store.find_submission_by_hash(poster_info.sha256)
        if existing:
            raise HTTPException(status_code=409, detail=already_there(existing.get("status")))
        # A resized or re-saved copy of a poster we already have: stop before reading it again.
        candidates = store.dedupe_candidates()
        early = dedupe.blocking_match(dedupe.find_matches(event, poster_info.fingerprint, candidates))
        if early:
            raise HTTPException(status_code=409, detail=dedupe.duplicate_message(early))
    elif not (event["title"] and event["date"] and event["venue"]):
        raise HTTPException(status_code=422, detail="Add a poster, or fill in the event title, date and venue.")

    # Read whatever the submitter left blank off the poster.
    extracted_raw = None
    found: Dict[str, Any] = {}
    gaps = [k for k in ("title", "category", "venue", "area", "date") if not event[k]]
    # If reading is over its overall cap, save anyway: the gaps get filled in review.
    if poster_info and (gaps or (price_value is None and not free)) and reading_allowed():
        details = await run_in_threadpool(extract_poster_details, data, poster.filename or "")
        extracted_raw = details.get("raw")
        found = from_extraction(details)
        for key in ("title", "category", "venue", "area", "date", "end_date", "description",
                    "booking_link", "contact_phone", "instagram"):
            if not event.get(key) and found.get(key):
                event[key] = found[key]

    if free:
        event["price"], event["is_free"] = 0, True
    elif price_value is not None:
        event["price"], event["is_free"] = price_value, price_value == 0
    elif "price" in found:
        event["price"], event["is_free"] = found["price"], found["is_free"]
    else:
        event["price"], event["is_free"] = 0, True

    event["venue"], event["area"], geo = locate(event["venue"], event["area"])
    event["lat"], event["lng"] = geo.get("lat"), geo.get("lng")

    # Same poster for the same day, now that we know the date. Lookalikes with a
    # different poster or date still go through; they're flagged on the review page.
    if poster_info:
        match = dedupe.blocking_match(dedupe.find_matches(event, poster_info.fingerprint, candidates or []))
        if match:
            raise HTTPException(status_code=409, detail=dedupe.duplicate_message(match))
        event["image_url"] = store.upload_poster(data, poster_info)

    try:
        created = store.create_event(
            event,
            source="web_form",
            poster=poster_info,
            extracted_data=extracted_raw,
            submitter_contact=contact_text,
        )
    except store.DuplicatePoster as exc:
        raise HTTPException(status_code=409, detail=already_there(None)) from exc

    missing = [f for f in store.missing_to_publish(event) if f not in ("lat", "lng")]
    message = "Thanks! Your event will appear on the map once it's reviewed."
    if missing:
        message += f" We couldn't read the {describe_missing(missing)} from the poster, so we'll fill that in during review."
    return {"id": created["id"], "status": created["status"], "missing": missing, "message": message}


@app.get("/api/venues")
def list_venues():
    """Verified Chennai venues, for autocomplete."""
    return store.list_venues()


@app.post("/api/reports", status_code=201)
def report_event(request: Request, event_id: int = Form(...), reason: str = Form(...)):
    """Flag an event as spam or inaccurate."""
    enforce(request, "report", *REPORTS_PER_VISITOR, SLOW_DOWN)
    if not store.get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    ip = client_ip(request)
    salt = os.environ.get("REPORT_IP_SALT", "jarvis")
    ip_hash = hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest() if ip else ""
    report_id = store.insert_report(event_id, clean_text(reason, "Reason", 1000, required=True), ip_hash)
    return {"status": "ok", "report_id": report_id, "message": "Report received"}


# --------------------------------------------------------------------------- #
# Admin review desk (Authorization: Bearer <ADMIN_TOKEN>)
# --------------------------------------------------------------------------- #
MIN_ADMIN_TOKEN = 16


def require_admin(authorization: Optional[str] = Header(None)) -> None:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if len(expected) < MIN_ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail=f"Admin access isn't set up. Set ADMIN_TOKEN ({MIN_ADMIN_TOKEN}+ characters) on the server.",
        )
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Wrong admin password.")


def with_location_note(event: Dict[str, Any]) -> Dict[str, Any]:
    """How sure the pin is: 'venue' (exact), 'area', 'city' (centre of Chennai), 'manual' or None."""
    if event.get("lat") is None or event.get("lng") is None:
        event["location_precision"] = None
        return event
    if not event.get("venue") and not event.get("area"):
        event["location_precision"] = "manual"
        return event
    geo = resolve_venue_coordinates(event.get("venue") or "", event.get("area") or "")
    same_pin = abs(geo["lat"] - event["lat"]) < 1e-6 and abs(geo["lng"] - event["lng"]) < 1e-6
    event["location_precision"] = geo["precision"] if same_pin else "manual"
    return event


class EventEdit(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    venue: Optional[str] = None
    area: Optional[str] = None
    date: Optional[str] = None
    end_date: Optional[str] = None
    price: Optional[int] = None
    is_free: Optional[bool] = None
    description: Optional[str] = None
    booking_link: Optional[str] = None
    contact_phone: Optional[str] = None
    instagram: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_featured: Optional[bool] = None


class StatusChange(BaseModel):
    status: str


def admin_event_or_404(event_id: int) -> Dict[str, Any]:
    event = store.get_admin_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/api/admin/session", dependencies=[Depends(require_admin)])
def admin_session():
    """Lets the review page check a password before showing anything."""
    return {"ok": True}


@app.get("/api/admin/events", dependencies=[Depends(require_admin)])
def admin_list_events(status: str = Query("review")):
    if status not in store.STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status.")
    return [with_location_note(e) for e in store.list_admin_events(status)]


@app.patch("/api/admin/events/{event_id}", dependencies=[Depends(require_admin)])
def admin_edit_event(event_id: int, edit: EventEdit):
    current = admin_event_or_404(event_id)
    given = edit.model_dump(exclude_unset=True)
    fields: Dict[str, Any] = {}

    if "title" in given:
        fields["title"] = clean_text(given["title"], "Title", 200) or None
    if "category" in given:
        fields["category"] = check_category(given["category"])
    if "venue" in given:
        fields["venue"] = clean_text(given["venue"], "Venue", 200) or None
    if "area" in given:
        fields["area"] = clean_text(given["area"], "Area", 100) or None
    if "date" in given:
        fields["date"] = parse_datetime(given["date"], "Date")
    if "end_date" in given:
        fields["end_date"] = parse_datetime(given["end_date"], "End date")
    if "description" in given:
        fields["description"] = clean_text(given["description"], "Description", 2000)
    if "booking_link" in given:
        fields["booking_link"] = check_link(given["booking_link"])
    if "contact_phone" in given:
        fields["contact_phone"] = check_phone(given["contact_phone"])
    if "instagram" in given:
        fields["instagram"] = check_instagram(given["instagram"])
    if "is_featured" in given:
        fields["is_featured"] = bool(given["is_featured"])
    if "price" in given or "is_free" in given:
        price = given.get("price", current.get("price")) or 0
        if price < 0:
            raise HTTPException(status_code=422, detail="Price can't be negative.")
        free = given.get("is_free", current.get("is_free"))
        fields["price"], fields["is_free"] = (0, True) if free or price == 0 else (price, False)

    if "lat" in given or "lng" in given:
        lat, lng = given.get("lat"), given.get("lng")
        if lat is None or lng is None:
            fields["lat"] = fields["lng"] = None
        elif not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
            raise HTTPException(status_code=422, detail="That pin is outside Chennai.")
        else:
            fields["lat"], fields["lng"] = lat, lng
    elif "venue" in fields or "area" in fields:
        # Place changed and no pin given: re-pin from the new venue/area.
        venue = fields.get("venue", current.get("venue"))
        area = fields.get("area", current.get("area"))
        venue, area, geo = locate(venue, area)
        fields.update(venue=venue, area=area, lat=geo.get("lat"), lng=geo.get("lng"))

    if current["status"] == "published":
        merged = {**current, **fields}
        missing = store.missing_to_publish(merged)
        if missing:
            raise HTTPException(status_code=422, detail=f"A live event needs a {describe_missing(missing)}. Hide it first to clear these.")

    return with_location_note(store.update_event(event_id, fields))


@app.post("/api/admin/events/{event_id}/status", dependencies=[Depends(require_admin)])
def admin_set_status(event_id: int, change: StatusChange):
    if change.status not in store.STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status.")
    event = admin_event_or_404(event_id)
    if change.status == "published":
        missing = store.missing_to_publish(event)
        if missing:
            raise HTTPException(status_code=422, detail=f"Fill in the {describe_missing(missing)} before publishing.")
    store.set_status(event_id, change.status)
    return with_location_note(admin_event_or_404(event_id))


@app.delete("/api/admin/events/{event_id}", dependencies=[Depends(require_admin)])
def admin_delete_event(event_id: int):
    if not store.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"ok": True}
