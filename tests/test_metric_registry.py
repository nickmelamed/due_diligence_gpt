from ddgpt.extract.metric_registry import (
    METRIC_REGISTRY,
    CATEGORY_ORDER,
    all_metrics,
    get,
    normalize_metric_name,
    slugify,
    category_for,
    display_label,
    format_metric_value,
)


def test_registry_has_seventeen_seed_metrics():
    # six original named fields + eleven new ones
    assert len(METRIC_REGISTRY) == 17
    assert set(METRIC_REGISTRY) >= {"aum", "net_irr", "tvpi", "target_irr", "mgmt_fee", "carry"}


def test_get_returns_metric_def_for_known_name():
    metric_def = get("dpi")
    assert metric_def is not None
    assert metric_def.display_label == "DPI"
    assert metric_def.unit == "multiple"
    assert metric_def.category == "performance"


def test_get_returns_none_for_unknown_name():
    assert get("not_a_real_metric") is None


def test_all_metrics_returns_every_seed_entry():
    assert len(all_metrics()) == len(METRIC_REGISTRY)


def test_normalize_exact_alias_match():
    name, is_custom = normalize_metric_name("Net IRR")
    assert name == "net_irr"
    assert is_custom is False


def test_normalize_is_case_and_hyphenation_insensitive():
    name, is_custom = normalize_metric_name("Distributions to Paid-In")
    assert name == "dpi"
    assert is_custom is False


def test_normalize_matches_full_metric_phrase():
    name, is_custom = normalize_metric_name("Total Value to Paid-In")
    assert name == "tvpi"
    assert is_custom is False


def test_normalize_management_fee_alias():
    name, is_custom = normalize_metric_name("Management Fee")
    assert name == "mgmt_fee"
    assert is_custom is False


def test_normalize_falls_back_to_stable_slug_for_unknown_metric():
    name, is_custom = normalize_metric_name("Portfolio Company Count")
    assert is_custom is True
    assert name == "portfolio_company_count"

    # Same input always slugifies to the same output -- required for
    # cross-document comparison of a never-seen-before metric.
    name_again, _ = normalize_metric_name("Portfolio Company Count")
    assert name_again == name


def test_normalize_empty_label_is_custom():
    name, is_custom = normalize_metric_name("")
    assert is_custom is True


def test_slugify_strips_punctuation_and_collapses_whitespace():
    assert slugify("Revenue Growth (YoY)") == "revenue_growth_yoy"
    assert slugify("  Multiple   Spaces  ") == "multiple_spaces"


def test_mgmt_fee_has_tighter_tolerance_override():
    metric_def = get("mgmt_fee")
    assert metric_def.tolerance_override == {"abs_pts": 0.25}


def test_irr_family_metrics_tagged_with_specialized_rule():
    for name in ("net_irr", "gross_irr", "target_irr"):
        assert get(name).specialized_rule == "irr_family"


def test_severity_preserves_original_rule_behavior():
    assert get("aum").default_severity == "RED"
    assert get("mgmt_fee").default_severity == "RED"
    assert get("carry").default_severity == "RED"
    assert get("hurdle_rate").default_severity == "RED"
    assert get("target_irr").default_severity == "YELLOW"
    assert get("tvpi").default_severity == "YELLOW"


def test_category_for_known_and_unknown_metrics():
    assert category_for("net_irr") == "performance"
    assert category_for("mgmt_fee") == "fees_and_terms"
    assert category_for("aum") == "capital_and_size"
    assert category_for("portfolio_company_count") == "other"


def test_category_order_covers_every_registry_category():
    registry_categories = {m.category for m in all_metrics()}
    assert registry_categories <= set(CATEGORY_ORDER)


def test_display_label_known_vs_custom():
    assert display_label("dpi") == "DPI"
    assert display_label("portfolio_company_count") == "Portfolio Company Count"


def test_format_metric_value_by_unit():
    assert format_metric_value(16.8, "percent") == "16.8%"
    assert format_metric_value(1.625, "multiple") == "1.62x"
    assert format_metric_value(1_250_000_000, "usd") == "$1.25B"
    assert format_metric_value(35_000_000, "usd") == "$35.00M"
    assert format_metric_value(2026, "year") == "2026"
    assert format_metric_value(4, "count") == "4"
    assert format_metric_value(None, "percent") == "N/A"
