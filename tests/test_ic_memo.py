from ddgpt.report.ic_memo import generate_ic_summary


def _doc(doc_name, doc_date, metrics):
    return {"doc_name": doc_name, "doc_date": doc_date, "metrics": metrics}


def _metric(name, value, unit, confidence=0.9, page=1, snippet="a snippet"):
    return {
        "name": name, "value": value, "unit": unit, "confidence": confidence,
        "evidence": {"page": page, "snippet": snippet},
    }


def test_generate_ic_summary_includes_every_document():
    extracted = [
        _doc("A.pdf", "2025-12-31", [_metric("aum", 1.2e9, "usd")]),
        _doc("B.pdf", None, [_metric("dpi", 0.45, "multiple")]),
    ]
    summary = generate_ic_summary(extracted, flags=[])

    assert "A.pdf" in summary
    assert "B.pdf" in summary
    assert "AUM" in summary
    assert "DPI" in summary


def test_generate_ic_summary_reports_data_completeness_from_open_metrics():
    extracted = [_doc("A.pdf", None, [_metric("aum", 1.2e9, "usd"), _metric("net_irr", 16.8, "percent")])]
    summary = generate_ic_summary(extracted, flags=[])

    assert "2** metrics extracted" in summary


def test_generate_ic_summary_handles_document_with_no_metrics():
    extracted = [_doc("A.pdf", None, [])]
    summary = generate_ic_summary(extracted, flags=[])
    assert "No metrics extracted" in summary
    assert "No evidence-backed metrics" in summary


def test_generate_ic_summary_includes_evidence_snippets():
    extracted = [_doc("A.pdf", None, [_metric("aum", 1.2e9, "usd", page=3, snippet="AUM: $1.20B")])]
    summary = generate_ic_summary(extracted, flags=[])
    assert "p.3" in summary
    assert "AUM: $1.20B" in summary


def test_generate_ic_summary_includes_flags_queue():
    extracted = [_doc("A.pdf", None, [])]
    flags = [{
        "severity": "RED", "type": "USD_MISMATCH", "docs": "A.pdf vs B.pdf",
        "detail": "AUM differs", "evidence": "...", "why_it_matters": "...", "question_to_ask": "...",
    }]
    summary = generate_ic_summary(extracted, flags=flags)
    assert "RED: USD_MISMATCH" in summary


def test_generate_ic_summary_no_flags_message():
    extracted = [_doc("A.pdf", None, [])]
    summary = generate_ic_summary(extracted, flags=[])
    assert "No flags detected." in summary
