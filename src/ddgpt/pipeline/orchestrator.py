from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.extract.postprocess import verify_and_score
from ddgpt.risk.engine import RiskEngine
from ddgpt.copilot.ic_copilot import ICCopilot
from ddgpt.copilot.recommendation_engine import determine_recommendation

class DiligencePipeline:
    def __init__(self, extractors, rules):
        self.extractor = FusionExtractor(extractors)

        self.risk_engine = RiskEngine(rules)

        self.copilot = ICCopilot()

    def run(self, docs):
        extracted = []

        for doc in docs:
            extracted_doc = self.extractor.extract(
                doc.doc_name,
                doc.pages,
                doc.tables
            )

            extracted_doc = verify_and_score(
                extracted_doc,
                doc.pages
            )

            extracted.append(
                extracted_doc.dict()
            )

        flags, risk_score = self.risk_engine.evaluate(extracted)

        recommendation = determine_recommendation(
            [f.dict() for f in flags]
        )

        memo = self.copilot.generate(
            extracted,
            [f.dict() for f in flags]
        )

        return {
            "extracted": extracted,
            "flags": [f.dict() for f in flags],
            "risk_score": risk_score,
            "recommendation": recommendation,
            "ic_memo": memo
        }