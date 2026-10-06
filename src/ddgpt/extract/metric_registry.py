from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

# Static domain vocabulary for the open-ended metric extraction system --
# lives here as plain code, not in Config, the same way DEFAULT_AUTHORITY_WEIGHTS
# (postprocess.py) and DEFAULT_EXTRACTOR_WEIGHTS (fusion_extractor.py) are
# module constants next to their usage rather than runtime-tunable settings.
#
# This registry lets extraction stay open (any quantifiable financial metric
# can be captured, not just these seventeen) while still giving cross-document
# comparison something stable to key off of for the metrics that are common
# enough to name in advance. Anything not recognized here still gets captured
# -- see normalize_metric_name -- just without the richer metadata (category,
# tolerance override, severity) a registry entry carries.


class MetricDef(BaseModel):
    name: str                                  # canonical snake_case name, e.g. "dpi"
    display_label: str                         # "DPI"
    unit: str                                  # "usd" | "percent" | "multiple" | "count" | "year"
    category: str                              # "performance" | "fees_and_terms" | "capital_and_size"
    aliases: List[str] = Field(default_factory=list)
    tolerance_override: Optional[dict] = None  # e.g. {"abs_pts": 0.25}
    specialized_rule: Optional[str] = None     # e.g. "irr_family" -- tags a metric for rule logic
    # that inherently needs to know what it means (InternalInconsistencyRule,
    # DefinitionDriftRule), as opposed to generic cross-document comparison.
    default_severity: str = "YELLOW"


_SEED_METRICS: List[MetricDef] = [
    MetricDef(
        name="aum", display_label="AUM", unit="usd", category="capital_and_size",
        aliases=["aum", "assets under management", "total assets under management"],
        default_severity="RED",  # preserves NumericMismatchRule's original AUM_MISMATCH severity
    ),
    MetricDef(
        name="net_irr", display_label="Net IRR", unit="percent", category="performance",
        aliases=["net irr", "net internal rate of return"],
        specialized_rule="irr_family",
    ),
    MetricDef(
        name="gross_irr", display_label="Gross IRR", unit="percent", category="performance",
        aliases=["gross irr", "gross internal rate of return"],
        specialized_rule="irr_family",
    ),
    MetricDef(
        name="target_irr", display_label="Target IRR", unit="percent", category="performance",
        aliases=["target irr", "target internal rate of return", "underwriting irr"],
        specialized_rule="irr_family",
    ),
    MetricDef(
        name="tvpi", display_label="TVPI", unit="multiple", category="performance",
        aliases=["tvpi", "total value to paid-in", "total value to paid in"],
    ),
    MetricDef(
        name="dpi", display_label="DPI", unit="multiple", category="performance",
        aliases=["dpi", "distributions to paid-in", "distributions to paid in", "dpi multiple"],
    ),
    MetricDef(
        name="rvpi", display_label="RVPI", unit="multiple", category="performance",
        aliases=["rvpi", "residual value to paid-in", "residual value to paid in"],
    ),
    MetricDef(
        name="moic", display_label="MOIC", unit="multiple", category="performance",
        aliases=["moic", "multiple on invested capital", "gross moic", "net moic"],
    ),
    MetricDef(
        name="nav", display_label="NAV", unit="usd", category="capital_and_size",
        aliases=["nav", "net asset value"],
    ),
    MetricDef(
        name="mgmt_fee", display_label="Management Fee", unit="percent", category="fees_and_terms",
        aliases=["management fee", "mgmt fee", "annual management fee"],
        tolerance_override={"abs_pts": 0.25},
        default_severity="RED",  # preserves NumericMismatchRule's original MGMT_FEE_MISMATCH severity
    ),
    MetricDef(
        name="carry", display_label="Carried Interest", unit="percent", category="fees_and_terms",
        aliases=["carried interest", "carry", "promote"],
        default_severity="RED",  # contractual term, same class as mgmt_fee -- previously had no cross-doc check at all
    ),
    MetricDef(
        name="hurdle_rate", display_label="Hurdle Rate", unit="percent", category="fees_and_terms",
        aliases=["hurdle rate", "preferred return", "hurdle"],
        default_severity="RED",  # contractual term, same class as mgmt_fee -- previously had no cross-doc check at all
    ),
    MetricDef(
        name="vintage_year", display_label="Vintage Year", unit="year", category="capital_and_size",
        aliases=["vintage year", "vintage"],
    ),
    MetricDef(
        name="fund_size", display_label="Fund Size", unit="usd", category="capital_and_size",
        aliases=["fund size", "total fund size", "target fund size", "fund commitment"],
    ),
    MetricDef(
        name="gp_commitment", display_label="GP Commitment", unit="usd", category="capital_and_size",
        aliases=["gp commitment", "general partner commitment"],
    ),
    MetricDef(
        name="called_capital", display_label="Called Capital", unit="usd", category="capital_and_size",
        aliases=["called capital", "capital called", "paid-in capital", "paid in capital"],
    ),
    MetricDef(
        name="distributed_capital", display_label="Distributed Capital", unit="usd", category="capital_and_size",
        aliases=["distributed capital", "capital distributed", "total distributions"],
    ),
]

