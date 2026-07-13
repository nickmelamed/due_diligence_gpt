from ddgpt.extract.schemas import ExtractedDoc, Metric
from ddgpt.provenance.evidence import Evidence
from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.rules.extractor_disagreement import ExtractorDisagreementRule


def _doc_with_aum(value, confidence):
    doc = ExtractedDoc(doc_name="test.pdf")
    doc.aum = Metric(value=value, confidence=confidence, evidence=Evidence(doc_name="test.pdf", page=1, snippet="x"))
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
    # every extractor returned None for AUM, but the pre-existing tie-break
    # logic still marks a (null-valued) pseudo-winner -- the table fallback
    # must demote it rather than leaving two "winners" in the trail.
    assert base.extraction_candidates["aum"][0]["winner"] is True
    assert base.extraction_candidates["aum"][0]["value"] is None

    fe._record_table_candidate(base, "aum", {
        "value": 1.30e9, "page": 2, "table_id": "t1", "snippet": "AUM $1.30B", "footnotes": [],
    })

    candidates = base.extraction_candidates["aum"]
    winners = [c for c in candidates if c["winner"]]

    assert len(winners) == 1
    assert winners[0]["extractor"] == "TableParser"
    assert winners[0]["value"] == 1.30e9
