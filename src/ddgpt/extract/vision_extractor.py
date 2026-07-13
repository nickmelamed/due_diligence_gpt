from __future__ import annotations

import base64
import logging
import time
from pathlib import Path
from typing import List

import requests

from ddgpt.extract.schemas import ChartExtraction
from ddgpt.provenance.evidence import Evidence
from ddgpt.utils.json_parser import safe_parse_json
from ddgpt.ingestion.page_render import render_pages_png

DEFAULT_OLLAMA_HOST = "http://localhost:11434"

DEFAULT_MODEL = "qwen2.5vl:7b"


DEFAULT_DPI = 150

RETRY_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 2.0


CHART_CONFIDENCE = 0.60

logger = logging.getLogger("ddgpt")


def ollama_vision_is_available(host: str = DEFAULT_OLLAMA_HOST, model: str = DEFAULT_MODEL, timeout: float = 2.0) -> bool:
    """Reachability + model-pulled check, mirroring ollama_extractor's
    ollama_is_available -- but this also confirms the specific vision model
    has actually been pulled, since an unpulled model fails per-page instead
    of at pipeline build time."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return False
        installed = {
            m.get("name", "").split(":")[0]
            for m in resp.json().get("models", [])
        }
        return model.split(":")[0] in installed
    except requests.RequestException:
        return False


class OllamaVisionExtractor:
    """Detects and extracts data from charts/graphs embedded as images on PDF
    pages, via a locally-running vision-capable model (e.g. qwen2.5vl).

    Distinct from table extraction (Camelot/pdfplumber, which reads ruled/
    whitespace-aligned tabular structures) and from OCR (which reads plain
    text off a scanned page) -- this targets bar/line/pie/area/scatter
    charts that carry no extractable text layer at all.
    """
    
    IS_LLM_BACKED = True

    def __init__(
        self,
        prompt_text: str,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
        temperature: float = 0.0,
        dpi: int = DEFAULT_DPI,
        max_pages: int = 20,
    ):
        self.prompt_text = prompt_text
        self.model = model
        self.host = host
        self.temperature = temperature
        self.dpi = dpi
        self.max_pages = max_pages

    def extract_charts(self, doc_name: str, path: str) -> List[dict]:
        if Path(path).suffix.lower() != ".pdf":
            return []

        try:
            page_images = render_pages_png(path, dpi=self.dpi)
        except Exception as e:
            logger.error(f"vision_extract doc={doc_name} status=error stage=render error={e!r}")
            return []

        page_numbers = sorted(page_images)[: self.max_pages]
        if len(page_images) > self.max_pages:
            logger.info(
                f"vision_extract doc={doc_name} pages_total={len(page_images)} "
                f"pages_processed={len(page_numbers)} (max_pages cap)"
            )

        results = []
        for page_num in page_numbers:
            results.extend(self._extract_page(doc_name, page_num, page_images[page_num]))
        return results

    def _extract_page(self, doc_name: str, page_num: int, png_bytes: bytes) -> List[dict]:
        """Returns a list because a single page can legitimately contain
        multiple charts (e.g. a bar chart next to a separate pie chart) --
        confirmed with a real document during development, where an earlier
        single-chart-per-page schema silently dropped the second chart."""
        b64 = base64.b64encode(png_bytes).decode("ascii")

        last_error = None

        for attempt in range(RETRY_ATTEMPTS):
            call_start = time.perf_counter()
            try:
                resp = requests.post(
                    f"{self.host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": self.prompt_text,
                        "images": [b64],
                        "options": {"temperature": self.temperature},
                        "format": "json",
                        "stream": False,
                    },
                    timeout=180,
                )
                resp.raise_for_status()
                latency = time.perf_counter() - call_start

                text = resp.json()["response"].strip()
                data = safe_parse_json(text)

                charts = data.get("charts", [])
                if not isinstance(charts, list):
                    charts = []

                extractions = []
                for chart in charts:
                    if not isinstance(chart, dict):
                        continue

                    series = [
                        {"label": str(s.get("label", "")), "value": s.get("value")}
                        for s in chart.get("series", [])
                        if isinstance(s, dict)
                    ]

                    title = chart.get("title")
                    summary = chart.get("summary", "") or ""

                    extraction = ChartExtraction(
                        page=page_num,
                        chart_type=chart.get("chart_type"),
                        title=title,
                        x_label=chart.get("x_label"),
                        y_label=chart.get("y_label"),
                        series=series,
                        summary=summary,
                        confidence=CHART_CONFIDENCE,
                        evidence=Evidence(
                            doc_name=doc_name,
                            page=page_num,
                            snippet=(title or summary)[:200],
                        ),
                    )
                    extractions.append(extraction.dict())

                logger.info(
                    f"llm_call provider=ollama_vision model={self.model} doc={doc_name} "
                    f"page={page_num} attempt={attempt + 1} status=ok latency_s={latency:.3f} "
                    f"charts_found={len(extractions)}"
                )
                return extractions

            except Exception as e:
                latency = time.perf_counter() - call_start
                last_error = e
                logger.warning(
                    f"llm_call provider=ollama_vision model={self.model} doc={doc_name} "
                    f"page={page_num} attempt={attempt + 1} status=error latency_s={latency:.3f} error={e!r}"
                )
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))

        logger.error(
            f"llm_call provider=ollama_vision model={self.model} doc={doc_name} "
            f"page={page_num} status=exhausted attempts={RETRY_ATTEMPTS} last_error={last_error!r}"
        )
        return []
