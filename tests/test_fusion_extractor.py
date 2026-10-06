from ddgpt.extract.schemas import ExtractedDoc, Metric, MetricEntry
from ddgpt.extract.tables.financial_table_parser import FinancialTableParser
from ddgpt.provenance.evidence import Evidence
from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.rules.extractor_disagreement import ExtractorDisagreementRule


def _doc_with_aum(value, confidence):
    doc = ExtractedDoc(doc_name="test.pdf")
    evidence = Evidence(doc_name="test.pdf", page=1, snippet="x")
    doc.aum = Metric(value=value, confidence=confidence, evidence=evidence)
    # _reconcile now reconciles from `metrics` (Phase 2), not the legacy
    # attribute directly -- a real extractor always dual-writes both (see
    # RegexExtractor/llm_common.py), so this fixture must too.
    doc.metrics = [
        MetricEntry(name="aum", raw_label="AUM", unit="usd", value=value, confidence=confidence, evidence=evidence)
    ]
    return doc


def test_agreeing_extractors_produce_no_disagreement_flag():
    doc_a = _doc_with_aum(1.20e9, 0.55)
    doc_b = _doc_with_aum(1.21e9, 0.60)  # within tolerance

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])

    assert result.aum.agreement == 1.0
    assert result.extractor_disagreements == []


def test_contradicting_extractors_flagged_distinctly_from_cross_document_mismatch():
    doc_a = _doc_with_aum(1.20e9, 0.55)
    doc_b = _doc_with_aum(1.80e9, 0.60)  # materially different, not just noisy

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])

    assert result.aum.agreement < 0.85
    assert len(result.extractor_disagreements) == 1
    assert result.extractor_disagreements[0]["field"] == "aum"

    flags = ExtractorDisagreementRule().apply([result.dict()])
    assert len(flags) == 1
    assert flags[0].type == "EXTRACTOR_DISAGREEMENT"
    # Must not collide with NumericMismatchRule's cross-document flag type.
    assert flags[0].type != "AUM_MISMATCH"


def test_higher_weighted_extractor_wins_reconciliation():
    doc_regex = _doc_with_aum(1.20e9, 0.55)   # RegexExtractor: 0.55 * 0.95 = 0.5225
    doc_cohere = _doc_with_aum(1.25e9, 0.60)  # CohereExtractor: 0.60 * 0.70 = 0.42

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_regex), ("CohereExtractor", doc_cohere)])

    assert result.aum.value == 1.20e9


def test_candidates_recorded_for_every_field_not_just_disagreements():
    doc_a = _doc_with_aum(1.20e9, 0.55)
    doc_b = _doc_with_aum(1.21e9, 0.60)  # agrees -- previously would be discarded entirely

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])

    aum_candidates = result.extraction_candidates["aum"]
    assert len(aum_candidates) == 2

    by_extractor = {c["extractor"]: c for c in aum_candidates}
    assert by_extractor["RegexExtractor"]["value"] == 1.20e9
    assert by_extractor["CohereExtractor"]["value"] == 1.21e9

    winners = [c for c in aum_candidates if c["winner"]]
    assert len(winners) == 1
    assert winners[0]["extractor"] == "RegexExtractor"  # higher score: 0.55*0.95 > 0.60*0.70


def test_candidates_include_score_math_for_reproducibility():
    doc_a = _doc_with_aum(1.20e9, 0.55)

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a)])

    candidate = result.extraction_candidates["aum"][0]
    assert candidate["confidence"] == 0.55
    assert candidate["weight"] == 0.95
    assert candidate["score"] == 0.55 * 0.95
    assert candidate["evidence"]["snippet"] == "x"


