from ddgpt.render.pdf_report import compute_data_quality


def _metric(name, value, confidence=0.8):
    return {"name": name, "value": value, "confidence": confidence}


def test_counts_whatever_metrics_are_actually_present_not_a_fixed_six():
    # A portfolio-terms document with no IRR/TVPI fields at all, but several
    # metrics outside the old fixed six (hurdle_rate, gp_commitment, and a
    # fully custom one) -- all of it should count.
    doc = {
        "doc_name": "portfolio_terms.pdf",
        "metrics": [
            _metric("carry", 20.0),
            _metric("hurdle_rate", 8.0),
            _metric("mgmt_fee", 2.0),
            _metric("aum", 1.2e9),
            _metric("gp_commitment", 35_000_000),
            _metric("portfolio_company_count", 4),
        ],
        "notes": [],
    }

    rows = compute_data_quality([doc])

    assert len(rows) == 1
    assert rows[0]["metrics_found"] == 6
    assert "fields_total" not in rows[0]
    # carry, hurdle_rate, mgmt_fee, and aum are core. The other two are not.
    assert (rows[0]["core_found"], rows[0]["core_total"]) == (4, 7)


def test_avg_confidence_none_when_no_metrics():
    doc = {"doc_name": "empty.pdf", "metrics": [], "notes": []}
    rows = compute_data_quality([doc])
    assert rows[0]["metrics_found"] == 0
    assert rows[0]["avg_confidence"] is None


def test_fuzzy_and_not_found_counts_still_derived_from_notes():
    doc = {
        "doc_name": "a.pdf",
        "metrics": [_metric("aum", 1.2e9)],
        "notes": ["aum matched page fuzzily", "carry not found verbatim"],
    }
    rows = compute_data_quality([doc])
    assert rows[0]["fuzzy_matches"] == 1
    assert rows[0]["not_found"] == 1
