#!/usr/bin/env python3
"""
extract_poster_vlm.py - VLM-powered event field extraction from Chennai event posters.

Primary  : Google Gemini 3.5 Flash Lite  (free-tier friendly, fast, cheap)
Fallback : HuggingFace Serverless Inference API  (HTTP only, no local GPU/download needed)
           Default model: Qwen/Qwen2.5-VL-3B-Instruct
           Set HF_TOKEN in your .env for authenticated (higher rate-limit) access.

The fallback is activated automatically if:
  - GEMINI_API_KEY is not set / missing, OR
  - the Gemini call fails (quota, network, etc.), OR
  - you explicitly pass --backend hf

Output schema is identical to extract_poster.py so results are drop-in compatible.

Setup
-----
    pip install google-genai pillow python-dotenv huggingface_hub

Usage
-----
    python extract_poster_vlm.py poster.jpg
    python extract_poster_vlm.py posters/ --out results.json --csv results.csv
    python extract_poster_vlm.py posters/ --post-date 2026-10-05
    python extract_poster_vlm.py posters/ --backend hf   # force HF fallback
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from PIL import Image

load_dotenv()  # picks up GEMINI_API_KEY from .env

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
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


def build_user_prompt(ref: date) -> str:
    return (
        f"Reference date (today): {ref.isoformat()}. "
        "Extract all event fields from this poster image."
    )


# --------------------------------------------------------------------------- #
# Image helpers
# --------------------------------------------------------------------------- #
def load_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img.load()
    return img


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


# --------------------------------------------------------------------------- #
# Post-processing
# --------------------------------------------------------------------------- #
REQUIRED_FIELDS = [
    "event_name", "date", "date_end", "time", "time_end",
    "venue", "area", "ticket_price", "booking_link", "category",
]
CONFIDENCE_FIELDS = [
    "event_name", "date", "time", "venue", "area",
    "ticket_price", "booking_link", "category",
]


def coerce_result(raw: dict, path: Path) -> dict:
    result = {"file": str(path)}
    for f in REQUIRED_FIELDS:
        result[f] = raw.get(f)

    conf = raw.get("confidence") or {}
    result["confidence"] = {f: float(conf.get(f, 0.0)) for f in CONFIDENCE_FIELDS}
    result["notes"] = list(raw.get("notes") or [])

    review = []
    if result["event_name"] is None or result["confidence"]["event_name"] < 0.55:
        review.append("event_name")
    if result["date"] is None or result["confidence"]["date"] < 0.55:
        review.append("date")
    if result["venue"] is None and result["area"] is None:
        review.append("venue_or_area")
    elif result["venue"] and result["confidence"]["venue"] < 0.55:
        review.append("venue")
    result["needs_review"] = review
    result["backend"] = raw.get("_backend", "unknown")
    return result


def parse_model_output(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object in model output:\n{text[:300]}")
    return json.loads(text[start:end])


# --------------------------------------------------------------------------- #
# Backend: Gemini 2.0 Flash Lite
# --------------------------------------------------------------------------- #
def call_gemini(img: Image.Image, ref: date, model: str = "gemini-3.5-flash-lite") -> dict:
    try:
        # pyrefly: ignore [missing-import]
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("Run: pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"')
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    img_bytes = image_to_bytes(img)

    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    text_part = types.Part.from_text(text=build_user_prompt(ref))

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[image_part, text_part])],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    raw = parse_model_output(response.text)
    raw["_backend"] = f"gemini/{model}"
    return raw


# --------------------------------------------------------------------------- #
# Backend: HuggingFace Serverless Inference API (HTTP fallback, no GPU needed)
# --------------------------------------------------------------------------- #
def call_hf_inference(
    img: Image.Image,
    ref: date,
    model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct",
) -> dict:
    """
    Calls the HuggingFace Serverless Inference API via HTTP.
    No local model download, no GPU required — works on any machine.
    Requires: pip install huggingface_hub
    Set HF_TOKEN in .env for authenticated access (higher rate limits).
    """
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise RuntimeError("Run: pip install huggingface_hub")

    hf_token = os.environ.get("HF_TOKEN", "").strip() or None
    if not hf_token:
        print(
            "[vlm] HF_TOKEN not set — using unauthenticated HF Inference (may be rate-limited).",
            file=sys.stderr,
        )

    # Encode image as a base64 data URL
    img_bytes = image_to_bytes(img)
    b64 = base64.b64encode(img_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

    client = InferenceClient(
        provider="hf-inference",
        api_key=hf_token,
    )

    print(f"[vlm] Calling HF Inference API: {model_id}", file=sys.stderr)
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": build_user_prompt(ref)},
                ],
            },
        ],
        max_tokens=1024,
        temperature=0.1,
    )

    text = response.choices[0].message.content
    raw = parse_model_output(text)
    raw["_backend"] = f"hf-inference/{model_id}"
    return raw


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def extract_poster_vlm(
    path: Path,
    ref: date,
    backend: str = "auto",
    gemini_model: str = "gemini-3.5-flash-lite",
    hf_model: str = "Qwen/Qwen2.5-VL-3B-Instruct",
) -> dict:
    img = load_image(path)
    raw = None
    errors = []

    if backend in ("auto", "gemini"):
        try:
            raw = call_gemini(img, ref, model=gemini_model)
        except Exception as exc:
            errors.append(f"Gemini failed: {exc}")
            if backend == "gemini":
                raise
            print(f"[vlm] Gemini error, falling back to HF Inference API: {exc}", file=sys.stderr)

    if raw is None:
        try:
            raw = call_hf_inference(img, ref, model_id=hf_model)
        except Exception as exc:
            errors.append(f"HF Inference failed: {exc}")
            raise RuntimeError("Both backends failed:\n" + "\n".join(errors)) from exc

    return coerce_result(raw, path)


# --------------------------------------------------------------------------- #
# CSV / output helpers
# --------------------------------------------------------------------------- #
CSV_FIELDS = [
    "file", "event_name", "date", "date_end", "time", "time_end",
    "venue", "area", "ticket_price", "booking_link", "category",
    "backend", "needs_review",
]


def find_images(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract event fields from posters using a Vision-Language Model."
    )
    ap.add_argument("path", type=Path, help="poster image or folder of posters")
    ap.add_argument("--out", type=Path, default=Path("results.json"), help="JSON output path")
    ap.add_argument("--csv", type=Path, help="optional CSV output path")
    ap.add_argument(
        "--post-date", type=date.fromisoformat, default=date.today(),
        help="YYYY-MM-DD reference date (used to infer missing years)"
    )
    ap.add_argument(
        "--backend", choices=["auto", "gemini", "hf"], default="auto",
        help="'auto' = try Gemini first, fall back to HF Serverless Inference API"
    )
    ap.add_argument("--gemini-model", default="gemini-3.5-flash-lite")
    ap.add_argument(
        "--hf-model", default="Qwen/Qwen2.5-VL-3B-Instruct",
        help="HuggingFace model ID for the serverless fallback"
    )
    args = ap.parse_args()

    images = find_images(args.path)
    if not images:
        sys.exit(f"No images found at {args.path}")

    results = []
    for n, path in enumerate(images, 1):
        print(f"[{n}/{len(images)}] {path.name}", file=sys.stderr)
        try:
            res = extract_poster_vlm(
                path,
                ref=args.post_date,
                backend=args.backend,
                gemini_model=args.gemini_model,
                hf_model=args.hf_model,
            )
        except Exception as exc:
            res = {"file": str(path), "error": str(exc), "needs_review": ["error"]}
        results.append(res)

    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(results)} result(s) to {args.out}", file=sys.stderr)

    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                row = dict(r)
                row["needs_review"] = ";".join(r.get("needs_review") or [])
                writer.writerow(row)
        print(f"Wrote CSV to {args.csv}", file=sys.stderr)

    flagged = sum(1 for r in results if r.get("needs_review"))
    print(f"{flagged}/{len(results)} poster(s) flagged for review.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
