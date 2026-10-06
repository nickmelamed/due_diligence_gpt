from __future__ import annotations
import json
import logging
import os
import time
from typing import List

from ddgpt.io.loaders import Page
from ddgpt.extract.base import Extractor
from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.utils.json_parser import safe_parse_json
from ddgpt.extract.regex_extractor import RegexExtractor
from ddgpt.extract.llm_common import (
    chunk_pages,
    build_schema_hint,
    build_known_metrics_hint,
    sanitize_extraction,
    merge_chunk_docs,
    extract_with_evidence_retry,
)

try:
    import cohere
except Exception:
    cohere = None  # type: ignore[assignment]  # optional dependency

# Conservative character budget per call. Long LPAs/quarterly reports can run
# well past a single context window; rather than silently truncating (and
# losing whatever field lives past the cutoff), the document is split into
# page-aligned chunks and results are merged field-by-field.
MAX_CHARS_PER_CALL = 60_000

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0

logger = logging.getLogger("ddgpt")

class CohereExtractor(Extractor):
    # Marks this extractor as sending document text to a third-party API,
    # so the pipeline knows to redact sensitive identifiers first when
    # cfg.run.redact_before_llm is enabled (see ddgpt.utils.redaction).
    IS_LLM_BACKED = True

    def __init__(self, model: str, temperature: float, prompt_text: str, enable_evidence_retry: bool = True):
        if cohere is None:
            raise RuntimeError("cohere not installed. pip install -r requirements.txt")
        api_key = os.getenv("CO_API_KEY")
        if not api_key:
            raise RuntimeError("CO_API_KEY env var not set.")
        self.client = cohere.Client(api_key)
        self.model = model
        self.temperature = temperature
        self.prompt_text = prompt_text
        self.enable_evidence_retry = enable_evidence_retry

    def extract(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        chunks = chunk_pages(pages, MAX_CHARS_PER_CALL)

        if len(chunks) == 1:
            return self._extract_chunk(doc_name, chunks[0])

        chunk_docs = [self._extract_chunk(doc_name, chunk) for chunk in chunks]
        return merge_chunk_docs(doc_name, chunk_docs, source_label="Cohere")

    def _extract_chunk(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        return extract_with_evidence_retry(
            pages,
            lambda: self._extract_chunk_attempt(doc_name, pages),
            enable_retry=self.enable_evidence_retry,
            doc_name=doc_name,
        )

    def _extract_chunk_attempt(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        pages_block = "\n\n".join([f"--- PAGE {p.page_num} ---\n{p.text}" for p in pages])

        msg = f"""{self.prompt_text}

{build_known_metrics_hint()}

SCHEMA EXAMPLE (shape only):
{json.dumps(build_schema_hint(doc_name))}

DOCUMENT:
{pages_block}
""".strip()

        last_error = None

        for attempt in range(RETRY_ATTEMPTS):
            call_start = time.perf_counter()
            try:
                resp = self.client.chat(model=self.model,
                                        message=msg,
                                        temperature=self.temperature)
                latency = time.perf_counter() - call_start
                logger.info(
                    f"llm_call provider=cohere model={self.model} doc={doc_name} "
                    f"attempt={attempt + 1} status=ok latency_s={latency:.3f}"
                )

                text = resp.text.strip()

                data = safe_parse_json(text)
                data = sanitize_extraction(data)
                # doc_name must always be the real filename
                data["doc_name"] = doc_name

                return ExtractedDoc.model_validate(data)

            except Exception as e:
                latency = time.perf_counter() - call_start
                last_error = e
                logger.warning(
                    f"llm_call provider=cohere model={self.model} doc={doc_name} "
                    f"attempt={attempt + 1} status=error latency_s={latency:.3f} error={e!r}"
                )

                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))

        logger.error(
            f"llm_call provider=cohere model={self.model} doc={doc_name} "
            f"status=exhausted attempts={RETRY_ATTEMPTS} last_error={last_error!r} "
            f"fallback=regex"
        )
        doc = RegexExtractor().extract(doc_name, pages)
        doc.notes.append(
            f"Cohere extraction failed after {RETRY_ATTEMPTS} attempts ({last_error}); "
            f"used regex-only fallback for this document/chunk."
        )
        return doc
