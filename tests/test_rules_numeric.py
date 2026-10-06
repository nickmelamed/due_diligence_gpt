from ddgpt.rules.numeric_mismatch import NumericMismatchRule
from ddgpt.config import ToleranceConfig


def _doc(doc_name, metrics):
    return {"doc_name": doc_name, "metrics": metrics}


def _metric(name, unit, value, page=1, snippet=""):
    return {
        "name": name, "unit": unit, "value": value, "confidence": 0.9, "is_custom": False,
        "evidence": {"page": page, "snippet": snippet},
    }


def test_mgmt_fee_mismatch_triggers_red_with_tighter_tolerance():
    # delta 0.30 clearly exceeds mgmt_fee's overridden 0.25pt tolerance --
    # not just equal to it (see the "within tolerance" test below for that
    # boundary distinction).
    extracted = [
        _doc("Manager.pdf", [_metric("mgmt_fee", "percent", 2.00, snippet="Management Fee: 2.0%")]),
        _doc("LPA.pdf", [_metric("mgmt_fee", "percent", 1.70, snippet="Management Fee shall be 1.70%")]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)

    assert len(flags) == 1
    assert flags[0].metric == "mgmt_fee"
    assert flags[0].type == "PERCENT_MISMATCH"
    assert flags[0].severity == "RED"


def test_mgmt_fee_within_tighter_tolerance_does_not_flag():
    # 0.2 point difference is within mgmt_fee's overridden 0.25pt tolerance,
    # even though it would exceed the generic percent_abs_pts=2.0 default.
    extracted = [
        _doc("A.pdf", [_metric("mgmt_fee", "percent", 2.0)]),
        _doc("B.pdf", [_metric("mgmt_fee", "percent", 2.2)]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)
    assert flags == []


def test_aum_mismatch_uses_relative_usd_tolerance_and_is_red():
    extracted = [
        _doc("A.pdf", [_metric("aum", "usd", 1_200_000_000)]),
        _doc("B.pdf", [_metric("aum", "usd", 1_800_000_000)]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)

    assert len(flags) == 1
    assert flags[0].metric == "aum"
    assert flags[0].type == "USD_MISMATCH"
    assert flags[0].severity == "RED"


def test_target_irr_mismatch_is_yellow():
    extracted = [
        _doc("A.pdf", [_metric("target_irr", "percent", 18.0)]),
        _doc("B.pdf", [_metric("target_irr", "percent", 22.0)]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)

    assert len(flags) == 1
    assert flags[0].metric == "target_irr"
    assert flags[0].severity == "YELLOW"


def test_multiple_unit_metrics_get_cross_document_comparison():
    # A genuinely new capability -- TVPI/DPI/RVPI/MOIC never had a
    # cross-document check before this rewrite.
    extracted = [
        _doc("A.pdf", [_metric("tvpi", "multiple", 1.20)]),
        _doc("B.pdf", [_metric("tvpi", "multiple", 1.60)]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)

    assert len(flags) == 1
    assert flags[0].metric == "tvpi"
    assert flags[0].type == "MULTIPLE_MISMATCH"


def test_carry_mismatch_is_red_as_a_contractual_term():
    extracted = [
        _doc("A.pdf", [_metric("carry", "percent", 20.0)]),
        _doc("B.pdf", [_metric("carry", "percent", 25.0)]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)

    assert len(flags) == 1
    assert flags[0].severity == "RED"


def test_custom_metric_mismatch_gets_conservative_yellow_and_generic_messaging():
    extracted = [
        _doc("A.pdf", [{"name": "portfolio_company_count", "unit": "count", "value": 4,
                        "confidence": 0.5, "is_custom": True, "evidence": {"page": 1, "snippet": ""}}]),
        _doc("B.pdf", [{"name": "portfolio_company_count", "unit": "count", "value": 9,
                        "confidence": 0.5, "is_custom": True, "evidence": {"page": 1, "snippet": ""}}]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)

    assert len(flags) == 1
    assert flags[0].severity == "YELLOW"
    assert flags[0].metric == "portfolio_company_count"
    assert "Portfolio Company Count" in flags[0].detail


def test_no_flag_when_metric_only_present_in_one_document():
    extracted = [
        _doc("A.pdf", [_metric("dpi", "multiple", 0.45)]),
        _doc("B.pdf", []),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)
    assert flags == []


def test_no_flag_when_within_relative_tolerance():
    extracted = [
        _doc("A.pdf", [_metric("aum", "usd", 1_200_000_000)]),
        _doc("B.pdf", [_metric("aum", "usd", 1_210_000_000)]),
    ]
    rule = NumericMismatchRule(ToleranceConfig())
    flags = rule.apply(extracted)
    assert flags == []
