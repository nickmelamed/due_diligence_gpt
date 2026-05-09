from __future__ import annotations

def determine_recommendation(flags):
    red = sum(1 for f in flags if f["severity"] == "RED")
    yellow = sum(1 for f in flags if f["severity"] == "YELLOW")

    if red >= 2:
        return {
            "decision": "PASS",
            "confidence": 0.88
        }

    if red >= 1 or yellow >= 3:
        return {
            "decision": "INVESTIGATE",
            "confidence": 0.74
        }

    return {
        "decision": "APPROVE",
        "confidence": 0.66
    }