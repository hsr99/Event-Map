#!/usr/bin/env python3
"""
test_sources.py - smoke tests for the source tools in the events pipeline.

  python test_sources.py static  URL [URL ...]      httpx + BeautifulSoup (no browser)
  python test_sources.py crawl   URL [URL ...]      Crawl4AI (real headless browser)
  python test_sources.py compare URL [URL ...]      both, side by side with timings
  python test_sources.py insta   HANDLE [HANDLE ...] Instaloader, new posts only

Setup
-----
    pip install httpx beautifulsoup4 crawl4ai instaloader
    crawl4ai-setup            # downloads the browser Crawl4AI drives (one time)
    export BOT_CONTACT="you@example.com"   # put a real contact in the User-Agent

What each test tells you
------------------------
  static / crawl : does the page load, how much text and how many images come back,
                   and is there schema.org Event JSON-LD (free structured data!).
  compare        : whether you need the browser at all for a given site.
  insta          : whether Instagram lets your session read a small watchlist, what a
                   post record looks like (image URL, caption, @mentions), and how the
                   "new posts only" cache behaves.

Ground rules built in
---------------------
  * robots.txt is checked before any web fetch; disallowed URLs are skipped.
  * Instagram: read-only, tiny watchlist, one connection attempt (no retry loops), and
    the run STOPS at the first block, rate-limit or login prompt. Instagram's terms
    prohibit automated access, so use a throwaway account (never your main one), keep
    nothing in your pipeline dependent on it, and don't retry your way past a block.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

CONTACT = os.environ.get("BOT_CONTACT", "set-BOT_CONTACT-env-var")
UA = f"EventMapBot/0.1 (+{CONTACT})"
STATE_FILE = Path("state/insta_state.json")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def robots_allowed(url: str) -> tuple[bool, str]:
    """Check robots.txt for our user agent. Conservative: 401/403 on robots = skip."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        r = httpx.get(robots_url, timeout=10, headers={"User-Agent": UA},
                      follow_redirects=True)
    except httpx.HTTPError as exc:
        return True, f"robots.txt unreachable ({type(exc).__name__}); treated as allowed"
    if r.status_code in (401, 403):
        return False, f"robots.txt returned {r.status_code}"
    if r.status_code >= 400:
        return True, "no robots.txt"
    parser = RobotFileParser()
    parser.parse(r.text.splitlines())
    ok = parser.can_fetch(UA, url)
    return ok, "allowed by robots.txt" if ok else "disallowed by robots.txt"


def strip_markdown(md: str) -> str:
    """Visible text only: drop image/link URLs so Crawl4AI's size is comparable to bs4's."""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)          # images
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)         # links -> link text
    md = re.sub(r"https?://\S+", " ", md)                      # bare URLs
    md = re.sub(r"[#*_>`|-]+", " ", md)                          # markdown punctuation
    return re.sub(r"\s+", " ", md).strip()


def check_expect(text: str, expect: list[str]) -> dict:
    low = text.lower()
    return {kw: kw.lower() in low for kw in expect}


def short_err(msg: object, limit: int = 220) -> str:
    """First useful line(s) of a long error message."""
    lines = [ln.strip() for ln in str(msg).splitlines() if ln.strip()]
    text = " | ".join(lines[:3])
    return text[:limit] + ("..." if len(text) > limit else "")


