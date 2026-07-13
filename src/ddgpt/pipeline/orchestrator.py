from __future__ import annotations

import logging
import time

from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.extract.postprocess import verify_and_score
from ddgpt.risk.engine import RiskEngine
from ddgpt.copilot.ic_copilot import ICCopilot
from ddgpt.copilot.recommendation_engine import determine_recommendation
from ddgpt.config import TrustConfig

logger = logging.getLogger("ddgpt")

class DiligencePipeline:
    def __init__(self, extractors, rules, trust_config: TrustConfig | None = None, redact_before_llm: bool = False,
                 cache_dir: str | None = None, enable_disk_cache: bool = False, chart_extractor=None):
        trust_config = trust_config or TrustConfig()

        self.extractor = FusionExtractor(
            extractors,
            extractor_weights=trust_config.extractor_weights,
            extractor_default_weight=trust_config.extractor_default_weight,
            cache_dir=cache_dir,
            enable_disk_cache=enable_disk_cache,
            chart_extractor=chart_extractor,
        )

        self.authority_weights = trust_config.authority_weights
        self.authority_default_weight = trust_config.authority_default_weight
        self.redact_before_llm = redact_before_llm

        self.risk_engine = RiskEngine(rules)

        self.copilot = ICCopilot()

    def run(self, docs):
        timings = {"per_document_s": {}}
        run_start = time.perf_counter()

        extracted = []

        for doc in docs:
            doc_start = time.perf_counter()

            extracted_doc = self.extractor.extract(
                doc.doc_name,
                doc.pages,
                doc.tables,
                doc.layout,
                redact_for_llm=self.redact_before_llm,
                path=doc.path,
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

            doc_duration = time.perf_counter() - doc_start
            timings["per_document_s"][doc.doc_name] = round(doc_duration, 3)
            logger.info(f"stage=extraction doc={doc.doc_name} duration_s={doc_duration:.3f}")

        timings["extraction_total_s"] = round(sum(timings["per_document_s"].values()), 3)

        t0 = time.perf_counter()
        flags, risk_score = self.risk_engine.evaluate(extracted)
        timings["risk_rules_s"] = round(time.perf_counter() - t0, 3)
        logger.info(f"stage=risk_rules duration_s={timings['risk_rules_s']:.3f} flags={len(flags)} risk_score={risk_score:.3f}")

        recommendation = determine_recommendation(
            [f.dict() for f in flags]
        )

        t1 = time.perf_counter()
        memo = self.copilot.generate(
            extracted,
            [f.dict() for f in flags],
            recommendation=recommendation
        )
        timings["memo_generation_s"] = round(time.perf_counter() - t1, 3)
        logger.info(f"stage=memo_generation duration_s={timings['memo_generation_s']:.3f}")

        timings["total_s"] = round(time.perf_counter() - run_start, 3)

        return {
            "extracted": extracted,
            "flags": [f.dict() for f in flags],
            "risk_score": risk_score,
            "recommendation": recommendation,
            "ic_memo": memo,
            "timings": timings
        }
