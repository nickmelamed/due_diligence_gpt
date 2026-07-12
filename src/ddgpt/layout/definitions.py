from __future__ import annotations

import re
from typing import List, Optional

from ddgpt.io.loaders import Page
from ddgpt.layout.models import DocumentLayout

# Broader than a literal "gross"/"net" keyword match: covers the common
# ways funds phrase the same convention without using either word.
NET_PATTERNS = [
    re.compile(r"\bnet\s+of\s+(all\s+)?fees\b", re.IGNORECASE),
    re.compile(r"\bnet\s+of\s+carried\s+interest\b", re.IGNORECASE),
    re.compile(r"\bafter[\s-]fee(s)?\b", re.IGNORECASE),
    re.compile(r"\bnet\s+irr\b", re.IGNORECASE),
    re.compile(r"\bnet\s+returns?\b", re.IGNORECASE),
]

GROSS_PATTERNS = [
    re.compile(r"\bgross\s+of\s+fees\b", re.IGNORECASE),
    re.compile(r"\bgross\s+irr\b", re.IGNORECASE),
    re.compile(r"\bbefore[\s-]fee(s)?\b", re.IGNORECASE),
    re.compile(r"\bpre[\s-]fee(s)?\b", re.IGNORECASE),
    re.compile(r"\bgross\s+returns?\b", re.IGNORECASE),
]

# Sections most likely to state the convention once, rather than next to
# every individual number -- checked first.
PRIORITY_SECTION_TYPES = ("definitions", "terms", "performance_summary", "fees_and_expenses")


def _scan_text_for_basis(text: str):
    for pattern in NET_PATTERNS:
        m = pattern.search(text)
        if m:
            return "net", m.group(0)
    for pattern in GROSS_PATTERNS:
        m = pattern.search(text)
        if m:
            return "gross", m.group(0)
    return None, None


def infer_irr_basis(pages: List[Page], layout: Optional[DocumentLayout]) -> Optional[dict]:
    """Infer the document-wide gross/net return convention.

    Convention is often stated once -- in a Definitions/Terms/Performance
    Summary section -- rather than repeated next to every number. This scans
    full section text (prioritizing those sections) before falling back to
    a whole-document, page-by-page scan for documents with no detected
    sections (e.g. plain-text inputs).
    """
    if layout and layout.sections:
        ordered_sections = sorted(
            layout.sections,
            key=lambda s: (s.canonical_type not in PRIORITY_SECTION_TYPES, s.page_start),
        )
        for section in ordered_sections:
            basis, snippet = _scan_text_for_basis(section.text)
            if basis:
                return {
                    "basis": basis,
                    "snippet": snippet,
                    "page": section.page_start,
                    "section": section.title,
                }

    for page in pages:
        basis, snippet = _scan_text_for_basis(page.text or "")
        if basis:
            return {
                "basis": basis,
                "snippet": snippet,
                "page": page.page_num,
                "section": None,
            }

    return None
