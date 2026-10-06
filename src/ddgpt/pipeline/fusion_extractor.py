from __future__ import annotations

from pathlib import Path

from ddgpt.extract.tables.financial_table_parser import FinancialTableParser
from ddgpt.pipeline.scoring import compute_agreement
from ddgpt.provenance.evidence import Evidence
from ddgpt.layout.definitions import infer_irr_basis
from ddgpt.layout.irr_mentions import find_irr_mentions
from ddgpt.extract.schemas import DefinitionContext, MetricEntry, sync_legacy_fields, SCHEMA_FINGERPRINT
from ddgpt.extract.evidence import get_page_text, classify_evidence_match, EVIDENCE_SCORE_BY_MATCH
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

        base = self._reconcile(results, pages)

        self._apply_table_fallback(base, doc_name, tables)

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

    def _apply_table_fallback(self, base, doc_name, tables):
        """Table-sourced values are a fallback of last resort: only used to
        fill a metric name no extractor produced at all, never competing on
        trust-weighted score the way the extractor ensemble does in
        _pick_best_metric_entry. Generalizes what was previously a
        hand-written block for exactly aum/tvpi/net_irr (the old
        TABLE_METRIC_FIELDS mapping) to every metric parse_metrics_open
        finds."""
        present_names = {m.name for m in base.metrics}

        for entry in self.table_parser.parse_metrics_open(tables):
            if entry["name"] in present_names:
                continue  # an extractor already found this metric -- the
                # table value is redundant, not recorded as a competing
                # candidate, matching this fallback's "last resort" intent.

            base.metrics.append(MetricEntry(
                name=entry["name"],
                raw_label=entry["raw_label"],
                unit=entry["unit"],
                value=entry["value"],
                confidence=entry["confidence"],
                is_custom=entry["is_custom"],
                evidence=Evidence(doc_name=doc_name, page=entry["page"], snippet=entry["snippet"]),
            ))
            present_names.add(entry["name"])

            self._record_table_candidate(base, entry["name"], entry)

            if entry["footnotes"]:
                base.notes.append(
                    f"{entry['name']}: sourced from table {entry['table_id']} "
                    f"with linked footnote(s): {'; '.join(entry['footnotes'])}"
                )

        sync_legacy_fields(base)

    def _extract_charts_with_cache(self, doc_name, path):
        if not self.enable_disk_cache:
            return self.chart_extractor.extract_charts(doc_name, path)

        file_bytes = Path(path).read_bytes()
        key = content_hash(
            "VisionChartExtractor",
            str(getattr(self.chart_extractor, "model", "")),
            str(getattr(self.chart_extractor, "prompt_text", "")),
            SCHEMA_FINGERPRINT,
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
        model/prompt config + page text + the current schema's field
        fingerprint. Skips a Cohere/Ollama call entirely (the expensive,
        costly part) when the same document has already been processed
        with the same prompt/model -- not just the CPU-bound parsing steps.
        The fingerprint ensures a schema change (a field added/renamed on
        ExtractedDoc or MetricEntry, say) naturally misses every old cache
        entry instead of pickle silently restoring an object missing that
        field -- see schemas.SCHEMA_FINGERPRINT."""
        if not self.enable_disk_cache:
            return extractor.extract(doc_name, pages)

        page_blob = "\n".join(p.text or "" for p in pages)
        key = content_hash(
            extractor.__class__.__name__,
            str(getattr(extractor, "model", "")),
            str(getattr(extractor, "temperature", "")),
            str(getattr(extractor, "prompt_text", "")),
            SCHEMA_FINGERPRINT,
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

    def _find_metric(self, doc, name):
        for m in doc.metrics:
            if m.name == name:
                return m
        return None

    def _evidence_discount(self, entry, pages):
        """Multiplier applied to a candidate's ranking score based on how
        its evidence.snippet holds up against the real cited page text --
        so a well-cited competing candidate wins over an ungrounded one
        even when its raw self-reported confidence is nominally lower. Does
        NOT touch the persisted confidence of whichever entry ultimately
        wins. That's postprocess.verify_metric's job, applied once to the
        single winner. `pages` is optional (defaults to a neutral 1.0, no
        discount) so callers that reconcile without real page text --
        existing tests included -- see unchanged behavior."""
        if not pages:
            return 1.0
        page_text = get_page_text(pages, entry.evidence.page)
        match = classify_evidence_match(entry.evidence.snippet, page_text)
        return EVIDENCE_SCORE_BY_MATCH[match.label]

    def _pick_best_metric_entry(self, name, docs, pages=None):
        """Generalized counterpart to the old _pick_best_metric: instead of
        getattr(doc, metric_name) against a fixed set of six named
        attributes, looks up a MetricEntry by name in each extractor's
        (dual-written, Phase 1) `metrics` list. An extractor that never
        produced this name at all is simply absent from consideration here
        -- unlike the old fixed-six behavior, there's no synthetic
        null-valued candidate for every extractor against every name, since
        for a fully open metric set that would conflate "this extractor
        looked and found nothing" with "this extractor has no notion of
        this metric" (see the Phase 2 plan for why this is the deliberate
        choice, not an oversight)."""
        present = [
            (extractor_name, entry)
            for extractor_name, doc in docs
            for entry in [self._find_metric(doc, name)]
            if entry is not None
        ]

        values = [entry.value for _, entry in present]
        agreement = compute_agreement(values)

        candidates = []
        best_score = -1
        best_entry = None
        best_extractor = None

        for extractor_name, entry in present:
            weight = self.extractor_weights.get(
                extractor_name,
                self.extractor_default_weight
            )

            score = entry.confidence * weight * self._evidence_discount(entry, pages)

            candidates.append({
                "extractor": extractor_name,
                "value": entry.value,
                "confidence": entry.confidence,
                "weight": weight,
                "score": score,
                "evidence": {
                    "page": entry.evidence.page,
                    "snippet": entry.evidence.snippet,
                },
                "winner": False,
            })

            if score > best_score:
                best_score = score
                best_entry = entry
                best_extractor = extractor_name

        for candidate in candidates:
            if candidate["extractor"] == best_extractor:
                candidate["winner"] = True

        distinct_values = {v for v in values if v is not None}
        disagreement = None
        if len(distinct_values) > 1 and agreement < DISAGREEMENT_THRESHOLD:
            disagreement = {
                "field": name,
                "values": {extractor_name: entry.value for extractor_name, entry in present},
                "agreement": agreement,
            }

        winner = None
        if best_entry is not None:
            winner = MetricEntry(
                name=best_entry.name,
                raw_label=best_entry.raw_label,
                unit=best_entry.unit,
                value=best_entry.value,
                basis=best_entry.basis,
                confidence=best_entry.confidence,
                agreement=agreement,
                is_custom=best_entry.is_custom,
                needed_retry=best_entry.needed_retry,
                evidence=best_entry.evidence,
            )

        return winner, disagreement, candidates

    def _reconcile(self, docs, pages=None):
        base = docs[0][1]

        all_names = sorted({m.name for _, doc in docs for m in doc.metrics})

        disagreements = []
        candidates_by_name = {}
        reconciled_metrics = []

        for name in all_names:
            winner, disagreement, candidates = self._pick_best_metric_entry(name, docs, pages)
            candidates_by_name[name] = candidates
            if disagreement:
                disagreements.append(disagreement)
            if winner is not None:
                reconciled_metrics.append(winner)

        base.extractor_disagreements = disagreements
        base.extraction_candidates = candidates_by_name
        base.metrics = reconciled_metrics

        # Every extractor's notes matter, not just whichever doc happens to
        # be `base` (docs[0], picked arbitrarily) -- e.g. an evidence-retry
        # note from Ollama would otherwise be silently dropped on any run
        # where Ollama isn't first in the extractor list.
        merged_notes = []
        for _, doc in docs:
            for note in doc.notes:
                if note not in merged_notes:
                    merged_notes.append(note)
        base.notes = merged_notes

        # Backward-compat shim -- see schemas.sync_legacy_fields. Called
        # again in _apply_table_fallback once the table fallback has had a
        # chance to add anything no extractor found at all.
        sync_legacy_fields(base)

        return base

    def _record_table_candidate(self, base, metric_name, entry):
        """Table-sourced fallback is a distinct source from the extractor
        ensemble. It is recorded as its own candidate, and any existing pseudo
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
