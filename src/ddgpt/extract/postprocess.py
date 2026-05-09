from __future__ import annotations

import re
from typing import List
from datetime import datetime, UTC

from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.pipeline.scoring import final_confidence

AUTHORITY_WEIGHTS = [
    ("lpa", 0.98),
    ("agreement", 0.95),
    ("audited", 0.93),
    ("financial", 0.90),
    ("statement", 0.85),
    ("quarter", 0.75),
    ("update", 0.70),
    ("deck", 0.55),
]

def authority_weight(doc_name: str) -> float:
    name = doc_name.lower()

    for key, weight in AUTHORITY_WEIGHTS:
        if key in name:
            return weight

    return 0.50

def temporal_weight(doc_date: str | None) -> float:
    if not doc_date:
        return 0.50

    try:
        now = datetime.now(UTC)
        dt = datetime.fromisoformat(doc_date)
        days = (now - dt).days
        return max(0.30, min(1.0, 1.0 - (days / 3650)))
    except Exception:
        return 0.50

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()

def get_page_text(pages: List[Page], page_num: int | None) -> str:
    if page_num is None:
        return ""

    for p in pages:
        if p.page_num == page_num:
            return p.text or ""

    return ""

def verify_metric(metric, key: str, pages, authority, recency, notes, missing_fields):
    if metric.value is None:
        missing_fields.append(f"{key}.value")
        metric.confidence = 0.0
        return

    extraction_conf = metric.confidence

    snippet = normalize(metric.evidence.snippet)
    page_text = normalize(get_page_text(pages, metric.evidence.page))

    evidence_score = 1.0

    if not snippet:
        evidence_score *= 0.50
        notes.append(f"{key}: missing evidence snippet")

    elif snippet not in page_text:
        evidence_score *= 0.40
        notes.append(f"{key}: evidence snippet not found verbatim on cited page")

    agreement = 0.80

    metric.confidence = final_confidence(
        extraction_conf=extraction_conf,
        authority=authority,
        agreement=agreement,
        recency=recency
    ) * evidence_score

def verify_and_score(doc: ExtractedDoc, pages: List[Page]) -> ExtractedDoc:
    authority = authority_weight(doc.doc_name)
    recency = temporal_weight(doc.doc_date)

    verify_metric(
        doc.aum,
        "aum",
        pages,
        authority,
        recency,
        doc.notes,
        doc.missing_fields
    )

    verify_metric(
        doc.net_irr,
        "net_irr",
        pages,
        authority,
        recency,
        doc.notes,
        doc.missing_fields
    )

    verify_metric(
        doc.tvpi,
        "tvpi",
        pages,
        authority,
        recency,
        doc.notes,
        doc.missing_fields
    )

    verify_metric(
        doc.target_irr,
        "target_irr",
        pages,
        authority,
        recency,
        doc.notes,
        doc.missing_fields
    )

    verify_metric(
        doc.mgmt_fee,
        "mgmt_fee",
        pages,
        authority,
        recency,
        doc.notes,
        doc.missing_fields
    )

    verify_metric(
        doc.carry,
        "carry",
        pages,
        authority,
        recency,
        doc.notes,
        doc.missing_fields
    )

    return doc
