from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc

class Extractor(ABC):
    @abstractmethod
    def extract(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        raise NotImplementedError
