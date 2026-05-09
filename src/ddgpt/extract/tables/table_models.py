from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class ExtractedTable(BaseModel):
    table_id: str

    page: int

    headers: List[str] = Field(default_factory=list)

    rows: List[Dict[str, str]] = Field(default_factory=list)

    raw_text: str = ""

    confidence: float = 0.0