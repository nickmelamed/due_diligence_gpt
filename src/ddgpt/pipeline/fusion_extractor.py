from typing import List
from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.extract.postprocess import authority_weight

class FusionExtractor:
    def __init__(self, extractors):
        self.extractors = extractors

    def extract(self, doc_name, pages) -> ExtractedDoc:
        results = [e.extract(doc_name, pages) for e in self.extractors]
        return self._reconcile(results)

    def _reconcile(self, docs: List[ExtractedDoc]) -> ExtractedDoc:
        base = docs[0]

        def pick_best(metric_name):
            candidates = [getattr(d, metric_name) for d in docs]
            best = max(
                candidates,
                key=lambda m: m.confidence
            )
            return best

        # reconcile fields
        base.aum = pick_best("aum")
        base.net_irr = pick_best("net_irr")
        base.tvpi = pick_best("tvpi")
        base.target_irr = pick_best("target_irr")
        base.mgmt_fee = pick_best("mgmt_fee")
        base.carry = pick_best("carry")

        return base