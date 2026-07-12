from __future__ import annotations
from typing import List
from ddgpt.rules.base import Rule, Flag


class ExtractorDisagreementRule(Rule):
    """Surfaces cases where the regex and LLM extractors actively contradicted
    each other on a field within one document, as opposed to merely differing
    in confidence (which fusion silently resolves via weighted scoring).

    Distinct from NumericMismatchRule, which flags disagreement *across*
    documents -- this flags disagreement *within* a single document's
    extraction, before reconciliation picked a winner.
    """

    def apply(self, extracted: List[dict]) -> List[Flag]:
        flags: List[Flag] = []

        for doc in extracted:
            for disagreement in doc.get("extractor_disagreements", []):
                values_desc = ", ".join(
                    f"{extractor}={value}" for extractor, value in disagreement["values"].items()
                )

                flags.append(Flag(
                    severity="YELLOW",
                    type="EXTRACTOR_DISAGREEMENT",
                    docs=doc["doc_name"],
                    detail=(
                        f'Extractors disagree on {disagreement["field"]}: {values_desc} '
                        f'(agreement={disagreement["agreement"]:.2f})'
                    ),
                    evidence=values_desc,
                    why_it_matters=(
                        "Regex and LLM extraction produced materially different values for the same "
                        "field within one document; fusion selected a single winner by confidence "
                        "weighting, but the discarded value may have been correct."
                    ),
                    question_to_ask=(
                        f'Manually confirm the correct {disagreement["field"]} value from the source '
                        f'document {doc["doc_name"]}.'
                    )
                ))

        return flags
