#!/usr/bin/env python3
"""
test/test_groq.py - Test poster extraction using Groq API (Qwen model).
"""
import base64
import json
import os
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
RESULTS_DIR = SCRIPT_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Load .env from project root
load_dotenv(ROOT_DIR / ".env", override=True)
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


def image_to_base64_data_url(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    longest = max(w, h)
    if longest > 2048:
        scale = 2048 / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


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


def test_groq(poster_path: Path, model: str = "qwen/qwen3.8-27b", out_file: Path = RESULTS_DIR / "test_results_groq.json"):
    api_key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in environment or .env")

    print(f"[test_groq] Initializing Groq / OpenAI client for model: {model}...")
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
        )
    except ImportError:
        from groq import Groq
        client = Groq(api_key=api_key)

    data_url = image_to_base64_data_url(poster_path)
    ref_date = date.today().isoformat()
    user_prompt = f"Reference date (today): {ref_date}. Extract all event fields from this poster image."

    print(f"[test_groq] Sending request for image: {poster_path.name} to {model}...")
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        temperature=0.1,
    )

    content = completion.choices[0].message.content
    result = parse_model_output(content)
    result["_file"] = str(poster_path)
    result["_backend"] = f"groq/{model}"
    print("\n--- Extracted Result (Groq) ---")
    print(json.dumps(result, indent=2))

    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[test_groq] Saved test results to {out_file}")
    return result


if __name__ == "__main__":
    test_image = ROOT_DIR / "posters" / "image2.png"
    if len(sys.argv) > 1:
        test_image = Path(sys.argv[1])
    if not test_image.exists():
        print(f"Error: test image {test_image} not found", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
    test_groq(test_image, model=model)