def extract_jsonld_events(html: str) -> list[dict]:
    """Pull schema.org Event objects out of <script type="application/ld+json">."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            kind = node.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if any(isinstance(k, str) and k.endswith("Event") for k in kinds):
                keep = ("name", "startDate", "endDate", "location", "offers",
                        "url", "image", "organizer", "eventStatus")
                events.append({k: node[k] for k in keep if k in node})
            for value in node.values():          # also walks "@graph"
                if isinstance(value, (list, dict)):
                    walk(value)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or tag.get_text() or ""))
        except json.JSONDecodeError:
            continue
    return events


def summarise_html(html: str, base_url: str, expect: Optional[list] = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:image")
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src and not src.startswith("data:"):
            images.append(urljoin(base_url, src))
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    out = {
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "og_image": urljoin(base_url, og["content"]) if og and og.get("content") else None,
        "text_chars": len(text),
        "text_preview": text[:200],
        "image_count": len(images),
        "images_sample": images[:5],
        "link_count": len(soup.find_all("a", href=True)),
        "jsonld_events": extract_jsonld_events(html),
    }
    if expect:
        out["expect_found"] = check_expect(text, expect)
    return out


def show(label: str, data: dict) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# --------------------------------------------------------------------------- #
# static: httpx + BeautifulSoup
# --------------------------------------------------------------------------- #
def fetch_static(url: str, expect: Optional[list] = None) -> dict:
    ok, why = robots_allowed(url)
    if not ok:
        return {"url": url, "skipped": why}
    start = time.perf_counter()
    try:
        r = httpx.get(url, timeout=20, headers={"User-Agent": UA}, follow_redirects=True)
    except httpx.HTTPError as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}
    elapsed = round(time.perf_counter() - start, 2)
    out = {"url": url, "tool": "httpx+bs4", "robots": why, "status": r.status_code,
           "seconds": elapsed}
    out.update(summarise_html(r.text, str(r.url), expect))
    return out


def cmd_static(args) -> int:
    for url in args.urls:
        show(url, fetch_static(url, args.expect))
    return 0


# --------------------------------------------------------------------------- #
# crawl: Crawl4AI
# --------------------------------------------------------------------------- #
async def crawl_many(urls: list[str], expect: Optional[list] = None) -> list[dict]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError:
        sys.exit("crawl4ai is not installed. pip install crawl4ai && crawl4ai-setup")

    browser_cfg = BrowserConfig(headless=True, verbose=False, user_agent=UA)
    run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=30000)
    results = []
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        for url in urls:
            ok, why = robots_allowed(url)
            if not ok:
                results.append({"url": url, "skipped": why})
                continue
            start = time.perf_counter()
            try:
                res = await crawler.arun(url=url, config=run_cfg)
            except Exception as exc:                      # browser missing, timeout, ...
                results.append({"url": url, "error": f"{type(exc).__name__}: {short_err(exc)}"})
                continue
            elapsed = round(time.perf_counter() - start, 2)
            if not res.success:
                results.append({"url": url, "tool": "crawl4ai", "seconds": elapsed,
                                "error": short_err(res.error_message), "status": res.status_code})
                continue
            md = res.markdown
            md_text = getattr(md, "raw_markdown", None) or str(md or "")
            media_images = (res.media or {}).get("images", [])
            html_summary = summarise_html(res.html or "", url)
            visible = strip_markdown(md_text)
            item = {
                "url": url, "tool": "crawl4ai", "robots": why,
                "status": res.status_code, "seconds": elapsed,
                "title": html_summary["title"],
                "text_chars": len(visible),          # comparable with the static number
                "markdown_chars": len(md_text),      # inflated by link/image URLs
                "markdown_preview": md_text[:200].replace("\n", " "),
                # Crawl4AI's media list drops low-score images, so fall back to the HTML
                "image_count": len(media_images) or html_summary["image_count"],
                "images_sample": ([i.get("src") for i in media_images[:5]]
                                  or html_summary["images_sample"]),
                "images_source": "crawl4ai media" if media_images else "html <img> tags",
                "internal_links": len((res.links or {}).get("internal", [])),
                "jsonld_events": html_summary["jsonld_events"],
            }
            if expect:
                item["expect_found"] = check_expect(visible, expect)
            results.append(item)
    return results


def cmd_crawl(args) -> int:
    for item in asyncio.run(crawl_many(args.urls, args.expect)):
        show(item["url"], item)
    return 0


def cmd_compare(args) -> int:
    static_results = {u: fetch_static(u, args.expect) for u in args.urls}
    crawl_results = {r["url"]: r for r in asyncio.run(crawl_many(args.urls, args.expect))}
    print(f"\n{'URL':45} {'tool':10} {'sec':>6} {'visible chars':>14} {'images':>7} "
          f"{'events':>7} {'expect':>7}")
    for url in args.urls:
        for res in (static_results[url], crawl_results.get(url, {})):
            if "skipped" in res or "error" in res:
                print(f"{url[:45]:45} {res.get('tool', '?'):10} "
                      f"{res.get('skipped') or res.get('error')}")
                continue
            found = res.get("expect_found")
            hit = f"{sum(found.values())}/{len(found)}" if found else "-"
            print(f"{url[:45]:45} {res['tool']:10} {res['seconds']:>6} {res['text_chars']:>14} "
                  f"{res['image_count']:>7} {len(res['jsonld_events']):>7} {hit:>7}")
    print("\nReading it: compare the 'visible chars' and 'expect' of the two rows per URL. "
          "If static finds the same expected words (and similar text), you don't need the "
          "browser for that site. Image counts aren't comparable (Crawl4AI filters small ones).")
    return 0


# --------------------------------------------------------------------------- #
# insta: Instaloader, new posts only
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def cmd_insta(args) -> int:
    try:
        import instaloader
        from instaloader import exceptions as ie
    except ImportError:
        sys.exit("instaloader is not installed. pip install instaloader")

    loader = instaloader.Instaloader(
        download_pictures=False, download_videos=False, download_video_thumbnails=False,
        download_geotags=False, download_comments=False, save_metadata=False,
        compress_json=False, quiet=True,
        max_connection_attempts=1,      # one try: no retry loops against a block
        request_timeout=30,
    )
    if args.login_user:
        try:
            loader.load_session_from_file(args.login_user)
        except FileNotFoundError:
            sys.exit(f"No saved session for {args.login_user!r}. Create one once with:\n"
                     f"  instaloader --login {args.login_user}\n"
                     f"(use a throwaway account; the password is typed into Instaloader, "
                     f"never into this script)")

    state = load_state()
    image_dir = Path(args.download) if args.download else None
    if image_dir:
        image_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    total_new = 0

    for n, handle in enumerate(args.handles):
        handle = handle.lstrip("@")
        if n:
            time.sleep(args.delay)      # fixed courtesy pause between profiles
        print(f"\n--- @{handle}")
        try:
            profile = instaloader.Profile.from_username(loader.context, handle)
            if profile.is_private:
                print("  private account: skipped (we don't try to access these)")
                continue
            seen = state.get(handle, {})
            last_date = datetime.fromisoformat(seen["last_date"]) if seen.get("last_date") else None
            new_posts = []
            for post in profile.get_posts():            # newest first
                if last_date and post.date_utc <= last_date:
                    break
                new_posts.append(post)
                if len(new_posts) >= args.max_posts:
                    break
        except ie.ProfileNotExistsException:
            print("  profile does not exist")
            continue
        except (ie.LoginRequiredException, ie.TooManyRequestsException,
                ie.ConnectionException, ie.QueryReturnedBadRequestException) as exc:
            print(f"  STOP: Instagram blocked or asked for login ({type(exc).__name__}).")
            print(f"  Details: {short_err(exc, 300)}")
            print("  Not retrying. Wait it out, or fall back to the manual share feed.")
            return 2
        except ie.InstaloaderException as exc:
            print(f"  error: {type(exc).__name__}: {exc}")
            continue

        print(f"  {len(new_posts)} new post(s)")
        with out_path.open("a", encoding="utf-8") as fh:
            for post in new_posts:
                record = {
                    "handle": handle,
                    "shortcode": post.shortcode,
                    "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "date_utc": post.date_utc.isoformat(),
                    "caption": post.caption or "",
                    "mentions": post.caption_mentions,
                    "hashtags": post.caption_hashtags,
                    "is_video": post.is_video,
                    "media_count": post.mediacount,
                    "image_url": post.url,
                }
                if image_dir and not post.is_video:
                    try:
                        img = httpx.get(post.url, timeout=30, headers={"User-Agent": UA})
                        img.raise_for_status()
                        path = image_dir / f"{handle}_{post.shortcode}.jpg"
                        path.write_bytes(img.content)
                        record["local_image"] = str(path)
                    except httpx.HTTPError as exc:
                        record["image_error"] = str(exc)
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                first_line = (post.caption or "").strip().splitlines()[:1]
                print(f"  - {post.date_utc:%Y-%m-%d} {post.shortcode} "
                      f"{'(video) ' if post.is_video else ''}{first_line[0][:60] if first_line else ''}")
        if new_posts:
            state[handle] = {"last_date": max(p.date_utc for p in new_posts).isoformat()}
            save_state(state)
            total_new += len(new_posts)

    print(f"\nDone. {total_new} new post(s) appended to {out_path}. State: {STATE_FILE}")
    return 0


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("static", cmd_static, "httpx + BeautifulSoup"),
                            ("crawl", cmd_crawl, "Crawl4AI"),
                            ("compare", cmd_compare, "static vs Crawl4AI")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("urls", nargs="+")
        p.add_argument("--expect", nargs="*", default=[], metavar="WORD",
                       help="words you know are on the page (event name, venue, date); "
                            "reports which tool actually found them")
        p.set_defaults(func=fn)

    p = sub.add_parser("insta", help="Instaloader watchlist test")
    p.add_argument("handles", nargs="+", help="public accounts, e.g. someorganizer")
    p.add_argument("--login-user", help="throwaway account with a saved Instaloader session")
    p.add_argument("--max-posts", type=int, default=6, help="max new posts per profile")
    p.add_argument("--delay", type=float, default=8.0, help="seconds between profiles")
    p.add_argument("--download", metavar="DIR", help="also save post images here")
    p.add_argument("--out", default="insta_posts.jsonl")
    p.set_defaults(func=cmd_insta)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())