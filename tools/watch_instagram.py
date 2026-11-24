#!/usr/bin/env python3
"""
tools/watch_instagram.py - Check Chennai organisers' Instagram accounts for new
event posts and turn them into events.

For each account, only the newest few posts are looked at. Each new post goes:
  1. caption check (cheap text model): clearly not an upcoming Chennai event? skip
  2. poster read (vision model), with the caption as extra context
  3. rules: has a future date, venue inside Chennai, not a duplicate
  4. everything goes to the review desk (/admin). With --auto-publish, posts that
     pass every check with confidence go straight onto the map instead.

Reads Instagram with gallery-dl, logged in as your spare account through
Firefox's cookies. Runs on your own computer (Instagram blocks cloud servers).
Keep it gentle: a few minutes, once or twice a day.

Setup:
    1. Log in to the spare account on instagram.com in Firefox.
    2. List the accounts to watch in tools/instagram_accounts.txt.

Each run:
    python tools/watch_instagram.py
    python tools/watch_instagram.py --dry-run   # read posters, save nothing
    python tools/watch_instagram.py --auto-publish   # confident events skip review

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
from backend.caption_check import check_caption, rules_out  # noqa: E402
from backend.contacts import normalize_instagram  # noqa: E402
from backend.extractor import extract_poster_details  # noqa: E402
from backend.posters import InvalidPoster, inspect_poster  # noqa: E402
from tools.ingest_posters import build_event  # noqa: E402

ACCOUNTS_FILE = ROOT_DIR / "tools" / "instagram_accounts.txt"
SEEN_FILE = ROOT_DIR / "data" / "instagram_seen.json"
COOKIES_FILE = ROOT_DIR / "data" / "instagram_cookies.txt"  # the spare account's login: never commit
GALLERY_DL = Path(sys.executable).with_name("gallery-dl.exe" if sys.platform == "win32" else "gallery-dl")

LOOKBACK_DAYS = 30        # ignore posts older than this
POSTS_SCANNED = 6         # posts fetched per account (pinned ones come first, so a few extra)
LATEST_POSTS = 3          # of those, only the newest few are considered
MAX_POSTERS_PER_RUN = 25  # posts checked per run, across all accounts

# Rough box around Chennai and its suburbs (Mahabalipuram to Ponneri, Sriperumbudur to the coast).
CHENNAI_BOX = {"lat": (12.55, 13.45), "lng": (79.80, 80.40)}
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
            # For reels and videos this is the cover image, which is often the poster.
            "image_url": meta.get("display_url") or (url if meta.get("type") == "image" else None),
            "format": meta.get("type") or "",
            "caption": meta.get("description") or "",
        }
    return list(posts.values())


def new_posts(posts: list[dict], seen_ids: set, cutoff: datetime) -> list[dict]:
    """Of the account's newest few posts, the recent ones we haven't looked at yet."""
    latest = sorted(posts, key=lambda p: p["date"], reverse=True)[:LATEST_POSTS]
    return [p for p in latest if p["date"] >= cutoff and p["shortcode"] not in seen_ids and p["image_url"]]


def in_chennai(event: dict) -> bool:
    lat, lng = event.get("lat"), event.get("lng")
    if lat is None or lng is None:
        return True  # unknown: the review desk will catch it
    return (CHENNAI_BOX["lat"][0] <= lat <= CHENNAI_BOX["lat"][1]
            and CHENNAI_BOX["lng"][0] <= lng <= CHENNAI_BOX["lng"][1])


def is_over(event: dict, now: datetime) -> bool:
    end = datetime.fromisoformat(event.get("end_date") or event["date"])
    return end + timedelta(hours=6) < now


def handle_post(handle: str, post: dict, dry_run: bool, auto_publish: bool) -> str:
    """Run one post through the checks. Returns 'added', 'published', 'skipped' or 'retry' (try again next run)."""
    link = f"https://www.instagram.com/p/{post['shortcode']}/"

    def say(msg: str) -> None:
        print(f"    {link} [{post['format'] or '?'}] {msg}")

    # 1. Caption check: cheap, text only
    caption_result = check_caption(post["caption"], post["date"], handle)
    if rules_out(caption_result):
        say(f"skip, caption: not an upcoming Chennai event ({caption_result['reason']})")
        return "skipped"

    # 2. Poster read, with the caption as extra context
    resp = requests.get(post["image_url"], timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    data = resp.content
    try:
        info = inspect_poster(data)
    except InvalidPoster as exc:
        say(f"skip, image unusable ({exc})")
        return "skipped"
    if store.find_submission_by_hash(info.sha256):
        say("skip, this exact poster is already on record")
        return "skipped"
    details = extract_poster_details(data, filename=f"ig-{handle}-{post['shortcode']}.jpg", context=post["caption"])
    if details["backend"] == "heuristic":
        say("retry next run: couldn't read it (models unavailable)")
        return "retry"

    # 3. Rules
    if "date" in details["needs_review"]:
        say(f"skip, no event date found (caption check said: {caption_result['announces_event']})")
        return "skipped"
    if is_over(details, datetime.now(timezone.utc)):
        say(f"skip, '{details['title'][:40]}' is already over ({details['date'][:10]})")
        return "skipped"
    event, review = build_event(details, publish_all=False)
    event["instagram"] = event["instagram"] or handle
    if not in_chennai(event):
        say(f"skip, '{(event['venue'] or event['area'] or '?')[:40]}' is outside Chennai")
        return "skipped"
    matches = store.find_duplicates(event, info.fingerprint)
    block = dedupe.blocking_match(matches)
    if block:
        say(f"skip, already on the map as #{block['id']} ('{(block['title'] or '')[:40]}')")
        return "skipped"
    if matches:
        review.append("possible duplicate of " + ", ".join(f"#{m['id']}" for m in matches[:3]))
    if caption_result["announces_event"] != "yes":
        review.append("caption didn't clearly announce an event")

    # 4. Where it goes. During the trial everything is reviewed; `confident` is
    # recorded so we can later count how often it would have been right.
    confident = not review
    event["status"] = "published" if auto_publish and confident else "review"
    where = event["venue"][:30] or event["area"] or "?"
    summary = f"'{event['title'][:40]}' | {event['category']} | {event['date'][:16]} | {where}"
    if event["status"] == "published":
        verdict = "PUBLISH"
    else:
        verdict = "review (confident)" if confident else "review: " + ", ".join(review)
    say(f"{summary} -> {verdict}")
    if dry_run:
        return "retry"  # nothing saved, so look at it again on a real run

    event["image_url"] = store.upload_poster(data, info)
    raw = details.get("raw") if isinstance(details.get("raw"), dict) else {}
    store.create_event(event, source="instagram_share", poster=info, extracted_data={
        **raw,
        "instagram_post": link,
        "instagram_caption": post["caption"][:2000],
        "pipeline": {"caption_check": caption_result, "confident": confident, "review_reasons": review},
    })
    return "published" if event["status"] == "published" else "added"


def main() -> int:
    ap = argparse.ArgumentParser(description="Send new event posters from Instagram to the review desk.")
    ap.add_argument("--dry-run", action="store_true", help="read posters and print, save nothing")
    ap.add_argument("--limit", type=int, default=MAX_POSTERS_PER_RUN, help="most posts to check this run")
    ap.add_argument("--auto-publish", action="store_true",
                    help="put events that pass every check straight on the map (default: all go to review)")
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
    budget, added, published, read = args.limit, 0, 0, 0
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
            print(f"  @{handle}: {len(posts)} new post(s) among the latest {LATEST_POSTS}")
            for post in posts[:budget]:
                pause(4, 12)
                result = handle_post(handle, post, args.dry_run, args.auto_publish)
                read += 1
                budget -= 1
                added += result == "added"
                published += result == "published"
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

    print(f"\n[Instagram] Checked {read} post(s): {published} published, {added} sent to the review desk"
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
