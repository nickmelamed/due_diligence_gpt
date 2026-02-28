from __future__ import annotations
import json
import os
import re
from typing import List

from ddgpt.io.loaders import Page
from ddgpt.extract.base import Extractor
from ddgpt.extract.schemas import ExtractedDoc

try:
    import cohere
except Exception:
    cohere = None

class CohereExtractor(Extractor):
    def __init__(self, model: str, temperature: float, prompt_text: str):
        if cohere is None:
            raise RuntimeError("cohere not installed. pip install -r requirements.txt")
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError("COHERE_API_KEY env var not set.")
        self.client = cohere.Client(api_key)
        self.model = model
        self.temperature = temperature
        self.prompt_text = prompt_text

    def extract(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        pages_block = "\n\n".join([f"--- PAGE {p.page_num} ---\n{p.text}" for p in pages])

        schema_hint = {
            "doc_name": doc_name,
            "doc_date": None,
            "aum": {"value": None, "confidence": 0.0, "evidence": {"doc_name": doc_name, "page": None, "snippet": ""}},
            "net_irr": {"value": None, "confidence": 0.0, "evidence": {"doc_name": doc_name, "page": None, "snippet": ""}},
            "tvpi": {"value": None, "confidence": 0.0, "evidence": {"doc_name": doc_name, "page": None, "snippet": ""}},
            "target_irr": {"value": None, "confidence": 0.0, "evidence": {"doc_name": doc_name, "page": None, "snippet": ""}},
            "mgmt_fee": {"value": None, "basis": None, "confidence": 0.0, "evidence": {"doc_name": doc_name, "page": None, "snippet": ""}},
            "carry": {"value": None, "hurdle": None, "confidence": 0.0, "evidence": {"doc_name": doc_name, "page": None, "snippet": ""}},
            "notes": [],
            "missing_fields": []
        }

        msg = f"""{self.prompt_text}

SCHEMA EXAMPLE (shape only):
{json.dumps(schema_hint)}

DOCUMENT:
{pages_block}
""".strip()

        resp = self.client.chat(model=self.model, message=msg, temperature=self.temperature)
        text = resp.text.strip()

        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise ValueError("Could not parse JSON from Cohere response.")
        data = json.loads(m.group(0))
        return ExtractedDoc.model_validate(data)
