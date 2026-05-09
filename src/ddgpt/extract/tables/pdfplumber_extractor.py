from __future__ import annotations

import pdfplumber

from ddgpt.extract.tables.table_models import ExtractedTable

class PDFPlumberTableExtractor:
    def extract(self, pdf_path: str):
        extracted = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()

                for t_idx, table in enumerate(tables):
                    if not table:
                        continue

                    headers = table[0]

                    rows = []

                    for row in table[1:]:
                        row_dict = {}

                        for i, h in enumerate(headers):
                            row_dict[str(h)] = str(row[i])

                        rows.append(row_dict)

                    extracted.append(
                        ExtractedTable(
                            table_id=f"pdfplumber_{page_idx}_{t_idx}",
                            page=page_idx + 1,
                            headers=headers,
                            rows=rows,
                            raw_text=str(table),
                            confidence=0.75
                        )
                    )

        return extracted