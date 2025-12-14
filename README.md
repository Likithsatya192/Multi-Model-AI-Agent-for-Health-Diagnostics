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

### How it works:
1.  **Visual OCR / Text Extraction**: 
    *   We use **PyMuPDF** to extract raw text from digital PDFs.
    *   For images, **Tesseract OCR** scans the pixel data and converts it into a text block.
2.  **LLM Reasoning**:
    *   The raw, messy text is fed into **Llama 3.3 70B** (via Groq).
    *   The LLM is given a strict **Pydantic Schema** (`ExtractionOutput`). It is instructed to look for specific blood parameters (Hemoglobin, WBC, etc.).
    *   **Intelligent Parsing**: The LLM handles synonyms (e.g., "Hgb" -> "Hemoglobin"), unit normalization, and even corrects OCR errors (interpreting "12. 5" as "12.5").
3.  **Structured Output**:
    *   The LLM returns a clean JSON object containing the values, which we then validate against expectation.

---

## 📐 Legacy Logic: Heuristic Extraction
Located in `heuristic/`, this was our original approach.
*   **Method**: Uses `Rapidfuzz` to find parameter names (e.g., fuzzy matching "Neutrophils") and Regular Expressions (`re`) to find the nearest number on the same line.
*   **Pros**: Fast, runs offline, no API cost.
*   **Cons**: Fragile. Fails if the table layout changes or if OCR is noisy.
*   We kept this as a fallback mode (`main.py`) for comparison.

---

## 🌊 Workflow Architecture
The application runs on a **LangGraph** pipeline, where data floats through a series of "Nodes".

```mermaid
graph TD
    Start[User Upload] --> Ingest[Ingest & OCR Node]
    Ingest --> Extract[Extract Parameters (LLM/Heuristic)]
    
    Extract --> Validate[Validate & Standardize Node]
    Validate --> Interpret[Model 1: Range Interpretation]
    
    Interpret --> Pattern[Model 2: Pattern Recognition]
    Pattern --> Context[Model 3: Context Analysis]
    
    Context --> Synthesis[Synthesis Engine]
    Synthesis --> Recs[Recommendations Engine]
    
    Recs --> End[Final Report & UI Display]
```

### The Pipeline Steps:
1.  **Ingest & OCR**: Convert file to text.
2.  **Validation**: Check extracting numbers against known Reference Ranges (Low/Normal/High).
3.  **Pattern Recognition**: AI looks at all values together to find syndromes (e.g., Low Hb + Low MCV = Microcytic Anemia).
4.  **Context Analysis**: AI considers age/gender (e.g., "13 Hb is normal for a man, but excellent for a pregnant woman").
5.  **Synthesis**: Combines all logical findings into a coherent narrative.
6.  **Recommendations**: Generates dietary and lifestyle tips.

---

## 📂 Project File Guide
Here is exactly how every file contributes to the project:

### 1. Root Directory
*   **`app.py`**: The **Main Application**. Runs the **AI (LLM)** version. Handles UI, File Uploads, and displaying the modern Dashboard.
*   **`main.py`**: The **Heuristic Application**. Runs the **Legacy (Regex)** version. Useful for testing the old extraction method.
*   **`requirements.txt`**: List of all Python libraries needed (`streamlit`, `langchain`, `fastapi`, etc.).

### 2. `nodes/` (The Brain)
These files are the processing stations of our graph.
*   **`ingest_and_ocr.py`**: Handles reading PDFs and running Tesseract on images.
*   **`extract_parameters.py`**: **(CRITICAL)** The LLM Worker. Sends text to Groq/Llama and gets structured JSON back.
*   **`validate_standardize.py`**: Cleans data and checks it against `reference_ranges.json`.
*   **`model1_interpretation.py`**: Tags values as Low, Normal, or High.
*   **`model2_patterns.py`**: AI Agent that looks for disease patterns in the extracted data.
*   **`model3_context.py`**: AI Agent that adjusts interpretation based on Patient Age & Gender.
*   **`synthesis.py`**: AI Agent that writes the final summary report, signed by "Likith Sagar".
*   **`recommendations.py`**: AI Agent that suggests health tips based on the report.
*   **(Deletions)**: We removed `mapping.py` etc., as their logic was absorbed by the LLM.

### 3. `app/` (The Application Logic)
*   **`graph_state.py`**: Defines the data object (`ReportState`) that is passed between nodes. It's like the "memory" of the pipeline.
*   **`graph_builder.py`**: Connects the `nodes` together into the Flowchart/Graph shown above (for the LLM App).
*   **`run_pipeline.py`**: The trigger function that starts the graph execution.

### 4. `heuristic/` (The Legacy Logic)
*   **`extract_parameters_heuristic.py`**: The old Regex/Fuzzy match extraction logic.
*   **`graph_builder_heuristic.py`**: Builds a graph using the *heuristic* node instead of the *LLM* node.
*   **`run_pipeline_heuristic.py`**: Runner for the heuristic app.

### 5. `utils/` (Helpers)
*   **`llm_utils.py`**: Sets up the connection to Groq (`llama-3.3-70b-versatile`).
*   **`ocr_utils.py`**: Image pre-processing (grayscale, contrast) to make Tesseract accuracy higher.
*   **`reference_ranges.py`**: Loader for the JSON database of normal blood levels.

### 6. `configs/`
*   **`reference_ranges.json`**: The database of medical knowledge. Contains low/high limits for Men, Women, and Children for every extracted parameter.

---
**Developed by Likith Sagar & Team**
*Senior Medical Consultant AI Project*
