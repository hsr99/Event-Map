#!/usr/bin/env python3
"""
tools/watch_instagram.py - Check Chennai organisers' Instagram accounts for new
event posters and send them to the review desk (/admin). Nothing goes on the
map until you approve it.

Runs on your own computer (Instagram blocks cloud servers), logged in as a
spare Instagram account. Keep it gentle: a few minutes, once or twice a day.

One-time setup:
    venv\\Scripts\\instaloader --login YOUR_SPARE_ACCOUNT   (asks for the password, saves a session file)
    then list the accounts to watch in tools/instagram_accounts.txt

Each run:
    python tools/watch_instagram.py --user YOUR_SPARE_ACCOUNT
    python tools/watch_instagram.py --user YOUR_SPARE_ACCOUNT --dry-run   # read posters, save nothing

INSTAGRAM_USER in .env can stand in for --user.
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import instaloader  # noqa: E402
from instaloader import exceptions as ig_errors  # noqa: E402

from backend import dedupe, store  # noqa: E402
from backend.contacts import normalize_instagram  # noqa: E402
from backend.extractor import extract_poster_details  # noqa: E402
from backend.posters import InvalidPoster, inspect_poster  # noqa: E402
from tools.ingest_posters import build_event  # noqa: E402

ACCOUNTS_FILE = ROOT_DIR / "tools" / "instagram_accounts.txt"
SEEN_FILE = ROOT_DIR / "data" / "instagram_seen.json"

LOOKBACK_DAYS = 30       # ignore posts older than this
POSTS_SCANNED = 8        # newest posts looked at per account (one page, one request)
MAX_POSTERS_PER_RUN = 25  # posters read per run, across all accounts (each is one model call)
SEEN_KEPT = 60           # post ids remembered per account

# Instagram's own signs that we're going too fast or the login is no longer good.
# On any of these, stop for the day rather than push on.
PUSHBACK = (
    ig_errors.TooManyRequestsException,
    ig_errors.LoginRequiredException,
    ig_errors.QueryReturnedBadRequestException,
    ig_errors.ConnectionException,
)


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


def recent_posts(loader, handle: str, seen_ids: set, cutoff: datetime) -> list:
    """New, recent picture posts from one account, newest first."""
    profile = instaloader.Profile.from_username(loader.context, handle)
    found = []
    for i, post in enumerate(profile.get_posts()):
        if i >= POSTS_SCANNED:
            break
        old = post.date_utc.replace(tzinfo=timezone.utc) < cutoff
        if old and not post.is_pinned:
            break  # posts come newest first (pinned ones aside), so the rest are older still
        if old or post.shortcode in seen_ids or post.is_video:
            continue
        found.append(post)
    return found


def is_over(event: dict, now: datetime) -> bool:
    end = datetime.fromisoformat(event.get("end_date") or event["date"])
    return end + timedelta(hours=6) < now


def handle_post(loader, handle: str, post, dry_run: bool) -> str:
    """Read one post's poster. Returns 'added', 'skipped' or 'retry' (try again next run)."""
    link = f"https://www.instagram.com/p/{post.shortcode}/"
    # For a multi-picture post this is the first picture, which is where the poster usually is.
    data = loader.context.get_raw(post.url).content
    try:
        info = inspect_poster(data)
    except InvalidPoster as exc:
        print(f"    {link}: skipped ({exc})")
        return "skipped"
    if store.find_submission_by_hash(info.sha256):
        print(f"    {link}: already on record")
        return "skipped"

    details = extract_poster_details(data, filename=f"ig-{handle}-{post.shortcode}.jpg")
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
                       extracted_data={**raw, "instagram_post": link})
    return "added"


def main() -> int:
    ap = argparse.ArgumentParser(description="Send new event posters from Instagram to the review desk.")
    ap.add_argument("--user", default=os.environ.get("INSTAGRAM_USER", ""),
                    help="the spare Instagram account you logged in with")
    ap.add_argument("--dry-run", action="store_true", help="read posters and print, save nothing")
    ap.add_argument("--limit", type=int, default=MAX_POSTERS_PER_RUN, help="most posters to read this run")
    args = ap.parse_args()

    accounts = load_accounts()
    if not accounts:
        print(f"[Instagram] No accounts to watch. Add handles to {ACCOUNTS_FILE.relative_to(ROOT_DIR)}.")
        return 1
    if not args.user:
        print("[Instagram] Say which account to use: --user YOUR_SPARE_ACCOUNT (or INSTAGRAM_USER in .env).")
        return 1

    loader = instaloader.Instaloader(
        quiet=True, download_pictures=False, download_videos=False, download_video_thumbnails=False,
        download_comments=False, save_metadata=False, max_connection_attempts=1,
    )
    try:
        loader.load_session_from_file(args.user)
    except FileNotFoundError:
        print(f"[Instagram] Not logged in yet. Run once:  venv\\Scripts\\instaloader --login {args.user}")
        return 1
    if loader.test_login() != args.user:
        print(f"[Instagram] The saved login for {args.user} has expired. Log in again:  "
              f"venv\\Scripts\\instaloader --login {args.user}")
        return 1

    seen = load_seen()
    random.shuffle(accounts)
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    budget, added, read = args.limit, 0, 0
    print(f"[Instagram] Checking {len(accounts)} account(s) as {args.user}"
          f"{' (dry run)' if args.dry_run else ''}")

    try:
        for i, handle in enumerate(accounts):
            if budget <= 0:
                print("[Instagram] Reached this run's limit; the rest wait for next time.")
                break
            if i:
                pause(20, 60)
            history = seen.get(handle, [])
            try:
                posts = recent_posts(loader, handle, set(history), cutoff)
            except (ig_errors.ProfileNotExistsException, ig_errors.PrivateProfileNotFollowedException) as exc:
                print(f"  @{handle}: can't see this account ({exc.__class__.__name__}), skipping")
                continue
            print(f"  @{handle}: {len(posts)} new post(s)")
            for post in posts[:budget]:
                pause(4, 12)
                result = handle_post(loader, handle, post, args.dry_run)
                read += 1
                budget -= 1
                added += result == "added"
                if result != "retry":
                    history.append(post.shortcode)
            seen[handle] = history[-SEEN_KEPT:]
            save_seen(seen)
    except PUSHBACK as exc:
        save_seen(seen)
        print(f"\n[Instagram] Instagram pushed back ({exc.__class__.__name__}: {str(exc)[:120]}).")
        print("  Stopped for today. Don't re-run until tomorrow; if it keeps happening, open the")
        print("  spare account in the Instagram app once and clear any security check it shows.")
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
