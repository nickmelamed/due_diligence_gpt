from __future__ import annotations
import json
import logging
import time
from typing import List

import requests

from ddgpt.io.loaders import Page
from ddgpt.extract.base import Extractor
from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.utils.json_parser import safe_parse_json
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.llm_common import (
    chunk_pages,
    build_schema_hint,
    sanitize_extraction,
    merge_chunk_docs,
)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"

# Local open-weight models generally carry a smaller usable context window
# than hosted frontier models; chunk more aggressively than Cohere.
MAX_CHARS_PER_CALL = 24_000

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0

logger = logging.getLogger("ddgpt")


def ollama_is_available(host: str = DEFAULT_OLLAMA_HOST, timeout: float = 1.0) -> bool:
    """Cheap reachability check so callers can skip this extractor entirely
    (like CohereExtractor skips itself when CO_API_KEY is unset) rather than
    fail per-document once the pipeline is already running."""
    try:
        resp = requests.get(f"{host}/api/version", timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


class OllamaExtractor(Extractor):
    """Second, independent LLM extractor backed by a locally-running
    open-weight model (via Ollama). A genuinely different model family from
    Cohere's hosted model, so cross-extractor agreement reflects two
    independent readings of the document rather than two calls into the
    same underlying model.
    """

    def __init__(self, model: str, temperature: float, prompt_text: str, host: str = DEFAULT_OLLAMA_HOST):
        self.model = model
        self.temperature = temperature
        self.prompt_text = prompt_text
        self.host = host

    def extract(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        chunks = chunk_pages(pages, MAX_CHARS_PER_CALL)

        if len(chunks) == 1:
            return self._extract_chunk(doc_name, chunks[0])

        chunk_docs = [self._extract_chunk(doc_name, chunk) for chunk in chunks]
        return merge_chunk_docs(doc_name, chunk_docs, source_label="Ollama")

    def _extract_chunk(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        pages_block = "\n\n".join([f"--- PAGE {p.page_num} ---\n{p.text}" for p in pages])

        prompt = f"""{self.prompt_text}

SCHEMA EXAMPLE (shape only):
{json.dumps(build_schema_hint(doc_name))}

DOCUMENT:
{pages_block}
""".strip()

        last_error = None

        for attempt in range(RETRY_ATTEMPTS):
            call_start = time.perf_counter()
            try:
                resp = requests.post(
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "options": {"temperature": self.temperature},
                        "format": "json",
                        "stream": False,
                    },
                    timeout=180,
                )
                resp.raise_for_status()
                latency = time.perf_counter() - call_start
                logger.info(
                    f"llm_call provider=ollama model={self.model} doc={doc_name} "
                    f"attempt={attempt + 1} status=ok latency_s={latency:.3f}"
                )

                text = resp.json()["response"].strip()

                data = safe_parse_json(text)
                data = sanitize_extraction(data)
                # doc_name must always be the real filename, never whatever
                # the model decided to report.
                data["doc_name"] = doc_name

                return ExtractedDoc.model_validate(data)

            except Exception as e:
                latency = time.perf_counter() - call_start
                last_error = e
                logger.warning(
                    f"llm_call provider=ollama model={self.model} doc={doc_name} "
                    f"attempt={attempt + 1} status=error latency_s={latency:.3f} error={e!r}"
                )

                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))

        logger.error(
            f"llm_call provider=ollama model={self.model} doc={doc_name} "
            f"status=exhausted attempts={RETRY_ATTEMPTS} last_error={last_error!r} "
            f"fallback=regex"
        )
        doc = RegexExtractor().extract(doc_name, pages)
        doc.notes.append(
            f"Ollama extraction failed after {RETRY_ATTEMPTS} attempts ({last_error}); "
            f"used regex-only fallback for this document/chunk."
        )
        return doc
