from __future__ import annotations

from ddgpt.extract.tables.camelot_extractor import CamelotTableExtractor
from ddgpt.extract.tables.pdfplumber_extractor import PDFPlumberTableExtractor

class EnsembleTableExtractor:
    def __init__(self):
        self.extractors = [
            CamelotTableExtractor(),
            PDFPlumberTableExtractor()
        ]
        self.cache = {}

    def extract(self, pdf_path: str):
        if pdf_path in self.cache:
            return self.cache[pdf_path]
        
        all_tables = []

        for extractor in self.extractors:
            try:
                tables = extractor.extract(pdf_path)

                all_tables.extend(tables)

            except Exception as e:
                print(f"table extractor failed: {e}")
        
        self.cache[pdf_path] = all_tables

        return all_tables