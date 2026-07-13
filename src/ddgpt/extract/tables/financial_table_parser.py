from __future__ import annotations

import re

# Each metric requires its own label to actually appear in the row before a
# nearby number is accepted 
AUM_LABEL_RE = re.compile(r"\baum\b|assets under management", re.IGNORECASE)
IRR_LABEL_RE = re.compile(r"\birr\b", re.IGNORECASE)
TVPI_LABEL_RE = re.compile(r"\btvpi\b", re.IGNORECASE)

AUM_VALUE_RE = re.compile(r"\$([0-9\.]+)\s*b", re.IGNORECASE)
PCT_VALUE_RE = re.compile(r"([0-9]+\.[0-9]+)\s*%")
TVPI_VALUE_RE = re.compile(r"([0-9]+\.[0-9]+)\s*x", re.IGNORECASE)


class FinancialTableParser:
    """Pulls headline metrics out of extracted tables.

    Returns evidence-bearing dicts (value/page/table_id/snippet/footnotes)
    rather than bare floats, so table-sourced metrics get the same
    page/snippet provenance as text-sourced ones and aren't exempt from
    evidence verification.
    """

    def parse_metrics(self, tables):
        metrics = {}

        for table in tables:
            for row in table.rows:
                row_text = " ".join(str(v) for v in row.values() if v)

                if "aum" not in metrics and AUM_LABEL_RE.search(row_text):
                    m = AUM_VALUE_RE.search(row_text)
                    if m:
                        metrics["aum"] = self._make_entry(table, row_text, m, float(m.group(1)) * 1e9)

                if "irr" not in metrics and IRR_LABEL_RE.search(row_text):
                    m = PCT_VALUE_RE.search(row_text)
                    if m:
                        metrics["irr"] = self._make_entry(table, row_text, m, float(m.group(1)))

                if "tvpi" not in metrics and TVPI_LABEL_RE.search(row_text):
                    m = TVPI_VALUE_RE.search(row_text)
                    if m:
                        metrics["tvpi"] = self._make_entry(table, row_text, m, float(m.group(1)))

        return metrics

    def _make_entry(self, table, row_text, match, value):
        start = max(0, match.start() - 30)
        end = min(len(row_text), match.end() + 30)
        snippet = re.sub(r"\s+", " ", row_text[start:end]).strip()

        return {
            "value": value,
            "page": table.page,
            "table_id": table.table_id,
            "snippet": snippet,
            "footnotes": list(table.footnotes),
        }
