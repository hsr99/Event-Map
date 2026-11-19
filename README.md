# Chennai Event Map - Poster Field Extraction

Vision-Language Model (VLM) powered event field extraction for Chennai event posters.

## Fallback Cascade Order
1. **Primary**: **Groq API**
   - Model: `qwen/qwen3.8-27b` (fast, free tier, high throughput)
2. **First Backup**: **Google Gemini**
   - Model: `gemini-3.5-flash-lite` (free-tier friendly, fast, cheap)
3. **Last Order**: **Local Hugging Face Transformers (CPU friendly)**
   - Model: `Qwen/Qwen2-VL-2B-Instruct` (no API cost, runs locally via `transformers.pipeline("image-text-to-text")`)

---

## Directory Structure

```
Chennai-events/
├── test/
│   ├── test_groq.py             # Test Groq extraction (qwen/qwen3.8-27b)
│   ├── test_gemini.py           # Test Gemini extraction (gemini-3.5-flash-lite)
│   ├── test_qwen.py             # Test local CPU Hugging Face transformers pipeline
│   └── results/                 # Test run outputs
│       ├── test_results_groq.json
│       ├── test_results_gemini.json
│       └── test_results_qwen.json
├── extract_poster_vlm.py        # Cascaded VLM batch extractor (Groq -> Gemini -> Qwen)
├── frontend/public/posters/     # Poster images (single source, served by the frontend)
└── src/                         # Frontend application
```

---

## Test Scripts

Each backend has a standalone test script located in `test/`:

- **Groq Test**:
  ```bash
  python test/test_groq.py [frontend/public/posters/image2.png]
  ```
  Saves output to `test/results/test_results_groq.json`.

- **Gemini Test**:
  ```bash
  python test/test_gemini.py [frontend/public/posters/image2.png]
  ```
  Saves output to `test/results/test_results_gemini.json`.

- **Local Qwen / Hugging Face Transformers Test**:
  ```bash
  python test/test_qwen.py [frontend/public/posters/image2.png] [--model Qwen/Qwen2-VL-2B-Instruct]
  ```
  Saves output to `test/results/test_results_qwen.json`.

---

## Main Batch Extractor

Run the cascaded extraction pipeline on single posters or whole directories:

```bash
# Automatic fallback cascade (Groq 1st -> Gemini 2nd -> Qwen 3rd)
python extract_poster_vlm.py frontend/public/posters/ --out results.json --csv results.csv

# Force a specific backend
python extract_poster_vlm.py frontend/public/posters/ --backend groq
python extract_poster_vlm.py frontend/public/posters/ --backend gemini
python extract_poster_vlm.py frontend/public/posters/ --backend qwen
```
