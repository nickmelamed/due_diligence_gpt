from __future__ import annotations
from typing import List
import re

from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc

AUTHORITY_WEIGHTS = [
    ("lpa", 0.95),
    ("agreement", 0.90),
    ("audited", 0.88),
    ("statement", 0.82),
    ("quarter", 0.75),
    ("update", 0.72),
    ("deck", 0.60),
    ("assumptions", 0.65),
]

def authority_weight(doc_name: str) -> float:
    name = doc_name.lower()
    for key, w in AUTHORITY_WEIGHTS:
        if key in name:
            return w
    return 0.65

def _page_text(pages: List[Page], page_num: int | None) -> str:
    if page_num is None:
        return ""
    for p in pages:
        if p.page_num == page_num:
            return p.text or ""
    return ""

def verify_and_score(doc: ExtractedDoc, pages: List[Page]) -> ExtractedDoc:
    base_conf = authority_weight(doc.doc_name)

    def process_metric(metric, key: str):
        if metric.value is None:
            if f"{key}.value" not in doc.missing_fields:
                doc.missing_fields.append(f"{key}.value")
            metric.confidence = 0.0
            return

        metric.confidence = max(metric.confidence, base_conf)

        snip = (metric.evidence.snippet or "").strip()
        pg = metric.evidence.page
        page_text = _page_text(pages, pg)

        if snip and page_text:
            norm_page = re.sub(r"\s+", " ", page_text)
            norm_snip = re.sub(r"\s+", " ", snip)
            if norm_snip not in norm_page:
                metric.confidence = min(metric.confidence, 0.40)
                doc.notes.append(f"Evidence snippet for {key} not found verbatim on page {pg}; confidence reduced.")
        else:
            metric.confidence = min(metric.confidence, 0.40)
            doc.notes.append(f"Missing evidence page/snippet for {key}; confidence reduced.")

    process_metric(doc.aum, "aum")
    process_metric(doc.net_irr, "net_irr")
    process_metric(doc.tvpi, "tvpi")
    process_metric(doc.target_irr, "target_irr")
    process_metric(doc.mgmt_fee, "mgmt_fee")

    if doc.carry.value is None and "carry.value" not in doc.missing_fields:
        doc.missing_fields.append("carry.value")
    if doc.carry.hurdle is None and "carry.hurdle" not in doc.missing_fields:
        doc.missing_fields.append("carry.hurdle")

    if doc.carry.value is not None:
        doc.carry.confidence = max(doc.carry.confidence, base_conf)
        snip = (doc.carry.evidence.snippet or "").strip()
        pg = doc.carry.evidence.page
        page_text = _page_text(pages, pg)
        if snip and page_text:
            norm_page = re.sub(r"\s+", " ", page_text)
            norm_snip = re.sub(r"\s+", " ", snip)
            if norm_snip not in norm_page:
                doc.carry.confidence = min(doc.carry.confidence, 0.40)
                doc.notes.append(f"Evidence snippet for carry not found verbatim on page {pg}; confidence reduced.")
        else:
            doc.carry.confidence = min(doc.carry.confidence, 0.40)
            doc.notes.append("Missing evidence page/snippet for carry; confidence reduced.")

    return doc
