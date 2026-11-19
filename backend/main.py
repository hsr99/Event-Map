"""
backend/main.py - FastAPI Application Server for Chennai Event Map.
Provides endpoints for event discovery, poster extraction, event submission, and venues.
"""
import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import (
    init_db,
    get_events,
    get_event_by_id,
    insert_event,
    get_venues,
    insert_report,
)
from backend.extractor import extract_poster_details
from backend.geocoder import resolve_venue_coordinates

ROOT_DIR = Path(__file__).resolve().parent.parent
POSTERS_DIR = ROOT_DIR / "frontend" / "public" / "posters"
POSTERS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Jarvis Chennai Event Map API",
    description="Backend API powering Chennai event discovery, poster extraction, and submissions.",
    version="1.0.0",
)

# Enable CORS for local dev server and frontend hosting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded posters statically
app.mount("/posters", StaticFiles(directory=str(POSTERS_DIR)), name="posters")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Jarvis Chennai Event Map API"}


@app.get("/api/events")
def list_events(
    category: Optional[str] = Query(None, description="Category filter (concerts, tech-events, etc.)"),
    area: Optional[str] = Query(None, description="Chennai area filter"),
    is_free: Optional[bool] = Query(None, description="Filter for free events"),
    q: Optional[str] = Query(None, description="Search keyword in title, venue, area"),
):
    """Retrieve filtered list of published events."""
    return get_events(category=category, area=area, is_free=is_free, query=q)


@app.get("/api/events/{event_id}")
def get_single_event(event_id: int):
    """Retrieve details for a single event."""
    event = get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/api/extract")
async def extract_poster(poster: UploadFile = File(...)):
    """Upload a poster and extract event metadata using the VLM pipeline."""
    contents = await poster.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file uploaded")

    details = extract_poster_details(contents, filename=poster.filename or "")
    # Geocode venue
    geo = resolve_venue_coordinates(details.get("venue", ""), details.get("area", ""))
    details["lat"] = geo["lat"]
    details["lng"] = geo["lng"]
    if not details.get("area"):
        details["area"] = geo["area"]

    return details


@app.post("/api/submit")
async def submit_event(
    poster: UploadFile = File(None),
    title: str = Form(...),
    category: str = Form(...),
    venue: str = Form(...),
    area: str = Form(...),
    date: str = Form(...),
    end_date: Optional[str] = Form(None),
    price: int = Form(0),
    is_free: bool = Form(False),
    description: Optional[str] = Form(""),
    booking_link: Optional[str] = Form(""),
    image_url: Optional[str] = Form(None),
):
    """Submits a new event, saves the poster, resolves GPS coordinates, and records to DB."""
    final_image_url = image_url or ""

    # If an image file was uploaded, save it to public/posters/
    if poster and poster.filename:
        safe_filename = f"{int(datetime.now().timestamp())}_{poster.filename.replace(' ', '_')}"
        dest = POSTERS_DIR / safe_filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(poster.file, f)
        final_image_url = f"/posters/{safe_filename}"

    # Resolve coordinates
    geo = resolve_venue_coordinates(venue, area)

    event_payload = {
        "title": title.strip(),
        "category": category.strip(),
        "venue": venue.strip(),
        "area": area.strip() or geo["area"],
        "date": date.strip(),
        "end_date": end_date.strip() if end_date else None,
        "price": price,
        "isFree": is_free or price == 0,
        "description": description.strip() if description else "",
        "booking_link": booking_link.strip() if booking_link else "",
        "image_url": final_image_url or "/posters/openmic.jpeg",
        "lat": geo["lat"],
        "lng": geo["lng"],
        "is_featured": 1 if price > 0 else 0,
        "status": "published",
    }

    event_id = insert_event(event_payload)
    event_payload["id"] = event_id
    return event_payload


@app.get("/api/venues")
def list_venues():
    """Retrieve list of verified Chennai venues for autocomplete."""
    return get_venues()


@app.post("/api/reports")
def report_event(
    event_id: int = Form(...),
    reason: str = Form(...),
):
    """Submit an inaccuracy or spam report for an event."""
    report_id = insert_report(event_id, reason)
    return {"status": "ok", "report_id": report_id, "message": "Report received"}
