from __future__ import annotations

from ddgpt.extract.tables.financial_table_parser import FinancialTableParser
from ddgpt.pipeline.scoring import compute_agreement
from ddgpt.provenance.evidence import Evidence
from ddgpt.layout.definitions import infer_irr_basis
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
                 cache_dir=None, enable_disk_cache=False):
        self.extractors = extractors

        self.table_parser = FinancialTableParser()

        self.extractor_weights = extractor_weights or DEFAULT_EXTRACTOR_WEIGHTS
        self.extractor_default_weight = extractor_default_weight

        self.cache_dir = cache_dir
        self.enable_disk_cache = enable_disk_cache and cache_dir is not None

    def extract(self, doc_name, pages, tables, layout=None, redact_for_llm=False):
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

            if entry["footnotes"]:
                base.notes.append(
                    f"{metric_name}: sourced from table {entry['table_id']} "
                    f"with linked footnote(s): {'; '.join(entry['footnotes'])}"
                )

        base.net_irr_basis = self._build_definition_context(pages, layout)

        if layout is not None:
            base.sections_detected = layout.canonical_types_found()

        return base

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

            if score > best_score:
                best_score = score
                best_metric = metric
                best_extractor = extractor_name

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

        return best_metric, disagreement

    def _reconcile(self, docs):
        base = docs[0][1]

        disagreements = []

        for metric_name in ("aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"):
            metric, disagreement = self._pick_best_metric(metric_name, docs)
            setattr(base, metric_name, metric)
            if disagreement:
                disagreements.append(disagreement)

        base.extractor_disagreements = disagreements

        return base
