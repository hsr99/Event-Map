#!/usr/bin/env python3
"""
test/test_qwen.py - Test poster extraction using local Hugging Face Transformers pipeline.
Uses CPU-friendly Qwen vision model (default: Qwen/Qwen2-VL-2B-Instruct).
"""
import argparse
import json
import os
import sys
from datetime import date
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


_pipeline_cache = {}


def get_transformers_pipeline(model_id: str):
    if model_id not in _pipeline_cache:
        import torch
        from transformers import pipeline

        print(f"[test_qwen] Loading transformers pipeline for model '{model_id}' on CPU...")
        dtype = torch.float32
        pipe = pipeline(
            "image-text-to-text",
            model=model_id,
            torch_dtype=dtype,
            device="cpu",
        )
        _pipeline_cache[model_id] = pipe
    return _pipeline_cache[model_id]


def test_qwen(
    poster_path: Path,
    model_id: str = "Qwen/Qwen2-VL-2B-Instruct",
    out_file: Path = RESULTS_DIR / "test_results_qwen.json",
):
    pipe = get_transformers_pipeline(model_id)

    ref_date = date.today().isoformat()
    user_prompt = f"{SYSTEM_PROMPT}\n\nReference date (today): {ref_date}. Extract all event fields from this poster image."

    img = Image.open(poster_path).convert("RGB")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": user_prompt},
            ],
        }
    ]

    print(f"[test_qwen] Running pipeline inference for image: {poster_path.name}...")
    output = pipe(text=messages, max_new_tokens=1024)

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

    result = parse_model_output(text)
    result["_file"] = str(poster_path)
    result["_backend"] = f"transformers/{model_id}"
    print("\n--- Extracted Result (Local Transformers Qwen) ---")
    print(json.dumps(result, indent=2))

    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[test_qwen] Saved test results to {out_file}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test local Transformers vision extraction.")
    parser.add_argument("poster", nargs="?", default=str(ROOT_DIR / "frontend" / "public" / "posters" / "image2.png"), help="Path to poster image")
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2-VL-2B-Instruct",
        help="Model ID (default: Qwen/Qwen2-VL-2B-Instruct - fastest CPU friendly model)"
    )
    args = parser.parse_args()

    test_image = Path(args.poster)
    if not test_image.exists():
        print(f"Error: test image {test_image} not found", file=sys.stderr)
        sys.exit(1)

    test_qwen(test_image, model_id=args.model)