def test_table_fallback_recorded_as_distinct_candidate_and_sole_winner():
    doc_a = ExtractedDoc(doc_name="test.pdf")  # no extractor found AUM at all

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95}
    fe.extractor_default_weight = 0.50

    base = fe._reconcile([("RegexExtractor", doc_a)])
    # No extractor produced an "aum" entry at all (Phase 2: reconciliation
    # is driven by the dynamic set of names actually present in `metrics`,
    # not a fixed six with a synthetic null candidate for every extractor)
    # -- so there's no candidates list for "aum" yet until the table
    # fallback adds one.
    assert "aum" not in base.extraction_candidates

    fe._record_table_candidate(base, "aum", {
        "value": 1.30e9, "page": 2, "table_id": "t1", "snippet": "AUM $1.30B", "footnotes": [],
    })

    candidates = base.extraction_candidates["aum"]
    winners = [c for c in candidates if c["winner"]]

    assert len(winners) == 1
    assert winners[0]["extractor"] == "TableParser"
    assert winners[0]["value"] == 1.30e9


def test_reconcile_unions_open_metrics_from_every_extractor():
    # `base` is arbitrarily docs[0][1] -- without reconciling over the union
    # of every extractor's dual-written `metrics` names, whichever extractor
    # wasn't picked as `base` would have its open-metric contributions
    # silently dropped, even though the legacy named fields above are
    # correctly fused across all extractors.
    doc_a = _doc_with_aum(1.20e9, 0.55)
    doc_a.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.45, confidence=0.8)]

    doc_b = _doc_with_aum(1.21e9, 0.60)
    doc_b.metrics = [MetricEntry(name="rvpi", raw_label="RVPI", unit="multiple", value=1.10, confidence=0.7)]

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])

    names = {m.name for m in result.metrics}
    assert names == {"dpi", "rvpi"}


def test_reconcile_dedupes_dynamic_metric_by_trust_weighted_score():
    # Two extractors both find "dpi" (a non-legacy metric) with different
    # values -- Phase 2 must pick one winner by the same trust-weighted
    # scoring the six legacy fields already get, not just concatenate both.
    doc_a = ExtractedDoc(doc_name="test.pdf")
    doc_a.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.40, confidence=0.55)]

    doc_b = ExtractedDoc(doc_name="test.pdf")
    doc_b.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.45, confidence=0.60)]

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])

    dpi_entries = [m for m in result.metrics if m.name == "dpi"]
    assert len(dpi_entries) == 1
    assert dpi_entries[0].value == 0.40  # RegexExtractor: 0.55*0.95=0.5225 > CohereExtractor: 0.60*0.70=0.42


def test_reconcile_flags_disagreement_for_dynamic_metric_not_just_legacy_six():
    doc_a = ExtractedDoc(doc_name="test.pdf")
    doc_a.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.40, confidence=0.9)]

    doc_b = ExtractedDoc(doc_name="test.pdf")
    doc_b.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.90, confidence=0.9)]

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])

    assert len(result.extractor_disagreements) == 1
    assert result.extractor_disagreements[0]["field"] == "dpi"


def test_apply_table_fallback_fills_gap_for_metric_no_extractor_found():
    from ddgpt.extract.tables.table_models import ExtractedTable

    base = ExtractedDoc(doc_name="test.pdf")

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.table_parser = FinancialTableParser()

    table = ExtractedTable(table_id="t1", page=1, rows=[
        {"Metric": "DPI", "Current": "0.45x"},
    ], raw_text="")

    fe._apply_table_fallback(base, "test.pdf", [table])

    names = {m.name for m in base.metrics}
    assert "dpi" in names
    assert base.extraction_candidates["dpi"][0]["extractor"] == "TableParser"


def test_apply_table_fallback_skips_metric_an_extractor_already_found():
    from ddgpt.extract.tables.table_models import ExtractedTable

    base = ExtractedDoc(doc_name="test.pdf")
    base.metrics = [MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.99, confidence=0.9)]

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.table_parser = FinancialTableParser()

    table = ExtractedTable(table_id="t1", page=1, rows=[
        {"Metric": "DPI", "Current": "0.45x"},
    ], raw_text="")

    fe._apply_table_fallback(base, "test.pdf", [table])

    dpi_entries = [m for m in base.metrics if m.name == "dpi"]
    assert len(dpi_entries) == 1
    assert dpi_entries[0].value == 0.99  # table value not used -- extractor already had it
    assert "dpi" not in base.extraction_candidates  # not recorded as a competing candidate


