"""
backend/store.py - All reads and writes to Supabase (Postgres + Storage).

The backend uses the service-role key, which bypasses row-level security, so it
must never reach the browser. Visitors read published events directly from
Supabase with the public anon key instead (see frontend/src/lib/supabase.js).

Configuration (in the repo-root .env):
    SUPABASE_URL                 https://<project>.supabase.co  (falls back to VITE_SUPABASE_URL)
    SUPABASE_SERVICE_ROLE_KEY    service-role secret from Project Settings -> API
"""
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from backend import dedupe
from backend.posters import PosterInfo

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

POSTER_BUCKET = "posters"
CATEGORIES = ("concerts", "tech-events", "college-culturals", "movies", "social-gatherings")
STATUSES = ("review", "published", "hidden", "expired")

# Columns visitors may see. Private intake data lives in `submissions`.
EVENT_COLUMNS = (
    "id,title,category,area,venue,date,end_date,price,is_free,description,"
    "image_url,booking_link,lat,lng,is_featured,status,created_at"
)
WRITABLE_EVENT_FIELDS = (
    "title", "category", "area", "venue", "date", "end_date", "price", "is_free",
    "description", "image_url", "booking_link", "lat", "lng", "is_featured", "status",
)

# An event can sit in review with any of these blank, but can't be published without them.
REQUIRED_TO_PUBLISH = ("title", "category", "venue", "area", "date", "lat", "lng")
ADMIN_SELECT = (
    f"{EVENT_COLUMNS},"
    "submissions(source,submitter_contact,poster_path,poster_fingerprint,extracted_data,created_at)"
)


class StoreNotConfigured(RuntimeError):
    """Supabase URL or service-role key is missing."""


class DuplicatePoster(RuntimeError):
    """This exact poster image has already been submitted."""

    def __init__(self, event_id: Optional[int]):
        super().__init__(f"Poster already submitted (event {event_id})")
        self.event_id = event_id


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip().strip('"').strip("'")
        if value and "your-" not in value:
            return value
    return ""


@lru_cache(maxsize=1)
def client():
    url = _env("SUPABASE_URL", "VITE_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise StoreNotConfigured(
            "Supabase isn't configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env "
            "(Supabase dashboard -> Project Settings -> API)."
        )
    from supabase import create_client  # imported lazily so tests can run without it

    return create_client(url, key)


def is_configured() -> bool:
    return bool(_env("SUPABASE_URL", "VITE_SUPABASE_URL") and _env("SUPABASE_SERVICE_ROLE_KEY"))


def with_frontend_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """The frontend reads `isFree`; the database column is `is_free`."""
    row["isFree"] = bool(row.get("is_free"))
    return row


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
def _search_term(query: str) -> str:
    # PostgREST's or() filter syntax treats , ( ) as separators; drop them and
    # LIKE wildcards so user input is matched literally.
    return re.sub(r"[,()%*\\]", " ", query).strip()


