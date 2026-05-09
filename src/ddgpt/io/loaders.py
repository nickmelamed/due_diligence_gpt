from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel
import fitz

from ddgpt.extract.tables.ensemble_tables import EnsembleTableExtractor

class Page(BaseModel):
    page_num: int
    text: str

class LoadedDocument(BaseModel):
    doc_name: str

    path: str

    pages: list[Page]

    tables: list = []

def load_document(path: str):
    ext = Path(path).suffix.lower()

    if ext != ".pdf":
        raise ValueError("Only PDFs supported")

    doc = fitz.open(path)

    pages = []

    for i, page in enumerate(doc):
        pages.append(
            Page(
                page_num=i + 1,
                text=page.get_text("text")
            )
        )

    table_extractor = EnsembleTableExtractor()

    tables = table_extractor.extract(path)

    return LoadedDocument(
        doc_name=Path(path).name,
        path=path,
        pages=pages,
        tables=tables
    )