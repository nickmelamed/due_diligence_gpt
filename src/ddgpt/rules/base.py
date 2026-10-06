from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel

class Flag(BaseModel):
    severity: str
    type: str
    docs: str
    detail: str
    evidence: str
    why_it_matters: str
    question_to_ask: str
    # Canonical/custom metric name this flag is about, e.g. "aum", "dpi",
    # "portfolio_company_count" -- populated by rules that operate on a
    # specific metric (NumericMismatchRule); empty for rules that aren't
    # about one specific metric (e.g. ExtractorDisagreementRule spans
    # whichever field disagreed, DefinitionDriftRule is about a convention,
    # not a single value). Confirmed safe to add: recommendation_engine.py's
    # determine_recommendation() only reads `severity`, never `type` or this
    # field, so nothing downstream depends on Flag's exact shape today.
    metric: str = ""

class Rule(ABC):
    @abstractmethod
    def apply(self, extracted: List[dict]) -> List[Flag]:
        raise NotImplementedError
