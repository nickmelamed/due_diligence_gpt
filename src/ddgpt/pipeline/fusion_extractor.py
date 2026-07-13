from __future__ import annotations

from pathlib import Path

from ddgpt.extract.tables.financial_table_parser import FinancialTableParser
from ddgpt.pipeline.scoring import compute_agreement
from ddgpt.provenance.evidence import Evidence
from ddgpt.layout.definitions import infer_irr_basis
from ddgpt.layout.irr_mentions import find_irr_mentions
from ddgpt.extract.schemas import DefinitionContext
from ddgpt.utils.redaction import redact_pages
from ddgpt.utils.cache import disk_cached, content_hash

DEFAULT_EXTRACTOR_WEIGHTS = {
    "RegexExtractor": 0.95,
    "CohereExtractor": 0.70,
    "OllamaExtractor": 0.60,
}

# Below this agreement score, two extractors are treated as having actively
# contradicted each other (not just differed in confidence) and a
# EXTRACTOR_DISAGREEMENT flag is raised, separate from cross-document
# mismatch flags.
DISAGREEMENT_THRESHOLD = 0.85

TABLE_METRIC_FIELDS = {
    "aum": "aum",
    "tvpi": "tvpi",
    "irr": "net_irr",
}

class FusionExtractor:
    def __init__(self, extractors, extractor_weights=None, extractor_default_weight=0.50,
                 cache_dir=None, enable_disk_cache=False, chart_extractor=None):
        self.extractors = extractors

        self.table_parser = FinancialTableParser()
        self.chart_extractor = chart_extractor

        self.extractor_weights = extractor_weights or DEFAULT_EXTRACTOR_WEIGHTS
        self.extractor_default_weight = extractor_default_weight

        self.cache_dir = cache_dir
        self.enable_disk_cache = enable_disk_cache and cache_dir is not None

    def extract(self, doc_name, pages, tables, layout=None, redact_for_llm=False, path=None):
        results = []

        redacted_pages = redact_pages(pages) if redact_for_llm else pages

        for extractor in self.extractors:
            is_llm_backed = getattr(extractor, "IS_LLM_BACKED", False)
            extractor_pages = redacted_pages if is_llm_backed else pages

            doc = self._extract_with_cache(extractor, doc_name, extractor_pages)

            results.append(
                (extractor.__class__.__name__, doc)
            )

        base = self._reconcile(results)

        table_metrics = self.table_parser.parse_metrics(tables)

        for table_field, metric_name in TABLE_METRIC_FIELDS.items():
            entry = table_metrics.get(table_field)
            if entry is None:
                continue

            metric = getattr(base, metric_name)
            if metric.value is not None:
                continue

            metric.value = entry["value"]
            metric.confidence = 0.85
            metric.evidence = Evidence(
                doc_name=doc_name,
                page=entry["page"],
                snippet=entry["snippet"],
            )

            self._record_table_candidate(base, metric_name, entry)

            if entry["footnotes"]:
                base.notes.append(
                    f"{metric_name}: sourced from table {entry['table_id']} "
                    f"with linked footnote(s): {'; '.join(entry['footnotes'])}"
                )

        base.net_irr_basis = self._build_definition_context(pages, layout)
        base.irr_mentions = find_irr_mentions(pages)

        if layout is not None:
            base.sections_detected = layout.canonical_types_found()

        if self.chart_extractor is not None and path is not None:
            if redact_for_llm:
                # Unlike text (redact_pages), a page image can't be selectively
                # redacted before sending it to a vision model -- skip the
                # extractor entirely rather than leak whatever sensitive text
                # is rendered into the chart/page image.
                base.notes.append(
                    "Chart/graph extraction skipped: redact_before_llm is enabled and page "
                    "images cannot be redacted the way text can."
                )
            else:
                base.chart_extractions = self._extract_charts_with_cache(doc_name, path)

        return base

    def _extract_charts_with_cache(self, doc_name, path):
        if not self.enable_disk_cache:
            return self.chart_extractor.extract_charts(doc_name, path)

        file_bytes = Path(path).read_bytes()
        key = content_hash(
            "VisionChartExtractor",
            str(getattr(self.chart_extractor, "model", "")),
            str(getattr(self.chart_extractor, "prompt_text", "")),
            file_bytes,
        )

        return disk_cached(
            self.cache_dir,
            "chart_extractions",
            key,
            lambda: self.chart_extractor.extract_charts(doc_name, path),
        )

    def _extract_with_cache(self, extractor, doc_name, pages):
        """Caches per-extractor results on disk, keyed on extractor class +
        model/prompt config + page text. Skips a Cohere/Ollama call entirely
        (the expensive, costly part) when the same document has already been
        processed with the same prompt/model -- not just the CPU-bound
        parsing steps."""
        if not self.enable_disk_cache:
            return extractor.extract(doc_name, pages)

        page_blob = "\n".join(p.text or "" for p in pages)
        key = content_hash(
            extractor.__class__.__name__,
            str(getattr(extractor, "model", "")),
            str(getattr(extractor, "temperature", "")),
            str(getattr(extractor, "prompt_text", "")),
            page_blob,
        )

        return disk_cached(
            self.cache_dir,
            "extractions",
            key,
            lambda: extractor.extract(doc_name, pages),
        )

    def _build_definition_context(self, pages, layout):
        context = infer_irr_basis(pages, layout)
        if context is None:
            return None
        return DefinitionContext(**context)

    def _pick_best_metric(self, metric_name, docs):
        values = [getattr(doc, metric_name).value for _, doc in docs]
        agreement = compute_agreement(values)

        candidates = []
        best_score = -1
        best_metric = None
        best_extractor = None

        for extractor_name, doc in docs:
            metric = getattr(doc, metric_name)

            weight = self.extractor_weights.get(
                extractor_name,
                self.extractor_default_weight
            )

            score = metric.confidence * weight

            candidates.append({
                "extractor": extractor_name,
                "value": metric.value,
                "confidence": metric.confidence,
                "weight": weight,
                "score": score,
                "evidence": {
                    "page": metric.evidence.page,
                    "snippet": metric.evidence.snippet,
                },
                "winner": False,
            })

            if score > best_score:
                best_score = score
                best_metric = metric
                best_extractor = extractor_name

        for candidate in candidates:
            if candidate["extractor"] == best_extractor:
                candidate["winner"] = True

        if best_metric is not None:
            best_metric.agreement = agreement

        distinct_values = {v for v in values if v is not None}
        disagreement = None
        if len(distinct_values) > 1 and agreement < DISAGREEMENT_THRESHOLD:
            disagreement = {
                "field": metric_name,
                "values": {
                    extractor_name: getattr(doc, metric_name).value
                    for extractor_name, doc in docs
                    if getattr(doc, metric_name).value is not None
                },
                "agreement": agreement,
            }

        return best_metric, disagreement, candidates

    def _reconcile(self, docs):
        base = docs[0][1]

        disagreements = []
        candidates_by_field = {}

        for metric_name in ("aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"):
            metric, disagreement, candidates = self._pick_best_metric(metric_name, docs)
            setattr(base, metric_name, metric)
            candidates_by_field[metric_name] = candidates
            if disagreement:
                disagreements.append(disagreement)

        base.extractor_disagreements = disagreements
        base.extraction_candidates = candidates_by_field

        return base

    def _record_table_candidate(self, base, metric_name, entry):
        """Table-sourced fallback is a distinct source from the extractor
        ensemble; recorded as its own candidate, and any existing pseudo
        winner (an extractor that "won" a field no extractor actually found
        a value for) is demoted so exactly one candidate is ever marked the
        winner."""
        existing = base.extraction_candidates.setdefault(metric_name, [])
        for candidate in existing:
            candidate["winner"] = False

        existing.append({
            "extractor": "TableParser",
            "value": entry["value"],
            "confidence": 0.85,
            "weight": None,
            "score": None,
            "evidence": {
                "page": entry["page"],
                "snippet": entry["snippet"],
            },
            "winner": True,
        })
