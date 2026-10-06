from ddgpt.copilot.recommendation_engine import determine_recommendation


def _flag(severity):
    return {"severity": severity}


def _doc(confidences):
    return {"metrics": [
        {"name": "aum", "value": 1.0, "confidence": c} for c in confidences
    ]}


def test_two_red_flags_is_pass():
    result = determine_recommendation([_flag("RED"), _flag("RED")], [])
    assert result["decision"] == "PASS"


def test_one_red_flag_is_investigate():
    result = determine_recommendation([_flag("RED")], [])
    assert result["decision"] == "INVESTIGATE"


def test_three_yellow_flags_is_investigate():
    result = determine_recommendation([_flag("YELLOW")] * 3, [])
    assert result["decision"] == "INVESTIGATE"


def test_no_flags_is_approve():
    result = determine_recommendation([], [])
    assert result["decision"] == "APPROVE"


def test_confidence_reflects_extraction_quality_not_flag_count():
    # Same zero-flag APPROVE outcome, but two different underlying extraction
    # qualities -- confidence must track the data, not the fixed decision.
    high_quality = determine_recommendation([], [_doc([0.9, 0.85])])
    low_quality = determine_recommendation([], [_doc([0.3, 0.2])])

    assert high_quality["decision"] == low_quality["decision"] == "APPROVE"
    assert high_quality["confidence"] > low_quality["confidence"]
    assert low_quality["confidence"] == 0.25


def test_confidence_defaults_to_zero_with_no_extracted_data():
    result = determine_recommendation([], None)
    assert result["confidence"] == 0.0
