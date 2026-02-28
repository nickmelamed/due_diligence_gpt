from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional

class Evidence(BaseModel):
    doc_name: str
    page: Optional[int] = None
    snippet: str = Field(default="")
