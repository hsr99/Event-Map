#!/usr/bin/env python3
"""
tools/review_events.py - Approve or hide events waiting for review.

Submissions from the website and low-confidence ingests are saved with status
"review" and stay off the site until approved here.

Usage:
    python tools/review_events.py                # list the review queue
    python tools/review_events.py approve 12 15  # publish events 12 and 15
    python tools/review_events.py hide 13        # reject / take down event 13
"""
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend import store  # noqa: E402

ACTIONS = {"approve": "published", "hide": "hidden"}


def show_queue() -> None:
    queue = store.list_review_queue()
    if not queue:
        print("Review queue is empty.")
        return
    print(f"{len(queue)} event(s) waiting for review:\n")
    for ev in queue:
        sub = (ev.get("submissions") or [{}])
        sub = sub[0] if isinstance(sub, list) and sub else (sub if isinstance(sub, dict) else {})
        price = "Free" if ev.get("is_free") else f"Rs.{ev.get('price')}"
        print(f"  #{ev['id']}  {ev['title']}")
        print(f"        {ev['category']} | {ev['date']} | {ev['venue']} ({ev['area']}) | {price}")
        if ev.get("booking_link"):
            print(f"        link:    {ev['booking_link']}")
        if ev.get("image_url"):
            print(f"        poster:  {ev['image_url']}")
        flags = ((sub.get("extracted_data") or {}).get("needs_review")) if sub else None
        print(f"        source:  {sub.get('source', '?')}"
              f"{' | contact: ' + sub['submitter_contact'] if sub.get('submitter_contact') else ''}"
              f"{' | model unsure about: ' + ', '.join(flags) if flags else ''}")
        print()
    print("Approve with: python tools/review_events.py approve <id> [<id> ...]")


def main() -> int:
    ap = argparse.ArgumentParser(description="Review queue for submitted events.")
    ap.add_argument("action", nargs="?", choices=sorted(ACTIONS), help="approve or hide")
    ap.add_argument("ids", nargs="*", type=int, help="event ids")
    args = ap.parse_args()

    try:
        if not args.action:
            show_queue()
            return 0
        if not args.ids:
            ap.error("give at least one event id")
        for event_id in args.ids:
            updated = store.set_status(event_id, ACTIONS[args.action])
            print(f"  #{event_id}: {'-> ' + updated['status'] if updated else 'not found'}")
        return 0
    except store.StoreNotConfigured as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
