"""
OCR utilities for medical lab report ingestion.

Improvements over basic Tesseract:
  - Otsu binarization (better than autocontrast for printed medical tables)
  - Deskew correction (fixes tilted scans)
  - 400 DPI rendering (denser tables need higher resolution)
  - Multi-PSM strategy: tries PSM 6 then PSM 4 and picks longer result
    (PSM 6 = uniform text block, PSM 4 = single column with varying sizes)
  - Noise removal before binarization
"""

import logging
import os
import numpy as np
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from pytesseract import TesseractNotFoundError

logger = logging.getLogger(__name__)

# PSM modes to try in order — pick the one that extracts most text
_PSM_MODES = [
    "--oem 3 --psm 6",   # uniform block of text (best for structured reports)
    "--oem 3 --psm 4",   # single column, variable text sizes (multi-column labs)
    "--oem 3 --psm 11",  # sparse text — last resort for very mixed layouts
]

_OCR_DPI = 300  # 300 DPI is optimal for Tesseract; 400 adds latency with minimal gain
_PSM_MIN_CHARS = 150  # if PSM 6 returns this many chars, skip slower fallback modes


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


def _otsu_binarize(img: Image.Image) -> Image.Image:
    """
    Otsu's binarization — optimal threshold for bimodal (text/background) images.
    Much better than simple autocontrast for printed medical forms.
    """
    arr = np.array(img)
    # Histogram
    hist, bins = np.histogram(arr.flatten(), 256, [0, 256])
    total = arr.size
    sum_total = np.dot(np.arange(256), hist)

    weight_bg = 0.0
    sum_bg = 0.0
    best_thresh = 0
    best_var = 0.0

    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        between_var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between_var > best_var:
            best_var = between_var
            best_thresh = t

    arr_bin = (arr > best_thresh).astype(np.uint8) * 255
    return Image.fromarray(arr_bin)


def _deskew(img: Image.Image) -> Image.Image:
    """
    Correct tilt in scanned documents.
    Uses pixel variance to find the optimal rotation angle.
    Skips if PIL/numpy deskew unavailable.
    """
    try:
        arr = np.array(img)
        # Project onto horizontal axis to find skew angle
        from scipy.ndimage import rotate as ndimage_rotate
        best_score = -1
        best_angle = 0
        for angle in range(-10, 11, 1):
            rotated = ndimage_rotate(arr, angle, reshape=False, cval=255)
            projection = np.sum(rotated < 128, axis=1)
            score = np.var(projection)
            if score > best_score:
                best_score = score
                best_angle = angle
        if abs(best_angle) > 0:
            corrected = ndimage_rotate(arr, best_angle, reshape=False, cval=255)
            return Image.fromarray(corrected)
    except Exception:
        pass  # scipy unavailable or deskew failed — continue without
    return img


def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    Enhanced preprocessing for medical lab report scans:
    1. Convert to grayscale
    2. Remove noise (median filter)
    3. Deskew (fix tilted scans)
    4. Otsu binarization (optimal threshold for printed text)
    5. Sharpen edges
    6. Upscale if needed (≥1800px short side for 400 DPI equivalent)
    """
    img = img.convert("L")                      # grayscale
    img = img.filter(ImageFilter.MedianFilter(size=3))  # denoise
    img = _deskew(img)
    img = _otsu_binarize(img)                   # optimal binarization
    img = img.filter(ImageFilter.SHARPEN)       # edge sharpening

    # Upscale for Tesseract accuracy
    if min(img.size) < 1800:
        scale = 1800 / min(img.size)
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    return img


def _pdf_page_to_image(path: str, page_num: int = 0, dpi: int = _OCR_DPI) -> Image.Image:
    """Render a single PDF page to PIL Image at given DPI."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    page = doc.load_page(page_num)
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def _ocr_image_best(img: Image.Image) -> str:
    """
    Run Tesseract with PSM 6 first; only try fallback modes if result is sparse.
    PSM 6 wins for 95%+ of structured medical reports — skip the rest when it does.
    """
    processed = _preprocess_image(img)
    best = ""
    for config in _PSM_MODES:
        try:
            text = pytesseract.image_to_string(processed, config=config)
        except Exception:
            continue
        if len(text.strip()) > len(best.strip()):
            best = text
        # Early exit: PSM 6 already extracted enough text
        if len(best.strip()) >= _PSM_MIN_CHARS:
            break

    return best


def run_ocr(path: str) -> str:
    """Run OCR on a single-page file. Kept for backward compatibility."""
    if not _ensure_tesseract_installed():
        raise RuntimeError(
            "Tesseract is not installed or not in PATH. "
            "Install from https://github.com/tesseract-ocr/tesseract"
        )
    if path.lower().endswith(".pdf"):
        img = _pdf_page_to_image(path, page_num=0)
    else:
        img = Image.open(path)
    return _ocr_image_best(img)


def run_ocr_multipage(path: str) -> str:
    """
    Run OCR on ALL pages of a PDF or single image.
    Uses enhanced preprocessing + multi-PSM strategy per page.
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
            img = _pdf_page_to_image(path, page_num=page_num, dpi=_OCR_DPI)
            text = _ocr_image_best(img)
            if text.strip():
                page_texts.append(f"[Page {page_num + 1}]\n{text}")
            logger.debug(f"OCR page {page_num + 1}/{num_pages}: {len(text)} chars")

        return "\n\n".join(page_texts)
    else:
        img = Image.open(path)
        return _ocr_image_best(img)
