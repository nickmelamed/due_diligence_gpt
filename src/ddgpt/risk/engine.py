from typing import List
from ddgpt.rules.base import Rule

SEVERITY_WEIGHTS = {
    "RED": 1.0,
    "YELLOW": 0.5
}

class RiskEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = rules

    def evaluate(self, extracted: List[dict]):
        flags = []
        for r in self.rules:
            flags.extend(r.apply(extracted))

        score = self._score(flags)
        return flags, score

    def _score(self, flags):
        if not flags:
            return 0.0
        total = sum(SEVERITY_WEIGHTS.get(f.severity, 0.3) for f in flags)
        return total / len(flags)