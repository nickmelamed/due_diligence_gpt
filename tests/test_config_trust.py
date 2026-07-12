from ddgpt.config import Config
from ddgpt.extract.schemas import ExtractedDoc, Metric
from ddgpt.pipeline.fusion_extractor import FusionExtractor
from ddgpt.extract.postprocess import authority_weight


def test_fusion_extractor_uses_configured_weights_not_hardcoded_defaults():
    cfg = Config()
    cfg.trust.extractor_weights = {"RegexExtractor": 0.10, "CohereExtractor": 0.99}

    doc_regex = ExtractedDoc(doc_name="x")
    doc_regex.aum = Metric(value=1.0e9, confidence=0.9)  # would win under default weights

    doc_cohere = ExtractedDoc(doc_name="x")
    doc_cohere.aum = Metric(value=2.0e9, confidence=0.9)

    fe = FusionExtractor(
        extractors=[],
        extractor_weights=cfg.trust.extractor_weights,
        extractor_default_weight=cfg.trust.extractor_default_weight,
    )
    result = fe._reconcile([("RegexExtractor", doc_regex), ("CohereExtractor", doc_cohere)])

    # With the configured weights inverted from the defaults, Cohere should
    # now win despite Regex normally being trusted more.
    assert result.aum.value == 2.0e9


def test_authority_weight_uses_configured_dict():
    cfg = Config()
    cfg.trust.authority_weights = {"sidecar": 0.99}

    weight = authority_weight("Sidecar_Letter.pdf", cfg.trust.authority_weights, cfg.trust.authority_default_weight)
    assert weight == 0.99


def test_authority_weight_falls_back_to_default_when_no_match():
    cfg = Config()
    weight = authority_weight("random_file.pdf", cfg.trust.authority_weights, cfg.trust.authority_default_weight)
    assert weight == cfg.trust.authority_default_weight
