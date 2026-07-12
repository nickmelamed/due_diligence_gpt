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
