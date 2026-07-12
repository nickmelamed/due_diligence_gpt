from __future__ import annotations

import re


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
            raw = table.raw_text.lower()

            aum_match = re.search(r"\$([0-9\.]+)\s*b", raw)
            if aum_match and "aum" not in metrics:
                metrics["aum"] = self._make_entry(table, aum_match, float(aum_match.group(1)) * 1e9)

            irr_match = re.search(r"([0-9]+\.[0-9]+)\%", raw)
            if irr_match and "irr" not in metrics:
                metrics["irr"] = self._make_entry(table, irr_match, float(irr_match.group(1)))

            tvpi_match = re.search(r"([0-9]+\.[0-9]+)x", raw)
            if tvpi_match and "tvpi" not in metrics:
                metrics["tvpi"] = self._make_entry(table, tvpi_match, float(tvpi_match.group(1)))

        return metrics

    def _make_entry(self, table, match, value):
        start = max(0, match.start() - 30)
        end = min(len(table.raw_text), match.end() + 30)
        snippet = re.sub(r"\s+", " ", table.raw_text[start:end]).strip()

        return {
            "value": value,
            "page": table.page,
            "table_id": table.table_id,
            "snippet": snippet,
            "footnotes": list(table.footnotes),
        }
