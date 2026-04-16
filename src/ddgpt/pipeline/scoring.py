from datetime import datetime, UTC
import math

def temporal_weight(doc_date: str | None, now=None):
    if not doc_date:
        return 0.5
    now = now or datetime.now(UTC)
    doc_dt = datetime.fromisoformat(doc_date)
    days = (now - doc_dt).days
    return math.exp(-days / 365)

def final_confidence(extraction_conf, authority, agreement, recency):
    return (
        0.35 * extraction_conf +
        0.25 * authority +
        0.20 * agreement +
        0.20 * recency
    )