METRIC_REGISTRY: Dict[str, MetricDef] = {m.name: m for m in _SEED_METRICS}


def get(name: str) -> Optional[MetricDef]:
    return METRIC_REGISTRY.get(name)


def all_metrics() -> List[MetricDef]:
    return list(METRIC_REGISTRY.values())


# Shared taxonomy for reporting (render/pdf_report.py, report/ic_memo.py,
# report/tables.py) -- one source of truth for how metrics are grouped and
# displayed, so the PDF/CSV/memo/Streamlit surfaces can't drift from each
# other or from the registry itself.
CATEGORY_ORDER = ["performance", "fees_and_terms", "capital_and_size", "other"]
CATEGORY_LABELS = {
    "performance": "Performance",
    "fees_and_terms": "Fees & Terms",
    "capital_and_size": "Capital & Size",
    "other": "Other / Custom",
}


def category_for(name: str) -> str:
    metric_def = get(name)
    return metric_def.category if metric_def else "other"


def display_label(name: str) -> str:
    metric_def = get(name)
    return metric_def.display_label if metric_def else name.replace("_", " ").title()


def format_metric_value(value: Optional[float], unit: str) -> str:
    if value is None:
        return "N/A"
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "multiple":
        return f"{value:.2f}x"
    if unit == "usd":
        if abs(value) >= 1e9:
            return f"${value / 1e9:.2f}B"
        if abs(value) >= 1e6:
            return f"${value / 1e6:.2f}M"
        return f"${value:,.0f}"
    if unit in ("year", "count"):
        return f"{value:.0f}"
    return f"{value:g}"


def _normalize_for_matching(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace -- for comparing a
    raw label against a registry alias regardless of case/hyphenation."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(text: str) -> str:
    """Deterministic snake_case name for a label that doesn't match the
    registry -- the same raw label always slugifies to the same string, so
    an extractor-invented metric name stays comparable across documents even
    though it was never seen in advance."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown_metric"


def normalize_metric_name(raw_label: str) -> Tuple[str, bool]:
    """Match a raw label against the seed registry's aliases, falling back to a
    stable slug if nothing matches. Returns (name, is_custom)."""
    if not raw_label:
        return "unknown_metric", True

    normalized = _normalize_for_matching(raw_label)

    # Exact match first, across the whole registry, before any substring
    # fallback -- avoids a short alias incidentally substring-matching an
    # unrelated label.
    for metric_def in METRIC_REGISTRY.values():
        for alias in [metric_def.name, *metric_def.aliases]:
            if _normalize_for_matching(alias) == normalized:
                return metric_def.name, False

    for metric_def in METRIC_REGISTRY.values():
        for alias in [metric_def.name, *metric_def.aliases]:
            alias_norm = _normalize_for_matching(alias)
            if alias_norm and (alias_norm in normalized or normalized in alias_norm):
                return metric_def.name, False

    return slugify(raw_label), True
