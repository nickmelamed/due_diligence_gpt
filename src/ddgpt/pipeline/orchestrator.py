from __future__ import annotations

from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.extract.postprocess import verify_and_score
from ddgpt.risk.engine import RiskEngine
from ddgpt.copilot.ic_copilot import ICCopilot
from ddgpt.copilot.recommendation_engine import determine_recommendation
from ddgpt.config import TrustConfig

class DiligencePipeline:
    def __init__(self, extractors, rules, trust_config: TrustConfig | None = None, redact_before_llm: bool = False,
                 cache_dir: str | None = None, enable_disk_cache: bool = False):
        trust_config = trust_config or TrustConfig()

        self.extractor = FusionExtractor(
            extractors,
            extractor_weights=trust_config.extractor_weights,
            extractor_default_weight=trust_config.extractor_default_weight,
            cache_dir=cache_dir,
            enable_disk_cache=enable_disk_cache,
        )

        self.authority_weights = trust_config.authority_weights
        self.authority_default_weight = trust_config.authority_default_weight
        self.redact_before_llm = redact_before_llm

        self.risk_engine = RiskEngine(rules)

        self.copilot = ICCopilot()

    def run(self, docs):
        extracted = []

        for doc in docs:
            extracted_doc = self.extractor.extract(
                doc.doc_name,
                doc.pages,
                doc.tables,
                doc.layout,
                redact_for_llm=self.redact_before_llm
            )

            extracted_doc = verify_and_score(
                extracted_doc,
                doc.pages,
                authority_weights=self.authority_weights,
                authority_default_weight=self.authority_default_weight
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
            [f.dict() for f in flags],
            recommendation=recommendation
        )

        return {
            "extracted": extracted,
            "flags": [f.dict() for f in flags],
            "risk_score": risk_score,
            "recommendation": recommendation,
            "ic_memo": memo
        }
