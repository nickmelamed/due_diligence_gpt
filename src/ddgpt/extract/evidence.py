from __future__ import annotations
import re
import difflib
from typing import List, NamedTuple, Optional

# Shared evidence-citation matching -- used both to score confidence after
# fusion (postprocess.verify_metric, on the single winning entry) and to
# validate a candidate metric entry before fusion even sees it (fusion's
# per-candidate scoring, and the extraction-time retry check in
# llm_common.py) -- one implementation so the three layers can never
# disagree about what counts as a good citation.

FUZZY_MATCH_THRESHOLD = 0.80

# Multiplier applied to a candidate's trust-weighted score/confidence based
# on how its evidence.snippet held up against the actual cited page text.
EVIDENCE_SCORE_BY_MATCH = {
    "missing": 0.50,
    "verbatim": 1.0,
    "fuzzy": 0.75,
    "not_found": 0.40,
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def get_page_text(pages: List, page_num: Optional[int]) -> str:
    if page_num is None:
        return ""
    for p in pages:
        if p.page_num == page_num:
            return p.text or ""
    return ""


def fuzzy_match_ratio(snippet: str, page_text: str) -> float:
    """Fraction of a normalized snippet's characters coverable by matching
    blocks against normalized page_text, in order. 1.0 for an exact
    substring; degrades gracefully for OCR substitutions, hyphenation
    breaks, or ligature differences instead of an all-or-nothing verbatim
    check. Both arguments must already be normalize()-d."""
    if not snippet:
        return 0.0
    if snippet in page_text:
        return 1.0

    matcher = difflib.SequenceMatcher(None, page_text, snippet, autojunk=False)
    matched_chars = sum(block.size for block in matcher.get_matching_blocks())
    return matched_chars / len(snippet)


class EvidenceMatch(NamedTuple):
    label: str  # "missing" | "verbatim" | "fuzzy" | "not_found"
    ratio: float  # 0.0 for "missing"; the raw fuzzy_match_ratio otherwise


def classify_evidence_match(raw_snippet: str, raw_page_text: str) -> EvidenceMatch:
    snippet = normalize(raw_snippet)
    if not snippet:
        return EvidenceMatch("missing", 0.0)

    ratio = fuzzy_match_ratio(snippet, normalize(raw_page_text))
    if ratio >= 1.0:
        return EvidenceMatch("verbatim", ratio)
    if ratio >= FUZZY_MATCH_THRESHOLD:
        return EvidenceMatch("fuzzy", ratio)
    return EvidenceMatch("not_found", ratio)
