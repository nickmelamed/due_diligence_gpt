from __future__ import annotations

import re
import statistics
from typing import List, Tuple

from ddgpt.layout.models import Section, Footnote

# Section headings the rest of the pipeline cares about identifying by name,
# independent of font size (decks/scans often don't carry reliable font metadata).
CANONICAL_PATTERNS = [
    ("performance_summary", re.compile(r"performance\s+(summary|highlights|overview)", re.IGNORECASE)),
    ("terms", re.compile(r"^\s*(key\s+|fund\s+)?terms\b|term\s+sheet", re.IGNORECASE)),
    ("risk_factors", re.compile(r"risk\s+(factors|considerations)", re.IGNORECASE)),
    ("definitions", re.compile(r"^\s*definitions?\b", re.IGNORECASE)),
    ("fees_and_expenses", re.compile(r"fees?\s*(and|&)?\s*expenses|^\s*fees\b", re.IGNORECASE)),
]

FOOTNOTE_MARKER_RE = re.compile(r"^\s*(\(?\d{1,2}\)?[\.\)]?|\*{1,3}|[†‡])\s+\S")

HEADING_MAX_WORDS = 12
BODY_SIZE_HEADING_RATIO = 1.15
BODY_SIZE_FOOTNOTE_RATIO = 0.90
FOOTNOTE_Y_FRAC_THRESHOLD = 0.82


def _classify_canonical(text: str) -> str | None:
    for canonical, pattern in CANONICAL_PATTERNS:
        if pattern.search(text):
            return canonical
    return None


def _is_bold(flags: int) -> bool:
    return bool(flags & (2 ** 4))


def _collect_lines(fitz_doc) -> List[dict]:
    """Flatten every text line across the document with page, size, boldness, vertical position."""
    lines = []
    for page_index, page in enumerate(fitz_doc):
        raw = page.get_text("dict")
        page_height = page.rect.height or 1.0
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                sizes = [s.get("size", 0.0) for s in spans]
                flags = [s.get("flags", 0) for s in spans]
                y0 = line["bbox"][1]
                lines.append({
                    "page_num": page_index + 1,
                    "text": text,
                    "size": max(sizes) if sizes else 0.0,
                    "bold": any(_is_bold(f) for f in flags),
                    "y_frac": y0 / page_height,
                })
    return lines


def _looks_like_heading(text: str, size: float, bold: bool, body_size: float) -> str | None:
    canonical = _classify_canonical(text)
    if canonical is not None:
        return canonical

    word_count = len(text.split())
    if word_count > HEADING_MAX_WORDS:
        return None

    is_heading_size = body_size > 0 and size >= body_size * BODY_SIZE_HEADING_RATIO
    is_heading_bold = bold and not text.endswith((".", ",", ";"))

    if is_heading_size or is_heading_bold:
        return "__generic__"

    return None


def _extract_footnote_marker(text: str) -> str:
    m = FOOTNOTE_MARKER_RE.match(text)
    if not m:
        return ""
    return m.group(1).strip("().*")


def parse_sections(fitz_doc) -> Tuple[List[Section], List[Footnote]]:
    """Reconstruct section hierarchy + footnotes from a layout-rich (PDF) document."""
    lines = _collect_lines(fitz_doc)
    if not lines:
        return [], []

    body_size = statistics.median(l["size"] for l in lines) or 10.0

    sections: List[Section] = []
    footnotes: List[Footnote] = []

    current_title = "Front Matter"
    current_canonical = None
    current_start_page = lines[0]["page_num"]
    current_text_parts: List[str] = []
    last_page_seen = current_start_page

    def close_section(end_page: int):
        sections.append(Section(
            title=current_title,
            canonical_type=current_canonical if current_canonical != "__generic__" else None,
            page_start=current_start_page,
            page_end=end_page,
            text=" ".join(current_text_parts).strip(),
        ))

    for line in lines:
        last_page_seen = line["page_num"]

        is_footnote = (
            line["y_frac"] > FOOTNOTE_Y_FRAC_THRESHOLD
            and body_size > 0
            and line["size"] < body_size * BODY_SIZE_FOOTNOTE_RATIO
            and FOOTNOTE_MARKER_RE.match(line["text"])
        )
        if is_footnote:
            footnotes.append(Footnote(
                marker=_extract_footnote_marker(line["text"]),
                text=line["text"],
                page_num=line["page_num"],
            ))
            continue

        heading = _looks_like_heading(line["text"], line["size"], line["bold"], body_size)
        if heading is not None:
            close_section(line["page_num"])
            current_title = line["text"]
            current_canonical = heading
            current_start_page = line["page_num"]
            current_text_parts = []
        else:
            current_text_parts.append(line["text"])

    close_section(last_page_seen)
    return sections, footnotes


def parse_sections_from_text(text: str, page_num: int = 1) -> Tuple[List[Section], List[Footnote]]:
    """Fallback section/footnote detection for plain-text documents with no font metadata."""
    lines = [l.strip() for l in text.splitlines()]

    sections: List[Section] = []
    footnotes: List[Footnote] = []

    current_title = "Front Matter"
    current_canonical = None
    current_text_parts: List[str] = []

    def close_section():
        sections.append(Section(
            title=current_title,
            canonical_type=current_canonical,
            page_start=page_num,
            page_end=page_num,
            text=" ".join(current_text_parts).strip(),
        ))

    for line in lines:
        if not line:
            continue

        if FOOTNOTE_MARKER_RE.match(line) and len(line.split()) <= 40:
            footnotes.append(Footnote(
                marker=_extract_footnote_marker(line),
                text=line,
                page_num=page_num,
            ))
            continue

        canonical = _classify_canonical(line)
        word_count = len(line.split())
        looks_like_heading = canonical is not None or (
            word_count <= HEADING_MAX_WORDS and (line.isupper() or line.endswith(":"))
        )

        if looks_like_heading:
            close_section()
            current_title = line
            current_canonical = canonical
            current_text_parts = []
        else:
            current_text_parts.append(line)

    close_section()
    return sections, footnotes
