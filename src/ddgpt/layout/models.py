from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class Footnote(BaseModel):
    marker: str
    text: str
    page_num: int


class Section(BaseModel):
    title: str
    canonical_type: Optional[str] = None  # e.g. "performance_summary", "terms", "risk_factors", "definitions"
    page_start: int
    page_end: int
    text: str = ""


class DocumentLayout(BaseModel):
    sections: List[Section] = Field(default_factory=list)
    footnotes: List[Footnote] = Field(default_factory=list)

    def section_for_page(self, page_num: int) -> Optional[Section]:
        for s in self.sections:
            if s.page_start <= page_num <= s.page_end:
                return s
        return None

    def sections_of_type(self, canonical_type: str) -> List[Section]:
        return [s for s in self.sections if s.canonical_type == canonical_type]

    def canonical_types_found(self) -> List[str]:
        seen = []
        for s in self.sections:
            if s.canonical_type and s.canonical_type not in seen:
                seen.append(s.canonical_type)
        return seen
