from __future__ import annotations

import logging
from pathlib import Path
from pydantic import BaseModel, Field
import fitz

from ddgpt.extract.tables.ensemble_tables import EnsembleTableExtractor
from ddgpt.ingestion.ocr import ocr_page_image
from ddgpt.layout.models import DocumentLayout
from ddgpt.layout.section_parser import parse_sections, parse_sections_from_text
from ddgpt.layout.footnote_linker import attach_footnotes_to_tables

# pdfminer (used internally by pdfplumber/Camelot for table extraction) logs
# a routine, harmless notice at WARNING level whenever a PDF page omits an
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# A page whose native text layer is shorter than this is treated as a
# scanned/image page and re-read via OCR instead of silently kept as
# (near-)empty text.
MIN_TEXT_LAYER_CHARS = 20


class Page(BaseModel):
    page_num: int
    text: str


class LoadedDocument(BaseModel):
    doc_name: str

    path: str

    pages: list[Page]

    tables: list = []

    layout: DocumentLayout = Field(default_factory=DocumentLayout)


def load_document(path: str, ocr_enabled: bool = True, ocr_dpi: int = 300) -> LoadedDocument:
    ext = Path(path).suffix.lower()

    if ext == ".txt":
        return _load_text_document(path)

    if ext != ".pdf":
        raise ValueError(f"Unsupported file type: {ext} (supported: .pdf, .txt)")

    return _load_pdf_document(path, ocr_enabled=ocr_enabled, ocr_dpi=ocr_dpi)


def _load_text_document(path: str) -> LoadedDocument:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    sections, footnotes = parse_sections_from_text(text, page_num=1)

    return LoadedDocument(
        doc_name=Path(path).name,
        path=path,
        pages=[Page(page_num=1, text=text)],
        tables=[],
        layout=DocumentLayout(sections=sections, footnotes=footnotes),
    )


def _load_pdf_document(path: str, ocr_enabled: bool = True, ocr_dpi: int = 300) -> LoadedDocument:
    doc = fitz.open(path)

    pages = []

    for i, page in enumerate(doc):
        text = page.get_text("text")

        if ocr_enabled and len(text.strip()) < MIN_TEXT_LAYER_CHARS:
            ocr_text = ocr_page_image(page, dpi=ocr_dpi)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text

        pages.append(
            Page(
                page_num=i + 1,
                text=text
            )
        )

    sections, footnotes = parse_sections(doc)

    doc.close()

    table_extractor = EnsembleTableExtractor()

    tables = table_extractor.extract(path)
    tables = attach_footnotes_to_tables(tables, footnotes)

    return LoadedDocument(
        doc_name=Path(path).name,
        path=path,
        pages=pages,
        tables=tables,
        layout=DocumentLayout(sections=sections, footnotes=footnotes),
    )
