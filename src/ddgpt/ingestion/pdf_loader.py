from __future__ import annotations

import fitz
from pathlib import Path
from ddgpt.io.loaders import Page

def load_pdf(path: str):
    doc = fitz.open(path)

    pages = []

    for i, page in enumerate(doc):
        text = page.get_text("text")

        pages.append(
            Page(
                page_num=i + 1,
                text=text
            )
        )

    return Path(path).name, pages