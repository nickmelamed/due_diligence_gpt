from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import os

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

@dataclass
class Page:
    page_num: int  # 1-indexed
    text: str

def load_document(path: str) -> Tuple[str, List[Page]]:
    doc_name = os.path.basename(path)
    if path.lower().endswith(".pdf"):
        if PdfReader is None:
            raise RuntimeError("pypdf not installed. pip install -r requirements.txt")
        reader = PdfReader(path)
        pages: List[Page] = []
        for i, p in enumerate(reader.pages):
            pages.append(Page(page_num=i+1, text=(p.extract_text() or "").strip()))
        return doc_name, pages

    if path.lower().endswith(".txt"):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return doc_name, [Page(page_num=1, text=text)]

    raise ValueError(f"Unsupported file type: {path}")
