from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from ddgpt.provenance.evidence import Evidence

class Metric(BaseModel):
    value: Optional[float] = None
    confidence: float = 0.0
    evidence: Evidence = Field(default_factory=lambda: Evidence(doc_name="", page=None, snippet=""))

class FeeMetric(BaseModel):
    value: Optional[float] = None
    basis: Optional[str] = None
    confidence: float = 0.0
    evidence: Evidence = Field(default_factory=lambda: Evidence(doc_name="", page=None, snippet=""))

class CarryMetric(BaseModel):
    value: Optional[float] = None
    hurdle: Optional[float] = None
    confidence: float = 0.0
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
