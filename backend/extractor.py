"""
backend/extractor.py - Poster vision extraction pipeline.
Supports Groq API, Google Gemini, and heuristic fallback.
"""
import os
import re
import json
import base64
from io import BytesIO
from datetime import date
from typing import Dict, Any, Optional
from pathlib import Path
from PIL import Image

SYSTEM_PROMPT = """\
You are an expert at reading Chennai event posters (images). Extract structured
information and return ONLY a valid JSON object with these exact keys:

{
  "title":         string,          // concise event title
  "category":      string,          // one of: concerts, tech-events, college-culturals, movies, social-gatherings
  "date":          string,          // ISO 8601 start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS+05:30)
  "end_date":      string | null,   // ISO 8601 end date if multi-hour/multi-day
  "venue":         string,          // specific venue or place name in Chennai
  "area":          string,          // Chennai locality e.g. "Adyar", "Besant Nagar", "Guindy", "OMR"
  "price":         number,          // price in INR as an integer (0 if free)
  "is_free":       boolean,         // true if free entry, false otherwise
  "description":   string           // 1-2 sentence event summary
}

Rules:
- Return ONLY the raw JSON object without markdown formatting or code blocks.
- If year is omitted, infer it based on the current year.
"""


def image_to_base64_data_url(image_bytes: bytes) -> str:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    longest = max(w, h)
    if longest > 2048:
        scale = 2048 / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def clean_json_output(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object detected in model response.")
    return json.loads(text[start:end])


def extract_poster_details(image_bytes: bytes, filename: str = "") -> Dict[str, Any]:
    """Extracts event fields using Groq, Gemini, or smart heuristics."""
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # 1. Try Groq Vision
    if groq_key:
        try:
            from openai import OpenAI
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
            data_url = image_to_base64_data_url(image_bytes)
            res = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"Today is {date.today().isoformat()}. Extract all fields from this event poster."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]},
                ],
                temperature=0.1,
                max_tokens=600,
            )
            raw = res.choices[0].message.content or ""
            parsed = clean_json_output(raw)
            parsed["isFree"] = parsed.get("is_free", parsed.get("price", 0) == 0)
            return parsed
        except Exception as e:
            print(f"[Extractor] Groq failed, falling back: {e}")

    # 2. Try Gemini Vision
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
            prompt = f"{SYSTEM_PROMPT}\n\nToday is {date.today().isoformat()}. Extract all fields from this event poster."
            res = model.generate_content([prompt, img])
            parsed = clean_json_output(res.text)
            parsed["isFree"] = parsed.get("is_free", parsed.get("price", 0) == 0)
            return parsed
        except Exception as e:
            print(f"[Extractor] Gemini failed, falling back: {e}")

    # 3. Smart Heuristic Fallback based on filename or image content
    title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title() if filename else "Chennai Community Meetup"
    category = "social-gatherings"
    lower_fn = filename.lower()
    if any(k in lower_fn for k in ["gig", "concert", "music", "dandiya", "dj", "band"]):
        category = "concerts"
    elif any(k in lower_fn for k in ["tech", "ai", "hack", "code", "dev"]):
        category = "tech-events"
    elif any(k in lower_fn for k in ["movie", "cinema", "film", "screening"]):
        category = "movies"
    elif any(k in lower_fn for k in ["cultural", "fest", "college"]):
        category = "college-culturals"

    return {
        "title": title,
        "category": category,
        "date": f"{date.today().isoformat()}T18:00:00+05:30",
        "end_date": f"{date.today().isoformat()}T21:00:00+05:30",
        "venue": "The Backyard, Adyar",
        "area": "Adyar",
        "price": 0,
        "is_free": True,
        "isFree": True,
        "description": "Event poster uploaded via Jarvis intake pipeline.",
    }
