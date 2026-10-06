from __future__ import annotations
from typing import List, Tuple
from ddgpt.rules.base import Rule, Flag
from ddgpt.extract.metric_registry import get as get_metric_def, format_metric_value

def pct_delta(a: float, b: float) -> float:
    denom = (abs(a) + abs(b)) / 2.0
    if denom == 0:
        return 0.0
    return abs(a - b) / denom

# The exact flag `type` a mismatch on each unit gets -- e.g. "AUM differs"
# and "GP Commitment differs" (both unit=usd) both surface as
# USD_MISMATCH, with the specific metric always identified via Flag.metric
# and spelled out in `detail`.
UNIT_FLAG_TYPES = {
    "usd": "USD_MISMATCH",
    "percent": "PERCENT_MISMATCH",
    "multiple": "MULTIPLE_MISMATCH",
    "count": "COUNT_MISMATCH",
    "year": "YEAR_MISMATCH",
    "other": "METRIC_MISMATCH",
}

# Preserves the specific, well-crafted messaging the original hand-written
# checks had for these three; anything else (new registry metrics, and any
# fully custom one) falls back to generic-but-still-useful messaging below.
KNOWN_MESSAGING = {
    "aum": (
        "AUM impacts scale, fees, and benchmarking; mismatches require reconciliation.",
        "Which document is authoritative for AUM as-of date? Provide supporting statement/capital account details.",
    ),
    "mgmt_fee": (
        "Fee terms directly affect net returns and legal obligations; LPA typically governs.",
        "Confirm the controlling fee schedule and whether any side-letter modifies the base fee.",
    ),
    "target_irr": (
        "Different stated targets can reflect marketing vs underwriting assumptions.",
        "Is one target marketing and the other underwriting base-case? Which governs IC decision-making?",
    ),
}


def _display_label(name: str) -> str:
    metric_def = get_metric_def(name)
    return metric_def.display_label if metric_def else name.replace("_", " ").title()


class NumericMismatchRule(Rule):
    """Cross-document numeric comparison for every metric two documents
    both report a value for -- not just a fixed set of named fields.
    Tolerance is driven by the metric's unit type (usd/percent/multiple/
    count/year) via ToleranceConfig, with per-metric overrides (from the
    metric registry, or ToleranceConfig.per_metric_overrides) taking
    priority over the unit-type default -- e.g. mgmt_fee keeps a tighter
    absolute-point tolerance than a generic percent metric."""

    def __init__(self, tolerance_config):
        self.tolerance = tolerance_config

    def _tolerance_for(self, name: str, unit: str) -> Tuple[str, float]:
        """Returns (kind, threshold); kind is "relative" (a fraction of the
        average of the two values) or "absolute" (a flat difference)."""
        metric_def = get_metric_def(name)
        override = None
        if metric_def is not None:
            override = metric_def.tolerance_override
        if override is None:
            override = self.tolerance.per_metric_overrides.get(name)

        if override:
            if "rel_pct" in override:
                return "relative", override["rel_pct"]
            if "abs_pts" in override:
                return "absolute", override["abs_pts"]

        if unit == "usd":
            return "relative", self.tolerance.usd_rel_pct
        if unit == "percent":
            return "absolute", self.tolerance.percent_abs_pts
        if unit == "multiple":
            return "relative", self.tolerance.multiple_rel_pct
        if unit == "count":
            return "absolute", self.tolerance.count_abs
        if unit == "year":
            return "absolute", self.tolerance.year_abs

        return "absolute", self.tolerance.percent_abs_pts  # "other" fallback

    def _severity_for(self, name: str) -> str:
        metric_def = get_metric_def(name)
        # Conservative default for a metric the registry has never seen
        # before: no basis to judge a never-seen-before label's materiality.
        return metric_def.default_severity if metric_def else "YELLOW"

    def apply(self, extracted: List[dict]) -> List[Flag]:
        flags: List[Flag] = []

        for i in range(len(extracted)):
            for j in range(i + 1, len(extracted)):
                A = extracted[i]
                B = extracted[j]
                doc_a, doc_b = A["doc_name"], B["doc_name"]

                by_name_a = {m["name"]: m for m in A.get("metrics", [])}
                by_name_b = {m["name"]: m for m in B.get("metrics", [])}

                for name in sorted(set(by_name_a) & set(by_name_b)):
                    entry_a = by_name_a[name]
                    entry_b = by_name_b[name]

                    val_a, val_b = entry_a.get("value"), entry_b.get("value")
                    if val_a is None or val_b is None:
                        continue

                    unit = entry_a.get("unit") or entry_b.get("unit") or "other"
                    kind, threshold = self._tolerance_for(name, unit)

                    if kind == "relative":
                        delta = pct_delta(val_a, val_b)
                        exceeds = delta > threshold
                        delta_desc = f"{delta * 100:.1f}%"
                    else:
                        delta = abs(val_a - val_b)
                        exceeds = delta > threshold
                        # Absolute deltas are point differences (unit=percent)
                        # or small-integer differences (count/year) -- show
                        # the delta in the same unit as the values themselves
                        # rather than a bare number with no context.
                        delta_desc = format_metric_value(delta, unit) if unit == "percent" else f"{delta:.2f}"

                    if not exceeds:
                        continue

                    label = _display_label(name)
                    why_it_matters, question_to_ask = KNOWN_MESSAGING.get(name, (
                        f"Reporting a materially different {label} figure across the fund's own "
                        f"documents warrants reconciliation before relying on either value.",
                        f"Which document is authoritative for {label}, and why do the two figures differ?",
                    ))

                    evidence_a = entry_a.get("evidence") or {}
                    evidence_b = entry_b.get("evidence") or {}

                    flags.append(Flag(
                        severity=self._severity_for(name),
                        type=UNIT_FLAG_TYPES.get(unit, "METRIC_MISMATCH"),
                        metric=name,
                        docs=f"{doc_a} vs {doc_b}",
                        detail=(
                            f"{label} differs by {delta_desc}: "
                            f"{format_metric_value(val_a, unit)} vs {format_metric_value(val_b, unit)}"
                        ),
                        evidence=(
                            f'{doc_a} (p.{evidence_a.get("page")}): {evidence_a.get("snippet")} | '
                            f'{doc_b} (p.{evidence_b.get("page")}): {evidence_b.get("snippet")}'
                        ),
                        why_it_matters=why_it_matters,
                        question_to_ask=question_to_ask,
                    ))

        return flags
