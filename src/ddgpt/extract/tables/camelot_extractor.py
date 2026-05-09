from __future__ import annotations

import camelot
import pandas as pd

from pathlib import Path

from ddgpt.extract.tables.table_models import ExtractedTable

class CamelotTableExtractor:
    def extract(self, pdf_path: str):
        tables = camelot.read_pdf(
            pdf_path,
            pages="all",
            flavor="lattice"
        )

        extracted = []

        for idx, table in enumerate(tables):
            df = table.df

            if len(df.columns) == 0:
                continue

            headers = list(df.iloc[0])

            rows = []

            for i in range(1, len(df)):
                row_dict = {}

                for col_idx, header in enumerate(headers):
                    row_dict[str(header)] = str(df.iloc[i, col_idx])

                rows.append(row_dict)

            extracted.append(
                ExtractedTable(
                    table_id=f"table_{idx}",
                    page=table.page,
                    headers=headers,
                    rows=rows,
                    raw_text=df.to_string(),
                    confidence=0.85
                )
            )

        return extracted