import math
from typing import List
from ddgpt.rules.base import Rule

SEVERITY_WEIGHTS = {
    "RED": 1.0,
    "YELLOW": 0.5
}

# Larger K => the score grows more slowly per additional flag (saturates
# further out toward 1.0).
SATURATION_K = 2.0

class RiskEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = rules

    def evaluate(self, extracted: List[dict]):
        flags = []
        for r in self.rules:
            flags.extend(r.apply(extracted))

        score = self.score_from_severities([f.severity for f in flags])
        return flags, score

    @staticmethod
    def score_from_severities(severities):
        if not severities:
            return 0.0
        total_weight = sum(SEVERITY_WEIGHTS.get(s, 0.3) for s in severities)
        # Monotonically increasing in both flag count and severity mix --
        # a flat average can't distinguish one RED flag from ten of them,
        # since both would average out to the same score.
        return 1.0 - math.exp(-total_weight / SATURATION_K)
