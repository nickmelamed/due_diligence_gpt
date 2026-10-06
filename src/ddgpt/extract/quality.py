from __future__ import annotations
from typing import List, Optional, Tuple

from ddgpt.extract.postprocess import CORE_METRIC_NAMES


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


def core_metric_coverage(doc: dict) -> Tuple[int, int]:
    """Return (found, total) for the core metrics in one document.

    A core metric counts as found when the document has an entry with a
    non-null value. Metrics outside the core set do not change the total.
    """
    present = {m.get("name") for m in doc.get("metrics", []) if m.get("value") is not None}
    found = sum(1 for name in CORE_METRIC_NAMES if name in present)
    return found, len(CORE_METRIC_NAMES)
