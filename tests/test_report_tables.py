from ddgpt.report.tables import to_facts_table


def _doc(doc_name, doc_date, metrics, missing_fields=None, notes=None):
    return {
        "doc_name": doc_name,
        "doc_date": doc_date,
        "metrics": metrics,
        "missing_fields": missing_fields or [],
        "notes": notes or [],
    }


def _metric(name, value, unit, confidence=0.9, is_custom=False, page=1, snippet=""):
    return {
        "name": name, "value": value, "unit": unit, "confidence": confidence, "is_custom": is_custom,
        "evidence": {"page": page, "snippet": snippet},
    }


def test_to_facts_table_produces_one_row_per_document_metric_pair():
    extracted = [
        _doc("A.pdf", "2025-12-31", [_metric("aum", 1.2e9, "usd"), _metric("net_irr", 16.8, "percent")]),
        _doc("B.pdf", None, [_metric("dpi", 0.45, "multiple", is_custom=False)]),
    ]

    df = to_facts_table(extracted)

    assert len(df) == 3
    assert set(df["doc_name"]) == {"A.pdf", "B.pdf"}
    assert set(df[df["doc_name"] == "A.pdf"]["metric_name"]) == {"aum", "net_irr"}


def test_to_facts_table_includes_category_and_display_label():
    extracted = [_doc("A.pdf", None, [_metric("mgmt_fee", 2.0, "percent")])]
    df = to_facts_table(extracted)

    row = df.iloc[0]
    assert row["category"] == "fees_and_terms"
    assert row["display_label"] == "Management Fee"


def test_to_facts_table_includes_custom_metrics_with_flag():
    extracted = [_doc("A.pdf", None, [_metric("portfolio_company_count", 4, "count", is_custom=True)])]
    df = to_facts_table(extracted)

    row = df.iloc[0]
    # pandas stores this as numpy.bool_, not Python's built-in True -- `is`
    # would compare identity, not value, and always fail regardless of the
    # actual data.
    assert bool(row["is_custom"]) is True
    assert row["category"] == "other"


def test_to_facts_table_empty_extracted_returns_empty_dataframe_with_columns():
    df = to_facts_table([])
    assert len(df) == 0
    assert "doc_name" in df.columns
    assert "metric_name" in df.columns


def test_to_facts_table_document_with_no_metrics_contributes_no_rows():
    extracted = [_doc("A.pdf", None, [])]
    df = to_facts_table(extracted)
    assert len(df) == 0


def test_to_facts_table_carries_missing_fields_and_notes_per_row():
    extracted = [_doc("A.pdf", None, [_metric("aum", 1.2e9, "usd")], missing_fields=["net_irr.value"], notes=["a note"])]
    df = to_facts_table(extracted)

    row = df.iloc[0]
    assert row["missing_fields"] == "net_irr.value"
    assert row["notes"] == "a note"
