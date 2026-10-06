from ddgpt.extract.schemas import ExtractedDoc, MetricEntry
from ddgpt.extract.postprocess import verify_and_score
from ddgpt.io.loaders import Page
from ddgpt.provenance.evidence import Evidence


def test_verify_and_score_verifies_every_open_metric_not_just_legacy_six():
    page_text = "DPI stands at 0.45x as of this reporting period."
    pages = [Page(page_num=1, text=page_text)]

    doc = ExtractedDoc(doc_name="fund_report.pdf")
    doc.metrics = [
        MetricEntry(name="dpi", raw_label="DPI", unit="multiple", value=0.45, confidence=0.9,
                    evidence=Evidence(doc_name="fund_report.pdf", page=1, snippet="DPI stands at 0.45x")),
    ]

    result = verify_and_score(doc, pages)

    dpi = next(m for m in result.metrics if m.name == "dpi")
    # verbatim evidence match -- confidence shouldn't be zeroed or flagged
    assert dpi.confidence > 0
    assert not any("not found verbatim" in n for n in result.notes)


def test_verify_and_score_flags_evidence_not_found_for_custom_metric():
    pages = [Page(page_num=1, text="This page says nothing about that metric at all.")]

    doc = ExtractedDoc(doc_name="x.pdf")
    doc.metrics = [
        MetricEntry(name="portfolio_company_count", raw_label="Portfolio Company Count", unit="count",
                    value=4, confidence=0.9,
                    evidence=Evidence(doc_name="x.pdf", page=1, snippet="a snippet that isn't on the page")),
    ]

    result = verify_and_score(doc, pages)

    assert any("not found verbatim" in n for n in result.notes)


def test_verify_and_score_marks_missing_core_fields_not_present_in_metrics():
    doc = ExtractedDoc(doc_name="x.pdf")
    doc.metrics = [MetricEntry(name="aum", raw_label="AUM", unit="usd", value=1.2e9, confidence=0.9)]

    result = verify_and_score(doc, [])

    assert "net_irr.value" in result.missing_fields
    assert "carry.hurdle" in result.missing_fields
    assert "aum.value" not in result.missing_fields


def test_verify_and_score_does_not_flag_custom_metrics_as_missing_core_fields():
    # A document simply not discussing some never-seen-before custom metric
    # isn't "missing" the way a document lacking AUM is -- only the six
    # legacy names (+ hurdle_rate) are ever added to missing_fields.
    doc = ExtractedDoc(doc_name="x.pdf")
    doc.metrics = [
        MetricEntry(name="portfolio_company_count", raw_label="Portfolio Company Count",
                    unit="count", value=4, confidence=0.9, is_custom=True),
    ]

    result = verify_and_score(doc, [])

    assert "portfolio_company_count.value" not in result.missing_fields


def test_verify_and_score_applies_extra_discount_when_metric_needed_retry():
    page_text = "Net IRR: 16.8%"
    pages = [Page(page_num=1, text=page_text)]

    clean = ExtractedDoc(doc_name="a.pdf")
    clean.metrics = [
        MetricEntry(name="net_irr", raw_label="Net IRR", unit="percent", value=16.8, confidence=0.9,
                    evidence=Evidence(doc_name="a.pdf", page=1, snippet="Net IRR: 16.8%")),
    ]

    retried = ExtractedDoc(doc_name="b.pdf")
    retried.metrics = [
        MetricEntry(name="net_irr", raw_label="Net IRR", unit="percent", value=16.8, confidence=0.9,
                    needed_retry=True,
                    evidence=Evidence(doc_name="b.pdf", page=1, snippet="Net IRR: 16.8%")),
    ]

    clean_result = verify_and_score(clean, pages)
    retried_result = verify_and_score(retried, pages)

    clean_conf = next(m for m in clean_result.metrics if m.name == "net_irr").confidence
    retried_conf = next(m for m in retried_result.metrics if m.name == "net_irr").confidence

    # Same evidence quality (verbatim match) both times -- the only
    # difference is needed_retry, which must lower confidence a bit further.
    assert retried_conf < clean_conf


def test_verify_and_score_resyncs_legacy_fields_with_post_verification_confidence():
    pages = [Page(page_num=1, text="Net IRR: 16.8%")]

    doc = ExtractedDoc(doc_name="x.pdf")
    doc.metrics = [
        MetricEntry(name="net_irr", raw_label="Net IRR", unit="percent", value=16.8, confidence=0.9,
                    evidence=Evidence(doc_name="x.pdf", page=1, snippet="Net IRR: 16.8%")),
    ]

    result = verify_and_score(doc, pages)

    verified_entry = next(m for m in result.metrics if m.name == "net_irr")
    # The legacy field must reflect the post-verification confidence, not
    # whatever it was before verify_metric ran.
    assert result.net_irr.confidence == verified_entry.confidence
    assert result.net_irr.value == 16.8
