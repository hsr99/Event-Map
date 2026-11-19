"""
backend/main.py - FastAPI server for the Chennai Event Map.

Run from the repo root:
    uvicorn backend.main:app --reload --port 8000

Visitors read published events straight from Supabase; this API handles the
things that need secrets or validation: poster extraction, submissions (which
land in the review queue), and reports.
"""
import hashlib
import os
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend import store
from backend.extractor import extract_poster_details
from backend.geocoder import resolve_venue_coordinates
from backend.posters import MAX_POSTER_BYTES, InvalidPoster, inspect_poster

app = FastAPI(
    title="Jarvis Chennai Event Map API",
    description="Poster extraction, event submissions and reports for the Chennai Event Map.",
    version="2.0.0",
)

# Comma-separated list of sites allowed to call this API from a browser.
DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:5179,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(store.StoreNotConfigured)
async def store_not_configured(_: Request, exc: store.StoreNotConfigured):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


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


# --------------------------------------------------------------------------- #
# Routes
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
async def extract_poster(poster: UploadFile = File(...)):
    """Read a poster with the vision models and return suggested form values. Stores nothing."""
    data = await read_poster(poster)
    details = extract_poster_details(data, filename=poster.filename or "")
    details.pop("raw", None)

    geo = resolve_venue_coordinates(details.get("venue", ""), details.get("area", ""))
    details["lat"], details["lng"] = geo["lat"], geo["lng"]
    details["location_precision"] = geo["precision"]
    if geo.get("venue"):
        details["venue"] = geo["venue"]
    if geo["precision"] == "venue" or not details.get("area"):
        details["area"] = geo["area"]
    return details


@app.post("/api/submit", status_code=201)
async def submit_event(
    poster: Optional[UploadFile] = File(None),
    title: str = Form(...),
    category: str = Form(...),
    venue: str = Form(...),
    area: Optional[str] = Form(""),  # filled from the venue when blank
    date: str = Form(...),
    end_date: Optional[str] = Form(None),
    price: int = Form(0),
    is_free: bool = Form(False),
    description: Optional[str] = Form(""),
    booking_link: Optional[str] = Form(""),
    contact: Optional[str] = Form(""),
):
    """Submit an event. It's saved as 'review' and appears on the site once approved."""
    if category not in store.CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown category.")
    if price < 0:
        raise HTTPException(status_code=422, detail="Price can't be negative.")
    link = clean_text(booking_link, "Booking link", 500)
    if link and urlparse(link).scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="Booking link must start with http:// or https://")

    venue_text = clean_text(venue, "Venue", 200, required=True)
    area_text = clean_text(area, "Area", 100)
    geo = resolve_venue_coordinates(venue_text, area_text)
    free = is_free or price == 0

    event = {
        "title": clean_text(title, "Title", 200, required=True),
        "category": category,
        "venue": geo.get("venue") or venue_text,
        "area": area_text or geo["area"],
        "date": parse_datetime(date, "Date", required=True),
        "end_date": parse_datetime(end_date, "End date"),
        "price": 0 if free else price,
        "is_free": free,
        "description": clean_text(description, "Description", 2000),
        "booking_link": link,
        "lat": geo["lat"],
        "lng": geo["lng"],
        "status": "review",
    }

    poster_info = None
    if poster and poster.filename:
        data = await read_poster(poster)
        poster_info = inspect_poster(data)
        if store.find_submission_by_hash(poster_info.sha256):
            raise HTTPException(status_code=409, detail="This poster has already been submitted.")
        event["image_url"] = store.upload_poster(data, poster_info)

    try:
        created = store.create_event(
            event,
            source="web_form",
            poster=poster_info,
            submitter_contact=clean_text(contact, "Contact", 200),
        )
    except store.DuplicatePoster as exc:
        raise HTTPException(status_code=409, detail="This poster has already been submitted.") from exc

    return {
        "id": created["id"],
        "status": created["status"],
        "message": "Thanks! Your event will appear on the map once it's reviewed.",
    }


@app.get("/api/venues")
def list_venues():
    """Verified Chennai venues, for autocomplete."""
    return store.list_venues()


@app.post("/api/reports", status_code=201)
def report_event(request: Request, event_id: int = Form(...), reason: str = Form(...)):
    """Flag an event as spam or inaccurate."""
    if not store.get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    ip = request.client.host if request.client else ""
    salt = os.environ.get("REPORT_IP_SALT", "jarvis")
    ip_hash = hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest() if ip else ""
    report_id = store.insert_report(event_id, clean_text(reason, "Reason", 1000, required=True), ip_hash)
    return {"status": "ok", "report_id": report_id, "message": "Report received"}
