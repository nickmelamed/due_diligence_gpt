from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel

class Flag(BaseModel):
    severity: str
    type: str
    docs: str
    detail: str
    evidence: str
    why_it_matters: str
    question_to_ask: str

class Rule(ABC):
    @abstractmethod
    def apply(self, extracted: List[dict]) -> List[Flag]:
        raise NotImplementedError
