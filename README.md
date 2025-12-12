## AI-Powered CBC Analyzer

Streamlit app that ingests CBC lab reports (PDF or image), performs OCR, extracts key hematology parameters, validates them against configured reference ranges, interprets them (normal / low / high), and presents the results in interactive tables with CSV export and basic charts.

### Features
- Upload PDF or common image formats.
- Automatic OCR (Tesseract) with image enhancement (grayscale, autocontrast, upscale).
- Robust parameter extraction with fuzzy matching and comma-aware number parsing.
- Reference-range validation and simple interpretation.
- Coverage indicator to show how many expected parameters were captured.
- CSV download of extracted parameters and quick bar chart visualization.

### Quickstart
1) Install system Tesseract (required for OCR):
   - Windows (example): `winget install -e --id UB-Mannheim.Tesseract-OCR`
   - If needed, set the executable path:
     - PowerShell (current session):  
       `$env:TESSERACT_CMD = 'C:\Program Files\Tesseract-OCR\tesseract.exe'`
     - Persist (PowerShell/CMD):  
       `setx TESSERACT_CMD "C:\Program Files\Tesseract-OCR\tesseract.exe"`
2) Create/activate a virtual environment.
3) Install Python deps: `pip install -r requirements.txt`
4) Run the app: `streamlit run app.py`
5) Upload a CBC report (PDF or image). Review the extracted table, validation, interpretation, and download CSV if needed.

### How the pipeline works (step by step)
1. **Ingest & OCR (`nodes/ingest_and_ocr.py`)**
   - Tries direct text extraction for PDFs.
   - Falls back to OCR via Tesseract with image preprocessing in `utils/ocr_utils.py` (grayscale, autocontrast, upscaling). PDF pages are rasterized at 300 DPI before OCR.
   - If Tesseract is missing, a clear error is surfaced.
2. **Parameter Extraction (`nodes/extract_parameters.py`)**
   - Splits text by lines, cleans punctuation, and fuzzy-matches lines against canonical CBC parameters and synonyms.
   - Parses numbers with commas (e.g., `10,000`), picks the first numeric token as the result value.
   - Applies scale heuristics for RBC (divide large values by 100) and platelets (multiply small values by 1000) and sets default units.
3. **Validation & Standardization (`nodes/validate_standardize.py`)**
   - Loads reference ranges from `configs/reference_ranges.json`.
   - Ensures values exist and parameter is configured; attaches unit and reference bounds.
4. **Interpretation (`nodes/model1_interpretation.py`)**
   - Classifies each validated value as low / normal / high based on the reference range.
5. **UI Rendering (`app.py`)**
   - Shows coverage (`captured / expected`) and warns if under 50%.
   - Displays extracted, validated, and interpreted tables.
   - Offers CSV download of extracted parameters.
   - Renders a simple bar chart of extracted numeric values.

### Key files
- `app.py` — Streamlit UI and user flow.
- `app/run_pipeline.py` — Runs the LangGraph pipeline and normalizes state.
- `app/graph_builder.py` — Defines pipeline DAG (ingest → extract → validate → interpret).
- `app/graph_state.py` — Shared state model.
- `nodes/ingest_and_ocr.py` — File ingest and OCR fallback.
- `nodes/extract_parameters.py` — Parsing and fuzzy matching of CBC parameters.
- `nodes/validate_standardize.py` — Reference checks and unit handling.
- `nodes/model1_interpretation.py` — Low/normal/high tagging.
- `utils/ocr_utils.py` — OCR preprocessing and Tesseract setup (env/auto path).
- `configs/reference_ranges.json` — Reference ranges and units for parameters.

### Notes and tips
- Prefer clear, high-resolution scans or the original PDF for best OCR results.
- If coverage is low, try rescanning with better contrast/lighting or a higher DPI.
- You can extend `configs/reference_ranges.json` to support additional parameters.
- If Tesseract is installed in a non-default path, set `TESSERACT_CMD` accordingly.
# Health AI Project

Starter repository scaffold for a medical lab-result ingestion and interpretation pipeline.

## Structure

- `app/` — pipeline entry and state definitions
- `nodes/` — modular processing nodes (OCR, extraction, cleaning, model interpretation)
- `utils/` — helpers for PDF/OCR, mapping, unit conversions
- `configs/` — sample JSON configs and LLM settings
- `tests/` — minimal pytest smoke tests

## Quick Start

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run tests:

```bash
pytest -q
```
