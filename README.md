# Chennai Event Map - Poster Field Extraction

Vision-Language Model (VLM) powered event field extraction for Chennai event posters.

## Fallback Cascade Order
1. **Primary**: **Groq API**
   - Candidate models: `meta-llama/llama-4-scout-17b-16e-instruct` -> `qwen/qwen3.8-27b` (fast, free tier, high throughput)
2. **First Backup**: **Google Gemini**
   - Model: `gemini-3.5-flash-lite` (free-tier friendly, fast, cheap)
3. **Last Order**: **Local Hugging Face Transformers (CPU friendly)**
   - Model: `Qwen/Qwen2-VL-2B-Instruct` (no API cost, runs locally via `transformers.pipeline("image-text-to-text")`)

---

## Test Scripts

Each backend has its own standalone test script:

- **Groq Test**:
  ```bash
  python test_groq.py [path_to_poster.png]
  ```
- **Gemini Test**:
  ```bash
  python test_gemini.py [path_to_poster.png]
  ```
- **Local Qwen / Hugging Face Transformers Test**:
  ```bash
  python test_qwen.py [path_to_poster.png] [--model Qwen/Qwen2-VL-2B-Instruct]
  ```

---

## Main Batch Extractor

Run the cascaded extraction pipeline on single posters or whole directories:

```bash
# Automatic fallback cascade (Groq -> Gemini -> Qwen)
python extract_poster_vlm.py posters/ --out results.json --csv results.csv

# Force a specific backend
python extract_poster_vlm.py posters/ --backend groq
python extract_poster_vlm.py posters/ --backend gemini
python extract_poster_vlm.py posters/ --backend qwen
```
