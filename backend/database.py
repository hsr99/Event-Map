"""
backend/database.py - SQLite Database management for Chennai Event Map.
Handles schema creation, event queries, insertions, and frontend sync.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "events.db"

FRONTEND_EVENTS_JSON = ROOT_DIR / "frontend" / "public" / "events.json"
FRONTEND_EVENTS_JS = ROOT_DIR / "frontend" / "src" / "data" / "events.js"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes SQLite schema for events, venues, posters, and reports."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                area TEXT NOT NULL,
                venue TEXT NOT NULL,
                date TEXT NOT NULL,
                end_date TEXT,
                price INTEGER DEFAULT 0,
                is_free INTEGER DEFAULT 1,
                description TEXT,
                image_url TEXT,
                booking_link TEXT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                is_featured INTEGER DEFAULT 0,
                status TEXT DEFAULT 'published',
                created_at TEXT NOT NULL
            )
        """)

        # Venues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS venues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                area TEXT NOT NULL,
                address TEXT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                category TEXT
            )
        """)

        # Posters audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                filename TEXT NOT NULL,
                file_hash TEXT,
                raw_vlm_output TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)

        # Spam/Inaccuracy reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                ip_hash TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id)
            )
        """)

        conn.commit()


def get_events(
    category: Optional[str] = None,
    area: Optional[str] = None,
    is_free: Optional[bool] = None,
    query: Optional[str] = None,
    status: str = "published"
) -> List[Dict[str, Any]]:
    """Query events with optional filtering."""
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM events WHERE status = ?"
        params: list = [status]

        if category and category != "all":
            sql += " AND category = ?"
            params.append(category)

        if area and area != "All":
            sql += " AND area = ?"
            params.append(area)

        if is_free is not None:
            sql += " AND is_free = ?"
            params.append(1 if is_free else 0)

        if query:
            sql += " AND (title LIKE ? OR venue LIKE ? OR area LIKE ? OR description LIKE ?)"
            term = f"%{query.strip()}%"
            params.extend([term, term, term, term])

        sql += " ORDER BY date ASC"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict_from_event_row(r) for r in rows]


def get_event_by_id(event_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        return dict_from_event_row(row) if row else None


def insert_event(event_data: Dict[str, Any]) -> int:
    """Inserts a new event into SQLite and syncs frontend JSON & JS datasets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO events (
                title, category, area, venue, date, end_date, price,
                is_free, description, image_url, booking_link, lat, lng,
                is_featured, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_data["title"],
            event_data["category"],
            event_data["area"],
            event_data["venue"],
            event_data["date"],
            event_data.get("end_date"),
            int(event_data.get("price", 0)),
            1 if event_data.get("isFree") or event_data.get("is_free") else 0,
            event_data.get("description", ""),
            event_data.get("image_url", ""),
            event_data.get("booking_link", ""),
            float(event_data["lat"]),
            float(event_data["lng"]),
            1 if event_data.get("is_featured") else 0,
            event_data.get("status", "published"),
            now
        ))
        event_id = cursor.lastrowid
        conn.commit()

    # Automatically keep the frontend in sync
    export_to_frontend()
    return event_id


def get_event_by_image_url(image_url: str) -> Optional[Dict[str, Any]]:
    """Find an event (any status) that already uses this poster image."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE image_url = ? LIMIT 1", (image_url,))
        row = cursor.fetchone()
        return dict_from_event_row(row) if row else None


def get_poster_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posters WHERE file_hash = ? LIMIT 1", (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None


def insert_poster_record(event_id: Optional[int], filename: str, file_hash: str, raw_vlm_output: Any) -> int:
    """Record which poster produced which event, with the raw model output for auditing."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO posters (event_id, filename, file_hash, raw_vlm_output, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, filename, file_hash, json.dumps(raw_vlm_output, ensure_ascii=False), datetime.now().isoformat()))
        conn.commit()
        return cursor.lastrowid


def get_venues() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM venues ORDER BY area, name")
        return [dict(r) for r in cursor.fetchall()]


def insert_venue(venue: Dict[str, Any]) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO venues (name, area, address, lat, lng, category)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            venue["name"],
            venue["area"],
            venue.get("address", ""),
            float(venue["lat"]),
            float(venue["lng"]),
            venue.get("category", "general")
        ))
        conn.commit()
        return cursor.lastrowid


def insert_report(event_id: int, reason: str, ip_hash: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO reports (event_id, reason, ip_hash, created_at)
            VALUES (?, ?, ?, ?)
        """, (event_id, reason, ip_hash, now))
        conn.commit()
        return cursor.lastrowid


def dict_from_event_row(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["isFree"] = bool(d["is_free"])
    d["is_featured"] = bool(d["is_featured"])
    return d


def export_to_frontend():
    """Compiles all published events directly into frontend/public/events.json and frontend/src/data/events.js."""
    events = get_events(status="published")

    # 1. Write frontend/public/events.json
    if FRONTEND_EVENTS_JSON.parent.exists():
        FRONTEND_EVENTS_JSON.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Write frontend/src/data/events.js
    if FRONTEND_EVENTS_JS.parent.exists():
        js_code = "// Auto-generated by Chennai Event Map Backend Engine\n\n"
        js_code += f"export const events = {json.dumps(events, indent=2, ensure_ascii=False)};\n"
        FRONTEND_EVENTS_JS.write_text(js_code, encoding="utf-8")
