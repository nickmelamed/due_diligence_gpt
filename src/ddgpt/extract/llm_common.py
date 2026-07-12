from __future__ import annotations
from typing import List

from ddgpt.io.loaders import Page
from ddgpt.extract.schemas import ExtractedDoc

# Shared between every LLM-backed extractor (Cohere, Ollama, ...): the
# structured-extraction schema hint, chunking for long documents, sanitizing
# a model's raw JSON, and merging per-chunk results back into one doc.

METRIC_FIELDS = ["aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"]


def chunk_pages(pages: List[Page], max_chars: int) -> List[List[Page]]:
    chunks: List[List[Page]] = []
    current: List[Page] = []
    current_len = 0

    for page in pages:
        page_len = len(page.text or "")
        if current and current_len + page_len > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(page)
        current_len += page_len

    if current:
        chunks.append(current)

    return chunks or [pages]


def build_schema_hint(doc_name: str) -> dict:
    return {
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


def sanitize_extraction(data: dict) -> dict:
    defaults = {
        "notes": [],
        "missing_fields": []
    }

    for k, v in defaults.items():
        if k not in data or data[k] is None:
            data[k] = v

    if isinstance(data.get("doc_date"), dict):
        data["doc_date"] = data["doc_date"].get("value")

    cleaned_notes = []
    for n in data.get("notes", []):
        if isinstance(n, str):
            cleaned_notes.append(n)
        elif isinstance(n, dict):
            cleaned_notes.append(n.get("text", str(n)))
        else:
            cleaned_notes.append(str(n))
    data["notes"] = cleaned_notes

    data["missing_fields"] = [str(x) for x in data.get("missing_fields", [])]

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


def merge_chunk_docs(doc_name: str, chunk_docs: List[ExtractedDoc], source_label: str) -> ExtractedDoc:
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
    notes.append(f"Document processed in {len(chunk_docs)} chunks due to length ({source_label}).")
    merged.notes = notes

    missing: List[str] = []
    for metric_name in METRIC_FIELDS:
        if getattr(merged, metric_name).value is None:
            missing.append(f"{metric_name}.value")
    if merged.carry.hurdle is None:
        missing.append("carry.hurdle")
    merged.missing_fields = missing

    return merged
