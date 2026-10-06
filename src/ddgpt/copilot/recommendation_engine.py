from __future__ import annotations
from ddgpt.extract.quality import average_confidence


def determine_recommendation(flags, extracted=None):
    red = sum(1 for f in flags if f["severity"] == "RED")
    yellow = sum(1 for f in flags if f["severity"] == "YELLOW")

    if red >= 2:
        decision = "PASS"
    elif red >= 1 or yellow >= 3:
        decision = "INVESTIGATE"
    else:
        decision = "APPROVE"

    # Confidence reflects how much of the underlying data we actually
    # trust (average extraction confidence), not the decision logic --
    # a fixed per-decision constant here previously meant "APPROVE" always
    # carried the *lowest* confidence of the three tiers, which read
    # backwards to a reviewer.
    confidence = average_confidence(extracted or []) or 0.0

    return {
        "decision": decision,
        "confidence": confidence,
    }