def list_events(
    status: str = "published",
    category: Optional[str] = None,
    area: Optional[str] = None,
    is_free: Optional[bool] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    q = client().table("events").select(EVENT_COLUMNS).eq("status", status)
    if category and category != "all":
        q = q.eq("category", category)
    if area and area != "All":
        q = q.eq("area", area)
    if is_free is not None:
        q = q.eq("is_free", is_free)
    term = _search_term(query or "")
    if term:
        q = q.or_(",".join(f"{col}.ilike.*{term}*" for col in ("title", "venue", "area", "description")))
    rows = q.order("date").execute().data
    return [with_frontend_fields(r) for r in rows]


def get_event(event_id: int, status: Optional[str] = "published") -> Optional[Dict[str, Any]]:
    q = client().table("events").select(EVENT_COLUMNS).eq("id", event_id)
    if status:
        q = q.eq("status", status)
    rows = q.limit(1).execute().data
    return with_frontend_fields(rows[0]) if rows else None


def find_submission_by_hash(poster_hash: str) -> Optional[Dict[str, Any]]:
    """The submission with this exact poster file, plus its event's `status`."""
    rows = (
        client().table("submissions").select("id,event_id,events(status)")
        .eq("poster_hash", poster_hash).limit(1).execute().data
    )
    if not rows:
        return None
    row = rows[0]
    event = row.pop("events", None) or {}
    row["status"] = event.get("status") if isinstance(event, dict) else None
    return row


def dedupe_candidates() -> List[Dict[str, Any]]:
    """Every event with its poster fingerprint, for duplicate checks."""
    rows = (
        client().table("events")
        .select("id,title,venue,date,status,image_url,submissions(poster_fingerprint)")
        .order("id", desc=True).limit(5000).execute().data
    )
    for row in rows:
        sub = row.pop("submissions", None)
        if isinstance(sub, list):
            sub = sub[0] if sub else None
        row["poster_fingerprint"] = (sub or {}).get("poster_fingerprint")
    return rows


def find_duplicates(
    event: Dict[str, Any],
    fingerprint: Optional[str],
    exclude_id: Optional[int] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if candidates is None:
        candidates = dedupe_candidates()
    return dedupe.find_matches(event, fingerprint, candidates, exclude_id=exclude_id)


def create_event(
    event: Dict[str, Any],
    *,
    source: str,
    poster: Optional[PosterInfo] = None,
    extracted_data: Any = None,
    submitter_contact: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert an event plus its private submission record.

    Raises DuplicatePoster if the poster's hash is already on record.
    """
    if poster:
        existing = find_submission_by_hash(poster.sha256)
        if existing:
            raise DuplicatePoster(existing.get("event_id"))

    row = {k: event[k] for k in WRITABLE_EVENT_FIELDS if k in event}
    if row.get("category") is not None and row["category"] not in CATEGORIES:
        raise ValueError(f"Unknown category: {row.get('category')!r}")
    row.setdefault("status", "review")

    created = client().table("events").insert(row).execute().data[0]
    try:
        client().table("submissions").insert({
            "event_id": created["id"],
            "source": source,
            "submitter_contact": submitter_contact or None,
            "poster_path": poster.storage_path if poster else None,
            "poster_hash": poster.sha256 if poster else None,
            "poster_fingerprint": poster.fingerprint if poster else None,
            "extracted_data": extracted_data,
        }).execute()
    except Exception:
        # No cross-table transactions over the REST API: undo the event so a
        # failed submission record doesn't leave an orphan behind.
        client().table("events").delete().eq("id", created["id"]).execute()
        raise
    return with_frontend_fields(created)


def set_status(event_id: int, status: str) -> Optional[Dict[str, Any]]:
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status!r}")
    rows = client().table("events").update({"status": status}).eq("id", event_id).execute().data
    return with_frontend_fields(rows[0]) if rows else None


def missing_to_publish(event: Dict[str, Any]) -> List[str]:
    """Fields that must be filled in before this event can go live."""
    return [f for f in REQUIRED_TO_PUBLISH if event.get(f) in (None, "")]


def _admin_row(row: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    sub = row.pop("submissions", None)
    if isinstance(sub, list):
        sub = sub[0] if sub else None
    sub = dict(sub or {})
    fingerprint = sub.pop("poster_fingerprint", None)
    row = with_frontend_fields(row)
    row["submission"] = sub or None
    row["missing"] = missing_to_publish(row)
    row["duplicates"] = find_duplicates(row, fingerprint, exclude_id=row["id"], candidates=candidates)
    return row


def list_admin_events(status: str = "review") -> List[Dict[str, Any]]:
    """Events in any status, with private submission details, for the review page."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status!r}")
    query = client().table("events").select(ADMIN_SELECT).eq("status", status)
    # Review queue: oldest first. Everything else: by event date.
    query = query.order("created_at") if status == "review" else query.order("date", desc=True)
    rows = query.limit(500).execute().data
    candidates = dedupe_candidates()
    return [_admin_row(r, candidates) for r in rows]


def get_admin_event(event_id: int) -> Optional[Dict[str, Any]]:
    rows = client().table("events").select(ADMIN_SELECT).eq("id", event_id).limit(1).execute().data
    return _admin_row(rows[0], dedupe_candidates()) if rows else None


def update_event(event_id: int, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    row = {k: v for k, v in fields.items() if k in WRITABLE_EVENT_FIELDS and k != "status"}
    if row.get("category") is not None and row["category"] not in CATEGORIES:
        raise ValueError(f"Unknown category: {row.get('category')!r}")
    if row:
        client().table("events").update(row).eq("id", event_id).execute()
    return get_admin_event(event_id)


def delete_event(event_id: int) -> bool:
    """Delete an event, its submission record (cascade) and its poster file."""
    event = get_admin_event(event_id)
    if not event:
        return False
    client().table("events").delete().eq("id", event_id).execute()
    path = (event.get("submission") or {}).get("poster_path")
    if path:
        try:
            client().storage.from_(POSTER_BUCKET).remove([path])
        except Exception as exc:  # a leftover file is harmless; don't fail the delete
            print(f"[store] Couldn't remove poster {path}: {exc}")
    return True


def list_review_queue() -> List[Dict[str, Any]]:
    """Events waiting for approval, with their private submission details."""
    return (
        client().table("events")
        .select(f"{EVENT_COLUMNS},submissions(source,submitter_contact,poster_path,extracted_data)")
        .eq("status", "review").order("created_at").execute().data
    )


# --------------------------------------------------------------------------- #
# Posters (Storage)
# --------------------------------------------------------------------------- #
def upload_poster(data: bytes, poster: PosterInfo) -> str:
    """Upload to the public posters bucket and return its public URL.

    Paths are content-addressed (sha256), so re-uploading the same image is a no-op overwrite.
    """
    bucket = client().storage.from_(POSTER_BUCKET)
    bucket.upload(
        poster.storage_path,
        data,
        {"content-type": poster.content_type, "upsert": "true", "cache-control": "31536000"},
    )
    return bucket.get_public_url(poster.storage_path).rstrip("?")


# --------------------------------------------------------------------------- #
# Venues & reports
# --------------------------------------------------------------------------- #
def list_venues() -> List[Dict[str, Any]]:
    return client().table("venues").select("*").order("area").order("name").execute().data


def upsert_venues(venues: List[Dict[str, Any]]) -> None:
    client().table("venues").upsert(venues, on_conflict="name").execute()


def insert_report(event_id: int, reason: str, reporter_ip_hash: str = "") -> int:
    rows = client().table("reports").insert({
        "event_id": event_id,
        "reason": reason,
        "reporter_ip_hash": reporter_ip_hash or None,
    }).execute().data
    return rows[0]["id"]
