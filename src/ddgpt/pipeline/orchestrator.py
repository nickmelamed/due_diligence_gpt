from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.extract.postprocess import verify_and_score
from ddgpt.risk.engine import RiskEngine
from ddgpt.copilot.ic_copilot import ICCopilot

class DiligencePipeline:
    def __init__(self, extractors, rules):
        self.extractor = FusionExtractor(extractors)
        self.risk_engine = RiskEngine(rules)
        self.copilot = ICCopilot()

    def run(self, docs):
        extracted = []

        for doc_name, pages in docs:
            doc = self.extractor.extract(doc_name, pages)
            doc = verify_and_score(doc, pages)
            extracted.append(doc.dict())

        flags, risk_score = self.risk_engine.evaluate(extracted)

        ic_memo = self.copilot.generate(extracted, flags)

        return {
            "extracted": extracted,
            "flags": [f.dict() for f in flags],
            "risk_score": risk_score,
            "ic_memo": ic_memo
        }