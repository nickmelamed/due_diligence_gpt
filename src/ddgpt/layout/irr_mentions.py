from __future__ import annotations

import re
from typing import Dict, List, Tuple

from ddgpt.io.loaders import Page

# Catches "Net IRR: 16.8%", "Target IRR: 18%", "gross IRR of 20%" -- a
# gross/net qualifier and/or "target" before "IRR", then a percentage within
# a short window afterward. The window is deliberately short (~25 chars) and
# excludes newlines so it can't leap across a paragraph and misassociate an
# unrelated figure (e.g. a management fee percentage) with "IRR".
IRR_LABEL_FIRST_RE = re.compile(
    r"(?:(gross|net)\s+)?(?:target\s+)?irr\b[^%\n]{0,25}?([0-9]+(?:\.[0-9]+)?)\s*%",
    re.IGNORECASE,
)

# Catches "20% gross IRR" -- the number before the qualifier/label.
IRR_VALUE_FIRST_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*%\s*(gross|net)?\s*irr\b",
    re.IGNORECASE,
)


def _snippet_around(text: str, start: int, end: int) -> str:
    lo = max(0, start - 30)
    hi = min(len(text), end + 30)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def _overlaps(span: Tuple[int, int], existing: List[Tuple[int, int]]) -> bool:
    start, end = span
    return any(not (end <= s or start >= e) for s, e in existing)


def find_irr_mentions(pages: List[Page]) -> List[dict]:
    """Every IRR-shaped percentage mention across the whole document -- not
    just the one a field extractor latched onto for target_irr/net_irr.

    A secondary claim stated once in prose (e.g. "targeting a 20% gross
    IRR" in a quarterly-update paragraph) never becomes a structured field
    on its own; this makes it visible so a rule can compare it against
    whatever *did* get extracted, instead of the discrepancy silently
    living only in an LLM's free-text notes.
    """
    mentions: List[dict] = []
    spans_by_page: Dict[int, List[Tuple[int, int]]] = {}

    for page in pages:
        text = page.text or ""
        spans = spans_by_page.setdefault(page.page_num, [])

        for pattern, basis_group, value_group in (
            (IRR_LABEL_FIRST_RE, 1, 2),
            (IRR_VALUE_FIRST_RE, 2, 1),
        ):
            for m in pattern.finditer(text):
                span = (m.start(), m.end())
                if _overlaps(span, spans):
                    continue

                try:
                    value = float(m.group(value_group))
                except (TypeError, ValueError):
                    continue

                basis = m.group(basis_group)
                basis = basis.lower() if basis else None

                spans.append(span)
                mentions.append({
                    "value": value,
                    "basis": basis,
                    "page": page.page_num,
                    "snippet": _snippet_around(text, m.start(), m.end()),
                })

    return mentions
