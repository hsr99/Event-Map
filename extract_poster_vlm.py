#!/usr/bin/env python3
"""
extract_poster_vlm.py - VLM-powered event field extraction from Chennai event posters.

Backend Order (Auto Fallback):
  1. Primary      : Groq API (default: meta-llama/llama-4-scout-17b-16e-instruct -> qwen/qwen3.8-27b)
  2. First Backup : Google Gemini (default: gemini-3.5-flash-lite)
  3. Last Order   : Qwen via Hugging Face Transformers pipeline (default: Qwen/Qwen2-VL-2B-Instruct on CPU)

The automatic fallback cascade triggers if:
  - An API key/token is missing, OR
  - An API call fails (quota, rate limit, model availability, network)

You can also force any backend explicitly using `--backend {groq, gemini, qwen, hf}`.

Setup
-----
    pip install groq openai google-genai huggingface_hub transformers torch torchvision pillow python-dotenv

Usage
-----
    python extract_poster_vlm.py frontend/public/posters/
    python extract_poster_vlm.py frontend/public/posters/ --out results.json --csv results.csv
    python extract_poster_vlm.py frontend/public/posters/ --backend groq
    python extract_poster_vlm.py frontend/public/posters/ --backend gemini
    python extract_poster_vlm.py frontend/public/posters/ --backend qwen
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from PIL import Image

load_dotenv(override=True)

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
  "contact_phone": string | null,   // organiser phone / WhatsApp number printed for bookings or enquiries
  "instagram":     string | null,   // organiser's Instagram handle, e.g. "@chennaigigs"
  "category":      string | null,   // one of: tech, music, comedy, art_workshop,
                                    //   sports_fitness, food_drink, networking_business,
                                    //   film_theatre, community_social, college_cultural
  "description":   string | null,   // 1-2 sentence summary of the event, in English
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


def build_user_prompt(ref: date, context: str = "") -> str:
    prompt = (
        f"Reference date (today): {ref.isoformat()}. "
        "Extract all event fields from this poster image."
    )
    if context.strip():
        # e.g. the Instagram caption posted with the poster: it often has the year,
        # full address or booking link that the poster itself leaves out.
        prompt += (
            "\n\nText posted alongside this poster (may fill gaps the poster leaves; "
            "if the two disagree, trust the poster):\n<<<\n" + context.strip()[:3000] + "\n>>>"
        )
    return prompt


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


def image_to_data_url(img: Image.Image) -> str:
    img_bytes = image_to_bytes(img)
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


# --------------------------------------------------------------------------- #
# Post-processing
# --------------------------------------------------------------------------- #
REQUIRED_FIELDS = [
    "event_name", "date", "date_end", "time", "time_end",
    "venue", "area", "ticket_price", "booking_link", "category", "description",
    "contact_phone", "instagram",
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
# Backend 1: Groq (Primary)
# --------------------------------------------------------------------------- #
def call_groq(
    img: Image.Image,
    ref: date,
    model: str = "qwen/qwen3.8-27b",
    context: str = "",
) -> dict:
    api_key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in environment or .env")

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
        )
    except ImportError:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
        except ImportError:
            raise RuntimeError("Run: pip install groq openai")

    data_url = image_to_data_url(img)
    user_prompt = build_user_prompt(ref, context)

    # Models to try in order on Groq
    candidates = [model]
    if model != "qwen/qwen3.6-27b":
        candidates.append("qwen/qwen3.6-27b")

    last_exc = None
    for m in candidates:
        try:
            completion = client.chat.completions.create(
                model=m,
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
            text = completion.choices[0].message.content
            raw = parse_model_output(text)
            raw["_backend"] = f"groq/{m}"
            return raw
        except Exception as exc:
            last_exc = exc
            print(f"[vlm] Groq model '{m}' failed: {exc}", file=sys.stderr)

    raise RuntimeError(f"All Groq candidates failed: {last_exc}")


# --------------------------------------------------------------------------- #
# Backend 2: Google Gemini (First Backup)
# --------------------------------------------------------------------------- #
def call_gemini(
    img: Image.Image,
    ref: date,
    model: str = "gemini-3.5-flash-lite",
    context: str = "",
) -> dict:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("Run: pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    img_bytes = image_to_bytes(img)

    image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    text_part = types.Part.from_text(text=build_user_prompt(ref, context))

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=[image_part, text_part])],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            break
        except Exception as exc:  # "model overloaded" (503) is usually gone within seconds
            if attempt == 2 or "503" not in str(exc):
                raise
            time.sleep(4 * (attempt + 1))
    raw = parse_model_output(response.text)
    raw["_backend"] = f"gemini/{model}"
    return raw


# --------------------------------------------------------------------------- #
# Backend 3: Hugging Face Transformers pipeline (Last Order, CPU Friendly)
# --------------------------------------------------------------------------- #
_local_pipeline = None


def call_local_transformers_qwen(
    img: Image.Image,
    ref: date,
    model_id: str = "Qwen/Qwen2-VL-2B-Instruct",
    context: str = "",
) -> dict:
    """
    Runs local CPU inference using Hugging Face transformers pipeline.
    Qwen2-VL-2B-Instruct is chosen as the most CPU-friendly & fast vision model
    compared to 17B Scout (which is >30GB and too heavy for CPU).
    """
    global _local_pipeline
    try:
        import torch
        from transformers import pipeline
    except ImportError:
        raise RuntimeError("Run: pip install transformers torch torchvision")

    if _local_pipeline is None:
        print(f"[vlm] Loading Hugging Face pipeline for '{model_id}' on CPU...", file=sys.stderr)
        _local_pipeline = pipeline(
            "image-text-to-text",
            model=model_id,
            torch_dtype=torch.float32,
            device="cpu",
        )

    user_prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(ref, context)}"
    rgb_img = img.convert("RGB")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": rgb_img},
                {"type": "text", "text": user_prompt},
            ],
        }
    ]

    output = _local_pipeline(text=messages, max_new_tokens=1024)
    if isinstance(output, list) and len(output) > 0:
        generated = output[0]
        if isinstance(generated, dict):
            text = generated.get("generated_text") or generated.get("content") or str(generated)
            if isinstance(text, list):
                text = text[-1].get("content", "") if isinstance(text[-1], dict) else str(text[-1])
        else:
            text = str(generated)
    else:
        text = str(output)

    raw = parse_model_output(text)
    raw["_backend"] = f"transformers/{model_id}"
    return raw


# --------------------------------------------------------------------------- #
# Orchestration with Cascade: Groq (1st) -> Gemini (2nd) -> Qwen (3rd)
# --------------------------------------------------------------------------- #
def extract_poster_vlm(
    path: Path,
    ref: date,
    backend: str = "auto",
    groq_model: str = "qwen/qwen3.8-27b",
    gemini_model: str = "gemini-3.5-flash-lite",
    qwen_model: str = "Qwen/Qwen2-VL-2B-Instruct",
) -> dict:
    return extract_from_image(
        load_image(path), path, ref,
        backend=backend, groq_model=groq_model,
        gemini_model=gemini_model, qwen_model=qwen_model,
    )


def extract_from_image(
    img: Image.Image,
    path: Path,
    ref: date,
    backend: str = "auto",
    groq_model: str = "qwen/qwen3.8-27b",
    gemini_model: str = "gemini-3.5-flash-lite",
    qwen_model: str = "Qwen/Qwen2-VL-2B-Instruct",
    context: str = "",
) -> dict:
    """Run the Groq -> Gemini -> local Qwen cascade on an already-loaded image.

    `path` is only recorded in the result's "file" field. `context` is optional
    text posted with the poster (e.g. an Instagram caption).
    """
    raw = None
    errors = []

    # 1. Try Groq (Primary)
    if backend in ("auto", "groq"):
        try:
            raw = call_groq(img, ref, model=groq_model, context=context)
        except Exception as exc:
            errors.append(f"Groq failed: {exc}")
            if backend == "groq":
                raise
            print(f"[vlm] Groq failed, falling back to Gemini (1st backup): {exc}", file=sys.stderr)

    # 2. Try Gemini (First backup)
    if raw is None and backend in ("auto", "gemini"):
        try:
            raw = call_gemini(img, ref, model=gemini_model, context=context)
        except Exception as exc:
            errors.append(f"Gemini failed: {exc}")
            if backend == "gemini":
                raise
            print(f"[vlm] Gemini failed, falling back to Qwen / Transformers (last order): {exc}", file=sys.stderr)

    # 3. Try Qwen / Local Transformers (Last order)
    if raw is None and backend in ("auto", "qwen", "hf"):
        try:
            raw = call_local_transformers_qwen(img, ref, model_id=qwen_model, context=context)
        except Exception as exc:
            errors.append(f"Qwen / Transformers failed: {exc}")
            if backend in ("qwen", "hf"):
                raise

    if raw is None:
        raise RuntimeError("All backends failed:\n" + "\n".join(errors))

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
        description="Extract event fields from posters using Vision-Language Models (Groq -> Gemini -> Qwen)."
    )
    ap.add_argument("path", type=Path, help="poster image or folder of posters")
    ap.add_argument("--out", type=Path, default=Path("results.json"), help="JSON output path")
    ap.add_argument("--csv", type=Path, help="optional CSV output path")
    ap.add_argument(
        "--post-date", type=date.fromisoformat, default=date.today(),
        help="YYYY-MM-DD reference date (used to infer missing years)"
    )
    ap.add_argument(
        "--backend", choices=["auto", "groq", "gemini", "qwen", "hf"], default="auto",
        help="'auto' = Groq first -> Gemini backup -> Qwen local fallback"
    )
    ap.add_argument(
        "--groq-model", default="qwen/qwen3.8-27b",
        help="Groq model ID (default: qwen/qwen3.8-27b)"
    )
    ap.add_argument(
        "--gemini-model", default="gemini-3.5-flash-lite",
        help="Google Gemini model ID (default: gemini-3.5-flash-lite)"
    )
    ap.add_argument(
        "--qwen-model", default="Qwen/Qwen2-VL-2B-Instruct",
        help="Hugging Face model ID for local transformers fallback (default: Qwen/Qwen2-VL-2B-Instruct)"
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
                groq_model=args.groq_model,
                gemini_model=args.gemini_model,
                qwen_model=args.qwen_model,
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
