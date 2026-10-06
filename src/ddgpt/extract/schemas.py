from __future__ import annotations
import hashlib
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Sequence, Type
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

class MetricEntry(BaseModel):
    """One financial metric found in a document -- the open-ended
    replacement for the fixed six named fields below (aum/net_irr/tvpi/
    target_irr/mgmt_fee/carry). `name` is either a metric_registry canonical
    name (is_custom=False) or a slugified version of whatever label the
    extractor found (is_custom=True) -- see
    ddgpt.extract.metric_registry.normalize_metric_name. Additive alongside
    the legacy fields until those get retired in favor of this list."""
    name: str
    raw_label: str = ""
    unit: str = "other"  # "usd" | "percent" | "multiple" | "count" | "year" | "other"
    value: Optional[float] = None
    basis: Optional[str] = None  # optional qualifier: net/gross, fee basis, etc.
    confidence: float = 0.0
    agreement: float = 1.0
    is_custom: bool = False
    # True when this entry's value only came from a second extraction
    # attempt (see llm_common.extract_with_evidence_retry) -- the first
    # attempt had at least one registry-recognized metric whose evidence
    # didn't hold up against the source page text, so the whole call was
    # retried once. Read by postprocess.verify_metric to apply a small
    # extra confidence discount on top of the usual evidence-match scoring.
    needed_retry: bool = False
    evidence: Evidence = Field(default_factory=lambda: Evidence(doc_name="", page=None, snippet=""))

class ChartSeriesPoint(BaseModel):
    label: str
    value: Optional[float] = None

class ChartExtraction(BaseModel):
    """A chart/graph (bar, line, pie, ...) detected on a page image by a
    vision-capable model -- distinct from table extraction (Camelot/
    pdfplumber, which reads ruled/whitespace tabular structures) and OCR
    (which reads plain text off a scanned page). Values are read off pixels,
    not cited from text, so confidence is capped below what a verbatim
    text-evidence match could earn."""
    page: int
    chart_type: Optional[str] = None  # "bar" | "line" | "pie" | "area" | "scatter" | "other"
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    series: List[ChartSeriesPoint] = Field(default_factory=list)
    summary: str = ""
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

    # Layout-derived context (see ddgpt.layout)
    net_irr_basis: Optional[DefinitionContext] = None
    sections_detected: List[str] = Field(default_factory=list)

    irr_mentions: List[dict] = Field(default_factory=list)

    # Populated when two extractors produce materially different values for
    # the same field; distinct from cross-document NumericMismatchRule flags.
    extractor_disagreements: List[dict] = Field(default_factory=list)

    # Full reproducibility trail: every candidate value each extractor (and,
    # if used, the table parser) produced per field
    extraction_candidates: Dict[str, List[dict]] = Field(default_factory=dict)

    # Charts/graphs detected on page images by the (opt-in) vision extractor.
    chart_extractions: List[dict] = Field(default_factory=list)

    # Open-ended metric extraction (see MetricEntry above) -- additive
    # alongside the six named fields above during the phased rollout.
    # Populated by every extractor and properly reconciled (trust-weighted,
    # deduplicated) by FusionExtractor as of Phase 2 of the migration; the
    # six named fields are still what rules/reports read directly, kept in
    # sync via sync_legacy_fields() below.
    metrics: List[MetricEntry] = Field(default_factory=list)


def _model_fingerprint(models: Sequence[Type[BaseModel]]) -> str:
    """Hash of every field name across the given models -- included in the
    disk cache's content-hash key (see fusion_extractor.py) so a schema
    change (a field added, renamed, or removed on any tracked model)
    automatically invalidates old cached pickles, rather than pickle
    silently restoring an object missing a field that a fresh
    `model_validate` call would have filled with its default. Pickle
    reconstructs an instance's `__dict__` directly and doesn't re-run
    validators, so a stale pickle from before this field existed raises
    AttributeError the first time something reads it -- confirmed by a
    real crash during this project's own development when `needed_retry`
    was added to MetricEntry."""
    parts = [f"{m.__name__}:{','.join(sorted(m.model_fields.keys()))}" for m in models]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


# Every BaseModel that ends up nested inside a cached ExtractedDoc --
# extend this list whenever a new one is added, so its fields are covered
# by SCHEMA_FINGERPRINT too.
SCHEMA_FINGERPRINT = _model_fingerprint([
    DefinitionContext, Metric, FeeMetric, CarryMetric, MetricEntry,
    ChartSeriesPoint, ChartExtraction, ExtractedDoc,
])


LEGACY_METRIC_NAMES = ("aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry")


def sync_legacy_fields(doc: ExtractedDoc) -> None:
    """Backward-compat shim: populates the six legacy named fields (plus
    carry.hurdle) from the corresponding entries in the reconciled `metrics`
    list, so rules/reports that haven't migrated to read `metrics` directly
    yet (everything, as of Phase 2) keep seeing correct, fully-reconciled
    values. Safe to call any time `metrics` changes -- both right after
    fusion reconciles it, and again after evidence verification adjusts
    each entry's confidence, so the legacy fields never go stale."""
    by_name = {m.name: m for m in doc.metrics}

    def _sync(name: str, attr) -> None:
        entry = by_name.get(name)
        if entry is None:
            return
        attr.value = entry.value
        attr.confidence = entry.confidence
        attr.agreement = entry.agreement
        attr.evidence = entry.evidence

    _sync("aum", doc.aum)
    _sync("net_irr", doc.net_irr)
    _sync("tvpi", doc.tvpi)
    _sync("target_irr", doc.target_irr)

    _sync("mgmt_fee", doc.mgmt_fee)
    if "mgmt_fee" in by_name:
        doc.mgmt_fee.basis = by_name["mgmt_fee"].basis

    _sync("carry", doc.carry)
    if "hurdle_rate" in by_name:
        doc.carry.hurdle = by_name["hurdle_rate"].value
