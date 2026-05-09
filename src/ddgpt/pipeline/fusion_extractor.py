from __future__ import annotations

from ddgpt.extract.tables.financial_table_parser import FinancialTableParser

EXTRACTOR_WEIGHTS = {
    "RegexExtractor": 0.95,
    "CohereExtractor": 0.70,
}

class FusionExtractor:
    def __init__(self, extractors):
        self.extractors = extractors

        self.table_parser = FinancialTableParser()

    def extract(self, doc_name, pages, tables):
        results = []

        for extractor in self.extractors:
            doc = extractor.extract(doc_name, pages)

            results.append(
                (extractor.__class__.__name__, doc)
            )

        base = self._reconcile(results)

        table_metrics = self.table_parser.parse_metrics(tables)

        if (
            base.aum.value is None and
            "aum" in table_metrics
        ):
            base.aum.value = table_metrics["aum"]
            base.aum.confidence = 0.85

        if (
            base.tvpi.value is None and
            "tvpi" in table_metrics
        ):
            base.tvpi.value = table_metrics["tvpi"]
            base.tvpi.confidence = 0.85

        return base

    def _pick_best_metric(self, metric_name, docs):
        best_score = -1

        best_metric = None

        for extractor_name, doc in docs:
            metric = getattr(doc, metric_name)

            weight = EXTRACTOR_WEIGHTS.get(
                extractor_name,
                0.50
            )

            score = metric.confidence * weight

            if score > best_score:
                best_score = score
                best_metric = metric

        return best_metric

    def _reconcile(self, docs):
        base = docs[0][1]

        base.aum = self._pick_best_metric("aum", docs)

        base.net_irr = self._pick_best_metric("net_irr", docs)

        base.tvpi = self._pick_best_metric("tvpi", docs)

        base.target_irr = self._pick_best_metric("target_irr", docs)

        base.mgmt_fee = self._pick_best_metric("mgmt_fee", docs)

        base.carry = self._pick_best_metric("carry", docs)

        return base