import logging
import os
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from pytesseract import TesseractNotFoundError

logger = logging.getLogger(__name__)

# Tesseract config for table-heavy medical reports
_TESS_CONFIG = "--oem 3 --psm 6"  # OEM 3 = best LSTM, PSM 6 = uniform block of text


def _ensure_tesseract_installed():
    try:
        custom_cmd = os.getenv("TESSERACT_CMD")
        if custom_cmd:
            pytesseract.pytesseract.tesseract_cmd = custom_cmd
        else:
            default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_win_path):
                pytesseract.pytesseract.tesseract_cmd = default_win_path
        pytesseract.get_tesseract_version()
        return True
    except (TesseractNotFoundError, FileNotFoundError):
        return False


def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    Enhance image quality for OCR on medical report scans:
    - Convert to grayscale
    - Auto-contrast to normalise brightness
    - Sharpen edges (critical for faint table borders & digits)
    - Upscale small images so Tesseract can detect characters reliably
    """
    img = img.convert("L")           # grayscale
    img = ImageOps.autocontrast(img) # normalise brightness
    img = img.filter(ImageFilter.SHARPEN)  # sharpen for thin digits/lines
    # Upscale if any dimension is too small — Tesseract needs ~300 DPI equivalent
    if min(img.size) < 1800:
        scale = 1800 / min(img.size)
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)
    return img


def _pdf_page_to_image(path: str, page_num: int = 0, dpi: int = 300) -> Image.Image:
    """Render a single PDF page to PIL Image at given DPI."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    page = doc.load_page(page_num)
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def _ocr_image(img: Image.Image) -> str:
    """Run Tesseract on a single PIL Image after preprocessing."""
    processed = _preprocess_image(img)
    return pytesseract.image_to_string(processed, config=_TESS_CONFIG)


def run_ocr(path: str) -> str:
    """
    Run OCR on a single-page file (image or first page of PDF).
    Kept for backward compatibility.
    """
    if not _ensure_tesseract_installed():
        raise RuntimeError(
            "Tesseract is not installed or not in PATH. "
            "Install from https://github.com/tesseract-ocr/tesseract"
        )

    if path.lower().endswith(".pdf"):
        img = _pdf_page_to_image(path, page_num=0)
    else:
        img = Image.open(path)

    return _ocr_image(img)


def run_ocr_multipage(path: str) -> str:
    """
    Run OCR on ALL pages of a PDF or a single image file.
    Concatenates text from every page with a page separator.
    This is the preferred function for production use.
    """
    if not _ensure_tesseract_installed():
        raise RuntimeError(
            "Tesseract is not installed or not in PATH. "
            "Install from https://github.com/tesseract-ocr/tesseract"
        )

    if path.lower().endswith(".pdf"):
        import fitz
        doc = fitz.open(path)
        num_pages = len(doc)
        doc.close()
        logger.info(f"OCR: processing {num_pages} page(s) for '{path}'")

        page_texts = []
        for page_num in range(num_pages):
            img = _pdf_page_to_image(path, page_num=page_num, dpi=300)
            text = _ocr_image(img)
            if text.strip():
                page_texts.append(f"[Page {page_num + 1}]\n{text}")
            logger.debug(f"OCR page {page_num + 1}/{num_pages}: {len(text)} chars")

        return "\n\n".join(page_texts)
    else:
        img = Image.open(path)
        return _ocr_image(img)
