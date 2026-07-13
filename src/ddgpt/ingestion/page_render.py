from __future__ import annotations

from typing import Dict, List, Optional

import fitz

DEFAULT_RENDER_DPI = 200


def render_pages_png(path: str, dpi: int = DEFAULT_RENDER_DPI, page_numbers: Optional[List[int]] = None) -> Dict[int, bytes]:
    """Rasterize PDF pages to PNG bytes, keyed by 1-indexed page number.

    Reuses the same fitz pixmap technique as ocr_page_image, but returns the
    raw image instead of running OCR on it -- for feeding a vision-capable
    model rather than Tesseract.
    """
    doc = fitz.open(path)
    try:
        wanted = set(page_numbers) if page_numbers is not None else None
        images: Dict[int, bytes] = {}

        for i, page in enumerate(doc):
            page_num = i + 1
            if wanted is not None and page_num not in wanted:
                continue
            pix = page.get_pixmap(dpi=dpi)
            images[page_num] = pix.tobytes("png")

        return images
    finally:
        doc.close()
