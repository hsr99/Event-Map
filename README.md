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

---

## Data & Backend (Supabase)

Supabase is the single source of truth: events live in Postgres and posters in a Storage bucket.

```
Visitor's browser ──(anon key, read-only: published events)──▶ Supabase
        │
        └──▶ FastAPI backend ──(service-role key: all writes)──▶ Supabase
              /api/extract   read a poster with the vision models
              /api/submit    save an event as "review" + upload its poster
              /api/reports   flag an event
```

- Visitors can only **read published events**. They can't write to the database or upload files directly.
- Every submission starts as **`review`** and only appears on the site after you approve it.
- Private intake details (submitter contact, raw model output, poster hash) are kept in the `submissions` table, which visitors can never read.
- `frontend/src/data/events.js` is a bundled **fallback snapshot**. It's shown on first paint and whenever Supabase is unreachable.

### One-time setup

1. Create a free project at [supabase.com](https://supabase.com).
2. In the dashboard, open **SQL Editor**, paste `supabase_schema.sql` and run it.
3. Copy `.env.example` to `.env` (repo root) and fill in the values from **Project Settings → API**:
   - `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`: public, used by the browser
   - `SUPABASE_SERVICE_ROLE_KEY`: **secret**, backend only. Never prefix it with `VITE_`.
4. Install the backend dependencies and move the existing events and posters in:
   ```bash
   pip install -r backend/requirements.txt
   python tools/migrate_to_supabase.py
   ```

### Day to day

```bash
uvicorn backend.main:app --reload --port 8000    # API (from the repo root)
cd frontend && npm run dev                       # site

python tools/ingest_posters.py                   # new posters in frontend/public/posters/ -> events
python tools/review_events.py                    # see what's waiting for review
python tools/review_events.py approve 12 15      # publish
python tools/review_events.py hide 13            # reject / take down
python tools/export_snapshot.py                  # refresh the bundled fallback from Supabase
```
