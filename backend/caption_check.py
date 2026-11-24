"""
backend/caption_check.py - A cheap first look at an Instagram caption, before
spending a vision-model call on the picture.

Answers two questions from the caption text alone:
  - does it announce an event, workshop, class or meetup people can sign up for?
  - is it in Chennai?

Each answer is "yes", "no" or "unsure". Only a clear "no" should rule a post
out; "unsure" (including an empty caption, or the model being unavailable)
means "look at the poster to find out".
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Dict

MODEL = "gemini-3.5-flash-lite"

PROMPT = """\
You screen Instagram posts for a map of events in Chennai, India.

Read the caption and answer with ONLY this JSON:
{"announces_event": "yes" | "no" | "unsure",
 "in_chennai": "yes" | "no" | "unsure",
 "reason": "<under 15 words>"}

announces_event = "yes" only if the post invites people to attend or sign up for
something on a date that has not happened yet: an event, workshop, class, meetup,
show, walk, screening, sports meet, etc.
It is "no" for: a recap or thank-you for a past event, a product or menu for sale,
a giveaway, a portfolio or artwork post, a quote, a meme, a personal update.
Use "unsure" when the caption is too short or vague to tell; the poster image will
be checked next.

in_chennai = "no" only if the caption clearly places it outside Chennai and its
suburbs (another city, or online-only). "unsure" if no place is mentioned.

Posted on: {posted}
Account: @{account}
Caption:
<<<
{caption}
>>>
"""

UNSURE = {"announces_event": "unsure", "in_chennai": "unsure"}


def _answer(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in ("yes", "no", "unsure") else "unsure"


def check_caption(caption: str, posted_at: datetime, account: str) -> Dict[str, str]:
    """{'announces_event', 'in_chennai', 'reason'}; never raises."""
    caption = (caption or "").strip()
    if len(caption) < 15:
        return {**UNSURE, "reason": "no caption to go on"}
    api_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        return {**UNSURE, "reason": "caption check unavailable (no GEMINI_API_KEY)"}
    try:
        from google import genai
        from google.genai import types

        # Keep the client in a variable: the library closes an unreferenced
        # client before the request is sent.
        client = genai.Client(api_key=api_key)
        prompt = (PROMPT.replace("{posted}", posted_at.strftime("%Y-%m-%d"))
                        .replace("{account}", account)
                        .replace("{caption}", caption[:3000]))
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=MODEL, contents=prompt,
                    config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
                )
                break
            except Exception as exc:  # "model overloaded" is usually gone within seconds
                if attempt == 2 or "503" not in str(exc):
                    raise
                time.sleep(4 * (attempt + 1))
        raw = json.loads(response.text)
    except Exception as exc:  # model down or odd output: let the poster decide
        return {**UNSURE, "reason": f"caption check failed ({exc.__class__.__name__})"}
    return {
        "announces_event": _answer(raw.get("announces_event")),
        "in_chennai": _answer(raw.get("in_chennai")),
        "reason": str(raw.get("reason") or "")[:120],
    }


def rules_out(result: Dict[str, str]) -> bool:
    """True when the caption alone shows this isn't an upcoming Chennai event."""
    return result["announces_event"] == "no" or result["in_chennai"] == "no"
