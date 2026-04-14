import logging
from utils.ocr_utils import run_ocr_multipage
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Minimum chars to consider native PDF text usable
_MIN_TEXT_LEN = 50


def extract_pdf_text(path: str) -> str:
    """
    Extract raw text from ALL pages of a PDF without OCR.
    Returns empty string on failure.
    """
    try:
        doc = fitz.open(path)
        pages_text = []
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            if page_text.strip():
                pages_text.append(page_text)
        doc.close()
        return "\n".join(pages_text)
    except Exception as e:
        logger.warning(f"Native PDF text extraction failed: {e}")
        return ""


def ingest_and_ocr_node(state):
    """
    Node: Ingest file and extract raw text.
    Strategy:
      1. For PDFs → try native text extraction (all pages).
      2. If text is too short (scanned PDF or image) → run multi-page OCR.
      3. For image files → run OCR directly.
    """
    file_path = state.raw_file_path
    if not file_path:
        return {"errors": state.errors + ["No file path provided."]}

    text = ""
    is_pdf = file_path.lower().endswith(".pdf")

    # Step 1: Try native PDF extraction
    if is_pdf:
        text = extract_pdf_text(file_path)
        if text.strip():
            logger.info(f"Native PDF extraction: {len(text)} chars from '{file_path}'")

    # Step 2: Fall back to OCR if text is insufficient
    if len(text.strip()) < _MIN_TEXT_LEN:
        logger.info(f"Falling back to OCR for '{file_path}' (text len={len(text.strip())})")
        try:
            text = run_ocr_multipage(file_path)
            logger.info(f"OCR complete: {len(text)} chars extracted")
        except Exception as e:
            logger.error(f"OCR failed for '{file_path}': {e}")
            return {"errors": state.errors + [f"OCR failed: {str(e)}"]}

    if not text.strip():
        return {"errors": state.errors + ["Could not extract any text from the file. The file may be corrupt or blank."]}

    return {"raw_text": text}
