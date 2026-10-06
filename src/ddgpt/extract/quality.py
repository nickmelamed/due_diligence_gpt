from __future__ import annotations
from typing import List, Optional


def metric_confidences(extracted: List[dict]) -> List[float]:
    """Every non-null confidence value across every document's open
    `metrics` list -- the shared basis for "how much do we trust what we
    extracted", used by both the recommendation engine and the PDF's
    per-document data-quality table so the two never disagree."""
    return [
        m.get("confidence", 0.0)
        for doc in extracted
        for m in doc.get("metrics", [])
        if m.get("value") is not None
    ]


def average_confidence(extracted: List[dict]) -> Optional[float]:
    confidences = metric_confidences(extracted)
    return (sum(confidences) / len(confidences)) if confidences else None
