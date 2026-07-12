from __future__ import annotations
import json
import os
from typing import List

from ddgpt.io.loaders import Page
from ddgpt.extract.base import Extractor
from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.utils.json_parser import safe_parse_json
from ddgpt.extract.regex_extractor import RegexExtractor

try:
    import cohere
except Exception:
    cohere = None

# Conservative character budget per call. Long LPAs/quarterly reports can run
# well past a single context window; rather than silently truncating (and
# losing whatever field lives past the cutoff), the document is split into
# page-aligned chunks and results are merged field-by-field.
MAX_CHARS_PER_CALL = 60_000

METRIC_FIELDS = ["aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"]

class CohereExtractor(Extractor):
    def __init__(self, model: str, temperature: float, prompt_text: str):
        if cohere is None:
            raise RuntimeError("cohere not installed. pip install -r requirements.txt")
        api_key = os.getenv("CO_API_KEY")
        if not api_key:
            raise RuntimeError("CO_API_KEY env var not set.")
        self.client = cohere.Client(api_key)
        self.model = model
        self.temperature = temperature
        self.prompt_text = prompt_text

    def _sanitize(self, data: dict) -> dict:
        # Ensure required top-level keys exist
        defaults = {
            "notes": [],
            "missing_fields": []
        }

        for k, v in defaults.items():
            if k not in data or data[k] is None:
                data[k] = v

        # normalize doc_date
        if isinstance(data.get("doc_date"), dict):
            data["doc_date"] = data["doc_date"].get("value")

        # normalize notes
        cleaned_notes = []
        for n in data.get("notes", []):
            if isinstance(n, str):
                cleaned_notes.append(n)
            elif isinstance(n, dict):
                cleaned_notes.append(n.get("text", str(n)))
            else:
                cleaned_notes.append(str(n))
        data["notes"] = cleaned_notes

        # normalize missing fields
        data["missing_fields"] = [str(x) for x in data.get("missing_fields", [])]

        # enforce metric structure
        metric_fields = ["aum", "net_irr", "tvpi", "target_irr"]

        for field in metric_fields:
            if field not in data or not isinstance(data[field], dict):
                data[field] = {}

            data[field].setdefault("value", None)
            data[field].setdefault("confidence", 0.0)
            data[field].setdefault("evidence", {
                "doc_name": "",
                "page": None,
                "snippet": ""
            })

        # management fee
        if "mgmt_fee" not in data or not isinstance(data["mgmt_fee"], dict):
            data["mgmt_fee"] = {}

        data["mgmt_fee"].setdefault("value", None)
        data["mgmt_fee"].setdefault("basis", None)
        data["mgmt_fee"].setdefault("confidence", 0.0)
        data["mgmt_fee"].setdefault("evidence", {
            "doc_name": "",
            "page": None,
            "snippet": ""
        })

        # carry
        if "carry" not in data or not isinstance(data["carry"], dict):
            data["carry"] = {}

        data["carry"].setdefault("value", None)
        data["carry"].setdefault("hurdle", None)
        data["carry"].setdefault("confidence", 0.0)
        data["carry"].setdefault("evidence", {
            "doc_name": "",
            "page": None,
            "snippet": ""
        })

        return data

    def extract(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        chunks = self._chunk_pages(pages)

        if len(chunks) == 1:
            return self._extract_chunk(doc_name, chunks[0])

        chunk_docs = [self._extract_chunk(doc_name, chunk) for chunk in chunks]
        return self._merge_chunks(doc_name, chunk_docs)

    def _chunk_pages(self, pages: List[Page]) -> List[List[Page]]:
        chunks: List[List[Page]] = []
        current: List[Page] = []
        current_len = 0

        for page in pages:
            page_len = len(page.text or "")
            if current and current_len + page_len > MAX_CHARS_PER_CALL:
                chunks.append(current)
                current = []
                current_len = 0
            current.append(page)
            current_len += page_len

        if current:
            chunks.append(current)

        return chunks or [pages]

    def _extract_chunk(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
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

        for attempt in range(3):
            try:
                resp = self.client.chat(model=self.model,
                                        message=msg,
                                        temperature=self.temperature)
                text = resp.text.strip()

                data = safe_parse_json(text)
                data = self._sanitize(data)
                # doc_name must always be the real filename, never whatever
                # title/name the model decided to report -- it drives
                # authority weighting and cross-document flag labeling.
                data["doc_name"] = doc_name

                return ExtractedDoc.model_validate(data)

            except Exception as e:
                print(f" Attempt {attempt + 1} failed: {e}")

                if attempt == 2:
                    print("Falling back to regex extraction")
                    return RegexExtractor().extract(doc_name, pages)

    def _merge_chunks(self, doc_name: str, chunk_docs: List[ExtractedDoc]) -> ExtractedDoc:
        merged = ExtractedDoc(doc_name=doc_name)

        for doc in chunk_docs:
            if doc.doc_date:
                merged.doc_date = doc.doc_date
                break

        for metric_name in METRIC_FIELDS:
            best = None
            for doc in chunk_docs:
                metric = getattr(doc, metric_name)
                if metric.value is None:
                    continue
                if best is None or metric.confidence > best.confidence:
                    best = metric
            if best is not None:
                setattr(merged, metric_name, best)

        notes: List[str] = []
        for doc in chunk_docs:
            for n in doc.notes:
                if n not in notes:
                    notes.append(n)
        notes.append(f"Document processed in {len(chunk_docs)} chunks due to length.")
        merged.notes = notes

        missing: List[str] = []
        for metric_name in METRIC_FIELDS:
            if getattr(merged, metric_name).value is None:
                missing.append(f"{metric_name}.value")
        if merged.carry.hurdle is None:
            missing.append("carry.hurdle")
        merged.missing_fields = missing

        return merged
