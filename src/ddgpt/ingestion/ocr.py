from __future__ import annotations

import fitz
import pytesseract
from PIL import Image
import io

from ddgpt.io.loaders import Page

def ocr_pdf(path: str):
    doc = fitz.open(path)

    pages = []

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)

        img = Image.open(io.BytesIO(pix.tobytes("png")))

        text = pytesseract.image_to_string(img)

        pages.append(
            Page(
                page_num=i + 1,
                text=text
            )
        )

    return pages