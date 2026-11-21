#!/usr/bin/env python3
"""
tools/watch_instagram.py - Check Chennai organisers' Instagram accounts for new
event posters and send them to the review desk (/admin). Nothing goes on the
map until you approve it.

Reads Instagram with gallery-dl, logged in as your spare account through
Firefox's cookies. Runs on your own computer (Instagram blocks cloud servers).
Keep it gentle: a few minutes, once or twice a day.

Setup:
    1. Log in to the spare account on instagram.com in Firefox.
    2. List the accounts to watch in tools/instagram_accounts.txt.

Each run:
    python tools/watch_instagram.py
    python tools/watch_instagram.py --dry-run   # read posters, save nothing

The first run copies the login out of Firefox (close Firefox first) into
data/instagram_cookies.txt; later runs use that copy, so Firefox can stay open.
If Instagram logs the spare account out, delete that file and run again with
Firefox closed.
"""
import argparse
import json
import random
import subprocess
import sys
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import dedupe, store  # noqa: E402
from backend.contacts import normalize_instagram  # noqa: E402
from backend.extractor import extract_poster_details  # noqa: E402
from backend.posters import InvalidPoster, inspect_poster  # noqa: E402
from tools.ingest_posters import build_event  # noqa: E402

ACCOUNTS_FILE = ROOT_DIR / "tools" / "instagram_accounts.txt"
SEEN_FILE = ROOT_DIR / "data" / "instagram_seen.json"
COOKIES_FILE = ROOT_DIR / "data" / "instagram_cookies.txt"  # the spare account's login: never commit
GALLERY_DL = Path(sys.executable).with_name("gallery-dl.exe" if sys.platform == "win32" else "gallery-dl")

LOOKBACK_DAYS = 30        # ignore posts older than this
POSTS_SCANNED = 8         # newest posts looked at per account
MAX_POSTERS_PER_RUN = 25  # posters read per run, across all accounts (each is one model call)
SEEN_KEPT = 60            # post ids remembered per account

# gallery-dl error text that means Instagram is pushing back or the login is no
# longer good. On any of these, stop for the day rather than push on.
PUSHBACK_SIGNS = ("429", "too many requests", "login", "challenge", "checkpoint", "401", "403",
                  "rate limit", "please wait")


class InstagramPushback(Exception):
    pass


def pause(low: float, high: float) -> None:
    """Wait a random while, like someone scrolling, reading, then moving on."""
    time.sleep(random.uniform(low, high))


def load_accounts() -> list[str]:
    if not ACCOUNTS_FILE.exists():
        return []
    handles = []
    for line in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        handle = normalize_instagram(line.split("#", 1)[0])
        if handle and handle not in handles:
            handles.append(handle)
    return handles


def load_seen() -> dict:
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_seen(seen: dict) -> None:
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=1, sort_keys=True), encoding="utf-8")


def save_login(handle: str) -> bool:
    """Copy the spare account's login out of Firefox into COOKIES_FILE, once.

    (gallery-dl only exports cookies from a normal or simulated run, not from
    the JSON listing used below, so this does a one-post simulated run.)
    """
    COOKIES_FILE.parent.mkdir(exist_ok=True)
    subprocess.run([str(GALLERY_DL), "--cookies-from-browser", "firefox", "--cookies-export", str(COOKIES_FILE),
                    "--post-range", "1", "-s", f"https://www.instagram.com/{handle}/posts/"],
                   capture_output=True, text=True, encoding="utf-8", timeout=120)
    return COOKIES_FILE.exists() and "sessionid" in COOKIES_FILE.read_text(encoding="utf-8")


