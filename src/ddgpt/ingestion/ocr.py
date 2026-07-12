from __future__ import annotations

import fitz
import pytesseract
from PIL import Image
import io

DEFAULT_OCR_DPI = 300


def ocr_page_image(page, dpi: int = DEFAULT_OCR_DPI) -> str:
    """OCR a single already-open fitz page object; returns extracted text."""
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def ocr_pdf(path: str, dpi: int = DEFAULT_OCR_DPI):
    """OCR every page of a PDF from scratch. Returns a list of (page_num, text)."""
    doc = fitz.open(path)
    try:
        return [(i + 1, ocr_page_image(page, dpi=dpi)) for i, page in enumerate(doc)]
    finally:
        doc.close()
