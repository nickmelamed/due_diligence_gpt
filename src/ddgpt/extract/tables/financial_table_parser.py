from __future__ import annotations

import re

from ddgpt.extract.metric_registry import get as get_metric_def
from ddgpt.extract.metric_registry import normalize_metric_name

# Each metric requires its own label to actually appear in the row before a
# nearby number is accepted
AUM_LABEL_RE = re.compile(r"\baum\b|assets under management", re.IGNORECASE)
IRR_LABEL_RE = re.compile(r"\birr\b", re.IGNORECASE)
TVPI_LABEL_RE = re.compile(r"\btvpi\b", re.IGNORECASE)

AUM_VALUE_RE = re.compile(r"\$([0-9\.]+)\s*b", re.IGNORECASE)
PCT_VALUE_RE = re.compile(r"([0-9]+\.[0-9]+)\s*%")
TVPI_VALUE_RE = re.compile(r"([0-9]+\.[0-9]+)\s*x", re.IGNORECASE)

# Broader than AUM_VALUE_RE (which is B-only, used by the legacy
# parse_metrics() below): GP commitment/fund size/called-distributed capital
# are routinely stated in millions, not just billions, so the open-ended
# path (parse_metrics_open) needs its own USD pattern rather than reusing
# AUM_VALUE_RE and silently missing every $M-denominated row.
_USD_SUFFIX_MULTIPLIER = {"b": 1e9, "m": 1e6, "k": 1e3}
USD_VALUE_RE = re.compile(r"\$([0-9][0-9,\.]*)\s*(b|m|k)?\b", re.IGNORECASE)

# Also broader than PCT_VALUE_RE (decimal-only, used by the legacy
# parse_metrics() below): a whole-number rate like "Carry: 20%" or "Target
# IRR: 18%" is at least as common as a decimal one in these documents.
OPEN_PCT_VALUE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")

# Value-shape patterns for the open-ended fallback path (parse_metrics_open),
# keyed by unit so a registry hit's known unit is tried first and a custom
# row tries each in turn.
_UNIT_VALUE_PATTERNS = {
    "usd": USD_VALUE_RE,
    "percent": OPEN_PCT_VALUE_RE,
    "multiple": TVPI_VALUE_RE,
}


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

    def parse_metrics_open(self, tables) -> list[dict]:
        """Open-ended counterpart to parse_metrics(): one entry per distinct
        metric name found across every table row, not just the three known
        fields -- a row whose label matches the metric registry (see
        ddgpt.extract.metric_registry) uses that metric's known unit; a row
        that doesn't match anything registered is still captured as a
        lower-confidence custom entry (slugified label) rather than
        silently dropped, provided it actually has a $/%/x-shaped value.
        First match per name wins, same dedup convention as parse_metrics().
        """
        entries: list[dict] = []
        seen_names: set[str] = set()

        for table in tables:
            for row in table.rows:
                cells = [str(v) for v in row.values() if v]
                if not cells:
                    continue

                label_text = cells[0]
                row_text = " ".join(cells)

                name, is_custom = normalize_metric_name(label_text)
                if name in seen_names:
                    continue

                metric_def = None if is_custom else get_metric_def(name)
                unit_hint = metric_def.unit if metric_def else None

                value, snippet, unit = self._extract_value(row_text, unit_hint)
                if value is None:
                    continue

                seen_names.add(name)
                entries.append({
                    "name": name,
                    "raw_label": label_text,
                    "unit": unit,
                    "value": value,
                    "confidence": 0.85 if not is_custom else 0.50,
                    "is_custom": is_custom,
                    "page": table.page,
                    "table_id": table.table_id,
                    "snippet": snippet,
                    "footnotes": list(table.footnotes),
                })

        return entries

    def _extract_value(self, row_text, unit_hint):
        units_to_try = [unit_hint] if unit_hint in _UNIT_VALUE_PATTERNS else []
        units_to_try += [u for u in ("usd", "percent", "multiple") if u != unit_hint]

        for unit in units_to_try:
            pattern = _UNIT_VALUE_PATTERNS[unit]
            m = pattern.search(row_text)
            if not m:
                continue
            raw_value = float(m.group(1).replace(",", ""))
            if unit == "usd":
                suffix = (m.group(2) or "").lower()
                value = raw_value * _USD_SUFFIX_MULTIPLIER.get(suffix, 1.0)
            else:
                value = raw_value
            snippet = self._snippet(row_text, m)
            return value, snippet, unit

        return None, "", None

    def _snippet(self, row_text, match):
        start = max(0, match.start() - 30)
        end = min(len(row_text), match.end() + 30)
        return re.sub(r"\s+", " ", row_text[start:end]).strip()

    def _make_entry(self, table, row_text, match, value):
        snippet = self._snippet(row_text, match)

        return {
            "value": value,
            "page": table.page,
            "table_id": table.table_id,
            "snippet": snippet,
            "footnotes": list(table.footnotes),
        }
