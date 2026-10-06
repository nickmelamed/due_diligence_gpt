from __future__ import annotations

from typing import List
from datetime import datetime, UTC

from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc, sync_legacy_fields
from ddgpt.pipeline.scoring import final_confidence
from ddgpt.extract.evidence import get_page_text, classify_evidence_match, EVIDENCE_SCORE_BY_MATCH

# The six legacy named fields (+ hurdle, tracked under carry) -- still
# checked explicitly for "missing" status, since a document simply not
# mentioning some never-seen-before custom metric isn't "missing" the way
# a document lacking one of these well-known ones is.
CORE_METRIC_NAMES = ("aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry", "hurdle_rate")

# Extra discount stacked on top of the usual evidence-match score when a
# metric's final value only came from a second extraction attempt (see
# llm_common.extract_with_evidence_retry) -- a call that needed retrying is
# a slightly weaker signal even when it ultimately produced a clean citation.
RETRY_PENALTY = 0.9

DEFAULT_AUTHORITY_WEIGHTS = {
    "lpa": 0.98,
    "agreement": 0.95,
    "audited": 0.93,
    "financial": 0.90,
    "statement": 0.85,
    "quarter": 0.75,
    "update": 0.70,
    "deck": 0.55,
}

def authority_weight(doc_name: str, weights: dict | None = None, default: float = 0.50) -> float:
    name = doc_name.lower()
    weights = weights or DEFAULT_AUTHORITY_WEIGHTS

    for key, weight in weights.items():
        if key in name:
            return weight

    return default

def temporal_weight(doc_date: str | None) -> float:
    if not doc_date:
        return 0.50

    try:
        now = datetime.now(UTC)
        dt = datetime.fromisoformat(doc_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        days = (now - dt).days
        return max(0.30, min(1.0, 1.0 - (days / 3650)))
    except Exception:
        return 0.50

def verify_metric(metric, key: str, pages, authority, recency, notes, missing_fields):
    if metric.value is None:
        if f"{key}.value" not in missing_fields:
            missing_fields.append(f"{key}.value")
        metric.confidence = 0.0
        return

    extraction_conf = metric.confidence

    page_text = get_page_text(pages, metric.evidence.page)
    match = classify_evidence_match(metric.evidence.snippet, page_text)
    evidence_score = EVIDENCE_SCORE_BY_MATCH[match.label]

    if match.label == "missing":
        notes.append(f"{key}: missing evidence snippet")
    elif match.label == "fuzzy":
        notes.append(
            f"{key}: evidence snippet matched page fuzzily "
            f"({match.ratio:.0%} — likely OCR/rendering noise, not verbatim)"
        )
    elif match.label == "not_found":
        notes.append(f"{key}: evidence snippet not found verbatim on cited page")

    if getattr(metric, "needed_retry", False):
        evidence_score *= RETRY_PENALTY

    agreement = getattr(metric, "agreement", 1.0)

    metric.confidence = final_confidence(
        extraction_conf=extraction_conf,
        authority=authority,
        agreement=agreement,
        recency=recency
    ) * evidence_score

def verify_and_score(
    doc: ExtractedDoc,
    pages: List[Page],
    authority_weights: dict | None = None,
    authority_default_weight: float = 0.50,
) -> ExtractedDoc:
    authority = authority_weight(doc.doc_name, authority_weights, authority_default_weight)
    recency = temporal_weight(doc.doc_date)

    # Every metric FusionExtractor reconciled -- known registry metrics and
    # customs alike -- gets the same evidence-verification treatment. Every
    # entry here already has a value (Phase 1's cleaning drops anything
    # without one), so verify_metric's missing-field branch never actually
    # fires from this loop; see the explicit core-field check below for
    # that.
    for metric in doc.metrics:
        verify_metric(metric, metric.name, pages, authority, recency, doc.notes, doc.missing_fields)

    present_names = {m.name for m in doc.metrics}
    for name in CORE_METRIC_NAMES:
        marker = "carry.hurdle" if name == "hurdle_rate" else f"{name}.value"
        if name not in present_names and marker not in doc.missing_fields:
            doc.missing_fields.append(marker)

    # Re-sync now that verification has adjusted each entry's confidence --
    # otherwise the legacy fields would reflect pre-verification confidence.
    sync_legacy_fields(doc)

    return doc
