from __future__ import annotations

from ddgpt.extract.tables.camelot_extractor import CamelotTableExtractor
from ddgpt.extract.tables.pdfplumber_extractor import PDFPlumberTableExtractor

class EnsembleTableExtractor:
    def __init__(self):
        self.extractors = [
            CamelotTableExtractor(),
            PDFPlumberTableExtractor()
        ]

    def extract(self, pdf_path: str):
        all_tables = []

        for extractor in self.extractors:
            try:
                tables = extractor.extract(pdf_path)

                all_tables.extend(tables)

            except Exception as e:
                print(f"table extractor failed: {e}")

        return all_tables