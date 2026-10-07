#!/usr/bin/env python3
"""
test_gemini.py - Test poster extraction using Google Gemini.
"""
import json
import os
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image

load_dotenv(override=True)

SYSTEM_PROMPT = """\
You are an expert at reading Chennai event posters (images). Extract structured
information and return ONLY a valid JSON object with these exact keys:

{
  "event_name":    string | null,
  "date":          string | null,   // ISO 8601 YYYY-MM-DD start date
  "date_end":      string | null,   // ISO 8601 end date if multi-day, else null
  "time":          string | null,   // 24-h HH:MM start time
  "time_end":      string | null,   // 24-h HH:MM end time or null
  "venue":         string | null,   // venue / place name
  "area":          string | null,   // Chennai locality e.g. "Velachery", "T Nagar"
  "ticket_price":  string | null,   // e.g. "Free", "Rs.299", "Rs.199-Rs.499"
  "booking_link":  string | null,   // registration / booking URL if present
  "category":      string | null,   // one of: tech, music, comedy, art_workshop,
                                    //   sports_fitness, food_drink, networking_business,
                                    //   film_theatre, community_social
  "confidence": {
    "event_name":   float,
    "date":         float,
    "time":         float,
    "venue":        float,
    "area":         float,
    "ticket_price": float,
    "booking_link": float,
    "category":     float
  },
  "notes": [string]
}

Rules:
- If unsure about a field, set it to null and confidence to 0.0.
- For dates: if the year is not printed, infer it from the reference date supplied.
- For prices: if free, return "Free".
- Return ONLY the JSON object with no markdown fences or explanation.
"""


def image_to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = BytesIO()
    rgb = img.convert("RGB")
    w, h = rgb.size
    longest = max(w, h)
    if longest > 2048:
        scale = 2048 / longest
        rgb = rgb.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    rgb.save(buf, format=fmt, quality=92)
    return buf.getvalue()


def parse_model_output(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in output:\n{text[:300]}")
    return json.loads(text[start:end])


def test_gemini(poster_path: Path, model: str = "gemini-2.5-flash"):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("Run: pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment or .env")

    print(f"[test_gemini] Initializing Gemini client with model: {model}...")
    client = genai.Client(api_key=api_key)

    img = Image.open(poster_path)
    img_bytes = image_to_bytes(img)

    ref_date = date.today().isoformat()
    user_prompt = f"Reference date (today): {ref_date}. Extract all event fields from this poster image."

    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    text_part = types.Part.from_text(text=user_prompt)

    print(f"[test_gemini] Sending request for image: {poster_path.name}...")
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[image_part, text_part])],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )

    result = parse_model_output(response.text)
    result["_file"] = str(poster_path)
    result["_backend"] = f"gemini/{model}"
    print("\n--- Extracted Result (Gemini) ---")
    print(json.dumps(result, indent=2))

    out_file = Path("test_results_gemini.json")
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[test_gemini] Saved test results to {out_file}")
    return result


if __name__ == "__main__":
    test_image = Path("posters/image2.png")
    if len(sys.argv) > 1:
        test_image = Path(sys.argv[1])
    if not test_image.exists():
        print(f"Error: test image {test_image} not found", file=sys.stderr)
        sys.exit(1)
    
    # Default to gemini-3.5-flash-lite (fast, cheap)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    test_gemini(test_image, model=model_name)
