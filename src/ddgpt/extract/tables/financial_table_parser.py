from __future__ import annotations

import re

class FinancialTableParser:
    def parse_metrics(self, tables):
        metrics = {}

        for table in tables:
            raw = table.raw_text.lower()

            # AUM
            aum_match = re.search(
                r"\$([0-9\.]+)\s*b",
                raw
            )

            if aum_match:
                metrics["aum"] = float(aum_match.group(1)) * 1e9

            # IRR
            irr_match = re.search(
                r"([0-9]+\.[0-9]+)\%",
                raw
            )

            if irr_match:
                metrics["irr"] = float(irr_match.group(1))

            # TVPI
            tvpi_match = re.search(
                r"([0-9]+\.[0-9]+)x",
                raw
            )

            if tvpi_match:
                metrics["tvpi"] = float(tvpi_match.group(1))

        return metrics