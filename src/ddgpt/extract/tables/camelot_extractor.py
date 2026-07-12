from __future__ import annotations

import camelot
import pandas as pd

from pathlib import Path

from ddgpt.extract.tables.table_models import ExtractedTable

# "lattice" finds ruled/bordered tables; many real fund reports use
# borderless tables (whitespace-aligned columns), which lattice simply
# returns nothing for. Falling back to "stream" catches those instead of
# silently producing no tables at all.
FLAVOR_CONFIDENCE = {
    "lattice": 0.85,
    "stream": 0.65,
}

class CamelotTableExtractor:
    def extract(self, pdf_path: str):
        for flavor in ("lattice", "stream"):
            extracted = self._extract_with_flavor(pdf_path, flavor)
            if extracted:
                return extracted

        return []

    def _extract_with_flavor(self, pdf_path: str, flavor: str):
        try:
            tables = camelot.read_pdf(
                pdf_path,
                pages="all",
                flavor=flavor
            )
        except Exception as e:
            print(f"camelot ({flavor}) failed: {e}")
            return []

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
                    table_id=f"{flavor}_{idx}",
                    page=table.page,
                    headers=headers,
                    rows=rows,
                    raw_text=df.to_string(),
                    confidence=FLAVOR_CONFIDENCE[flavor]
                )
            )

        return extracted