def test_evidence_discount_prefers_cited_candidate_over_higher_raw_confidence():
    from ddgpt.io.loaders import Page

    page_text = "Assets Under Management (AUM): $1.20B as of this reporting period."
    pages = [Page(page_num=1, text=page_text)]

    doc_ollama = ExtractedDoc(doc_name="test.pdf")  # higher raw confidence, but no citation at all
    doc_ollama.metrics = [MetricEntry(
        name="aum", raw_label="AUM", unit="usd", value=1.20e9, confidence=1.0,
        evidence=Evidence(doc_name="test.pdf", page=1, snippet=""),
    )]

    doc_regex = ExtractedDoc(doc_name="test.pdf")  # lower raw confidence, but a real verbatim citation
    doc_regex.metrics = [MetricEntry(
        name="aum", raw_label="AUM", unit="usd", value=1.20e9, confidence=0.60,
        evidence=Evidence(doc_name="test.pdf", page=1, snippet="Assets Under Management (AUM): $1.20B"),
    )]

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "OllamaExtractor": 0.60}
    fe.extractor_default_weight = 0.50

    # Without pages, ranking is undiscounted -- Ollama's 1.0*0.60=0.60 beats
    # Regex's 0.60*0.95=0.57, so the ungrounded candidate would win.
    undiscounted = fe._reconcile([("OllamaExtractor", doc_ollama), ("RegexExtractor", doc_regex)])
    winners = [c["extractor"] for c in undiscounted.extraction_candidates["aum"] if c["winner"]]
    assert winners == ["OllamaExtractor"]

    # With real page text available, Ollama's missing-snippet candidate is
    # discounted (1.0*0.60*0.50=0.30) below Regex's cited one (0.60*0.95*1.0=0.57).
    discounted = fe._reconcile(
        [("OllamaExtractor", doc_ollama), ("RegexExtractor", doc_regex)], pages
    )
    winners = [c["extractor"] for c in discounted.extraction_candidates["aum"] if c["winner"]]
    assert winners == ["RegexExtractor"]


def test_evidence_discount_neutral_when_pages_not_provided():
    doc_a = _doc_with_aum(1.20e9, 0.55)
    doc_b = _doc_with_aum(1.21e9, 0.60)

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95, "CohereExtractor": 0.70}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc_a), ("CohereExtractor", doc_b)])
    candidate = result.extraction_candidates["aum"][0]
    # Existing score math (confidence * weight, no evidence multiplier)
    # must be unchanged for every caller that doesn't pass pages.
    assert candidate["score"] == candidate["confidence"] * candidate["weight"]


def test_reconcile_aggregates_notes_from_every_extractor_not_just_base():
    # base = docs[0][1] is picked arbitrarily for non-metric fields -- a note
    # written by a *different* extractor (e.g. Ollama's evidence-retry note)
    # must not be silently dropped just because it isn't first in the list.
    doc_a = ExtractedDoc(doc_name="test.pdf")
    doc_a.notes = ["note from extractor A"]

    doc_b = ExtractedDoc(doc_name="test.pdf")
    doc_b.notes = ["note from extractor B", "note from extractor A"]  # one duplicate

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("A", doc_a), ("B", doc_b)])

    assert result.notes == ["note from extractor A", "note from extractor B"]


def test_winner_carries_needed_retry_flag_from_source_entry():
    doc = ExtractedDoc(doc_name="test.pdf")
    doc.metrics = [MetricEntry(
        name="aum", raw_label="AUM", unit="usd", value=1.2e9, confidence=0.8, needed_retry=True,
    )]

    fe = FusionExtractor.__new__(FusionExtractor)
    fe.extractor_weights = {"RegexExtractor": 0.95}
    fe.extractor_default_weight = 0.50

    result = fe._reconcile([("RegexExtractor", doc)])
    aum_entry = next(m for m in result.metrics if m.name == "aum")
    assert aum_entry.needed_retry is True
