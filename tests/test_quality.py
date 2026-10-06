from ddgpt.extract.quality import metric_confidences, average_confidence, core_metric_coverage


def _doc(metrics):
    return {"metrics": metrics}


def _metric(value, confidence):
    return {"name": "aum", "value": value, "confidence": confidence}


def test_metric_confidences_skips_null_value_entries():
    extracted = [_doc([_metric(1.2e9, 0.8), _metric(None, 0.9)])]
    assert metric_confidences(extracted) == [0.8]


def test_metric_confidences_flattens_across_documents():
    extracted = [_doc([_metric(1.0, 0.6)]), _doc([_metric(2.0, 0.8)])]
    assert metric_confidences(extracted) == [0.6, 0.8]


def test_average_confidence_returns_none_when_nothing_extracted():
    assert average_confidence([]) is None
    assert average_confidence([_doc([])]) is None


def test_average_confidence_computes_mean():
    extracted = [_doc([_metric(1.0, 0.6), _metric(2.0, 0.8)])]
    assert average_confidence(extracted) == 0.7


def _named(name, value):
    return {"name": name, "value": value, "confidence": 0.9}


def test_core_coverage_counts_core_metrics_with_values():
    doc = {"metrics": [_named("aum", 1.0), _named("net_irr", 16.0), _named("hurdle_rate", 8.0)]}
    assert core_metric_coverage(doc) == (3, 7)


def test_core_coverage_ignores_custom_metrics_and_null_values():
    doc = {"metrics": [_named("aum", None), _named("gp_commitment", 5.0), _named("custom_thing", 1.0)]}
    assert core_metric_coverage(doc) == (0, 7)


def test_core_coverage_of_an_empty_document():
    assert core_metric_coverage({"metrics": []}) == (0, 7)
    assert core_metric_coverage({}) == (0, 7)
