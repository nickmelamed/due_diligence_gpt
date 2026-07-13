from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from ddgpt.provenance.evidence import Evidence

class DefinitionContext(BaseModel):
    basis: Optional[str] = None  # "net" or "gross"
    snippet: str = ""
    page: Optional[int] = None
    section: Optional[str] = None

class Metric(BaseModel):
    value: Optional[float] = None
    confidence: float = 0.0
    agreement: float = 1.0  # cross-extractor agreement for this field; 1.0 = only one extractor produced a value
    evidence: Evidence = Field(default_factory=lambda: Evidence(doc_name="", page=None, snippet=""))

class FeeMetric(BaseModel):
    value: Optional[float] = None
    basis: Optional[str] = None
    confidence: float = 0.0
    agreement: float = 1.0
    evidence: Evidence = Field(default_factory=lambda: Evidence(doc_name="", page=None, snippet=""))

class CarryMetric(BaseModel):
    value: Optional[float] = None
    hurdle: Optional[float] = None
    confidence: float = 0.0
    agreement: float = 1.0
    evidence: Evidence = Field(default_factory=lambda: Evidence(doc_name="", page=None, snippet=""))

class ExtractedDoc(BaseModel):
    doc_name: str
    doc_date: Optional[str] = None

    aum: Metric = Field(default_factory=Metric)          # USD absolute
    net_irr: Metric = Field(default_factory=Metric)      # percent
    tvpi: Metric = Field(default_factory=Metric)         # multiple
    target_irr: Metric = Field(default_factory=Metric)   # percent

    mgmt_fee: FeeMetric = Field(default_factory=FeeMetric)
    carry: CarryMetric = Field(default_factory=CarryMetric)

    notes: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)

    # Layout-derived context (see ddgpt.layout)
    net_irr_basis: Optional[DefinitionContext] = None
    sections_detected: List[str] = Field(default_factory=list)

    # Every IRR-shaped percentage mention found anywhere in the document
    # text (see ddgpt.layout.irr_mentions), not just the ones that made it
    # into target_irr/net_irr -- lets a rule catch a secondary claim stated
    # once in prose that conflicts with what got structurally extracted.
    irr_mentions: List[dict] = Field(default_factory=list)

    # Populated when two extractors produce materially different values for
    # the same field; distinct from cross-document NumericMismatchRule flags.
    extractor_disagreements: List[dict] = Field(default_factory=list)

    # Full reproducibility trail: every candidate value each extractor (and,
    # if used, the table parser) produced per field -- not just the winner,
    # and not just the cases where they disagreed. Powers the "under the
    # hood" audit view; each entry is
    # {extractor, value, confidence, weight, score, evidence, winner}.
    extraction_candidates: Dict[str, List[dict]] = Field(default_factory=dict)