def fetch_posts(handle: str) -> list[dict]:
    """The account's newest posts as {shortcode, date, pinned, image_url, caption}, newest first."""
    cmd = [str(GALLERY_DL), "--cookies", str(COOKIES_FILE), "--post-range", f"1-{POSTS_SCANNED}",
           "--sleep-request", "3-8", "-j", f"https://www.instagram.com/{handle}/posts/"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
    errors = "\n".join(line for line in result.stderr.splitlines() if "[error]" in line or "[warning]" in line)
    if errors and any(sign in errors.lower() for sign in PUSHBACK_SIGNS):
        raise InstagramPushback(errors.strip()[:300])
    try:
        messages = json.loads(result.stdout or "[]")
    except ValueError:
        raise RuntimeError((errors or result.stderr or "no output").strip()[:300])
    if not isinstance(messages, list):
        return []

    posts: "OrderedDict[str, dict]" = OrderedDict()
    for message in messages:
        if not (isinstance(message, list) and len(message) == 3 and message[0] == 3):
            continue  # only "file URL + metadata" messages carry posts
        url, meta = message[1], message[2]
        code = meta.get("post_shortcode") or meta.get("shortcode")
        if not code or code in posts:
            continue  # first file of each post only: in a carousel that's where the poster usually is
        posts[code] = {
            "shortcode": code,
            "date": datetime.strptime(meta["post_date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
            "pinned": bool(meta.get("pinned")),
            "image_url": meta.get("display_url") or url if meta.get("type") == "image" else None,
            "caption": meta.get("description") or "",
        }
    return list(posts.values())


def new_posts(posts: list[dict], seen_ids: set, cutoff: datetime) -> list[dict]:
    """Recent picture posts we haven't looked at yet."""
    found = []
    for post in posts:
        old = post["date"] < cutoff
        if old and not post["pinned"]:
            break  # posts come newest first (pinned ones aside), so the rest are older still
        if old or post["shortcode"] in seen_ids or not post["image_url"]:
            continue  # videos and reels have no poster image
        found.append(post)
    return found


def is_over(event: dict, now: datetime) -> bool:
    end = datetime.fromisoformat(event.get("end_date") or event["date"])
    return end + timedelta(hours=6) < now


def handle_post(handle: str, post: dict, dry_run: bool) -> str:
    """Read one post's poster. Returns 'added', 'skipped' or 'retry' (try again next run)."""
    link = f"https://www.instagram.com/p/{post['shortcode']}/"
    resp = requests.get(post["image_url"], timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    data = resp.content
    try:
        info = inspect_poster(data)
    except InvalidPoster as exc:
        print(f"    {link}: skipped ({exc})")
        return "skipped"
    if store.find_submission_by_hash(info.sha256):
        print(f"    {link}: already on record")
        return "skipped"

    details = extract_poster_details(data, filename=f"ig-{handle}-{post['shortcode']}.jpg")
    if details["backend"] == "heuristic":
        print(f"    {link}: couldn't read it (models unavailable), will retry next run")
        return "retry"
    if "date" in details["needs_review"]:
        print(f"    {link}: no event date on it, probably not an event poster")
        return "skipped"
    if is_over(details, datetime.now(timezone.utc)):
        print(f"    {link}: '{details['title'][:40]}' is already over")
        return "skipped"

    event, review = build_event(details, publish_all=False)
    event["status"] = "review"  # always a person's call before it's public
    event["instagram"] = event["instagram"] or handle

    matches = store.find_duplicates(event, info.fingerprint)
    block = dedupe.blocking_match(matches)
    if block:
        print(f"    {link}: already on the map as #{block['id']} ('{(block['title'] or '')[:40]}')")
        return "skipped"

    print(f"    {link}: '{event['title'][:40]}' | {event['category']} | {event['date'][:10]} | {event['area'] or '?'}"
          f"{' (possible duplicate)' if matches else ''}")
    if dry_run:
        return "retry"  # nothing saved, so look at it again on a real run

    event["image_url"] = store.upload_poster(data, info)
    raw = details.get("raw") if isinstance(details.get("raw"), dict) else {}
    store.create_event(event, source="instagram_share", poster=info,
                       extracted_data={**raw, "instagram_post": link, "instagram_caption": post["caption"][:2000]})
    return "added"


def main() -> int:
    ap = argparse.ArgumentParser(description="Send new event posters from Instagram to the review desk.")
    ap.add_argument("--dry-run", action="store_true", help="read posters and print, save nothing")
    ap.add_argument("--limit", type=int, default=MAX_POSTERS_PER_RUN, help="most posters to read this run")
    args = ap.parse_args()

    accounts = load_accounts()
    if not accounts:
        print(f"[Instagram] No accounts to watch. Add handles to {ACCOUNTS_FILE.relative_to(ROOT_DIR)}.")
        return 1
    if not GALLERY_DL.exists():
        print("[Instagram] gallery-dl isn't installed:  venv\\Scripts\\python -m pip install gallery-dl")
        return 1

    if not COOKIES_FILE.exists():
        print("[Instagram] Copying the spare account's login from Firefox (close Firefox if this fails)...")
        if not save_login(accounts[0]):
            COOKIES_FILE.unlink(missing_ok=True)
            print("[Instagram] No Instagram login found in Firefox. Log in to the spare account on")
            print("  instagram.com in Firefox, close Firefox completely, and run this again.")
            return 1
        pause(5, 15)

    seen = load_seen()
    random.shuffle(accounts)
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    budget, added, read = args.limit, 0, 0
    print(f"[Instagram] Checking {len(accounts)} account(s){' (dry run)' if args.dry_run else ''}")

    try:
        for i, handle in enumerate(accounts):
            if budget <= 0:
                print("[Instagram] Reached this run's limit; the rest wait for next time.")
                break
            if i:
                pause(20, 60)
            history = seen.get(handle, [])
            try:
                posts = new_posts(fetch_posts(handle), set(history), cutoff)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                print(f"  @{handle}: couldn't read this account ({str(exc)[:150]}), skipping")
                continue
            print(f"  @{handle}: {len(posts)} new picture post(s)")
            for post in posts[:budget]:
                pause(4, 12)
                result = handle_post(handle, post, args.dry_run)
                read += 1
                budget -= 1
                added += result == "added"
                if result != "retry":
                    history.append(post["shortcode"])
            seen[handle] = history[-SEEN_KEPT:]
            save_seen(seen)
    except InstagramPushback as exc:
        save_seen(seen)
        print(f"\n[Instagram] Instagram pushed back:\n  {exc}")
        print("  Stopped for today. Don't re-run until tomorrow. If it keeps happening, open the spare")
        print("  account in Firefox, clear any security check, then delete data/instagram_cookies.txt,")
        print("  close Firefox and run again.")
        return 2

    print(f"\n[Instagram] Read {read} poster(s), sent {added} to the review desk"
          f"{' (dry run: nothing saved)' if args.dry_run else ''}.")
    if added:
        print("  Review them at /admin.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except store.StoreNotConfigured as exc:
        print(f"[Instagram] {exc}", file=sys.stderr)
        sys.exit(1)
